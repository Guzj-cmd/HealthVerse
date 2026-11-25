const ANGLES=[[11,13,15],[12,14,16],[11,23,25],[12,24,26],[23,25,27],[24,26,28],[7,11,23],[8,12,24]];
const JOINTS=[0,7,8,11,12,13,14,15,16,23,24,25,26];
const norm=v=>Math.hypot(...v);
const difference=(a,b)=>a.map((value,index)=>value-b[index]);

function angle(points,a,b,c){
  const left=difference(points[a],points[b]);
  const right=difference(points[c],points[b]);
  const denominator=norm(left)*norm(right);
  if(denominator<1e-9)return 0;
  const cosine=left.reduce((sum,value,index)=>sum+value*right[index],0)/denominator;
  return Math.acos(Math.max(-1,Math.min(1,cosine)))/Math.PI;
}

export function poseFeatures(landmarks){
  if(!Array.isArray(landmarks)||landmarks.length!==33)throw new TypeError('expected 33 MediaPipe landmarks');
  const xyz=landmarks.map(point=>[Number(point.x),Number(point.y),Number(point.z??0)]);
  if(xyz.some(point=>point.some(value=>!Number.isFinite(value))))throw new TypeError('landmarks must contain finite x, y and z coordinates');
  const visibility=landmarks.map(point=>Math.max(0,Math.min(1,Number(point.visibility??1))));
  const center=(left,right)=>[0,1,2].map(axis=>(xyz[left][axis]+xyz[right][axis])/2);
  const hips=center(23,24),shoulders=center(11,12);
  const scale=Math.max(norm(difference(shoulders,hips)),norm(difference(xyz[11],xyz[12])),1e-4);
  const normalized=xyz.map(point=>point.map((value,axis)=>(value-hips[axis])/scale));
  const values=[...normalized.flat(),...visibility];
  ANGLES.forEach(([a,b,c])=>values.push(angle(normalized,a,b,c)));
  values.push(Math.atan2(normalized[12][1]-normalized[11][1],normalized[12][0]-normalized[11][0])/Math.PI);
  values.push(Math.atan2(normalized[24][1]-normalized[23][1],normalized[24][0]-normalized[23][0])/Math.PI);
  const trunk=difference(shoulders,hips),head=center(7,8),neck=difference(head,shoulders);
  values.push(Math.atan2(trunk[0],-trunk[1])/Math.PI,Math.atan2(neck[0],-neck[1])/Math.PI);
  JOINTS.forEach((left,offset)=>JOINTS.slice(offset+1).forEach(right=>{
    const delta=difference(normalized[right],normalized[left]),distance=norm(delta),divisor=Math.max(distance,1e-9);
    values.push(delta[0]/divisor,delta[1]/divisor,delta[2]/divisor,distance);
  }));
  if(values.length!==456)throw new Error(`feature schema mismatch: ${values.length}`);
  return Float32Array.from(values);
}

function softmax(values){
  const maximum=Math.max(...values),exponentials=values.map(value=>Math.exp(value-maximum));
  const total=exponentials.reduce((sum,value)=>sum+value,0);
  return exponentials.map(value=>value/total);
}

function predictHist(model,features){
  const raw=[...model.baseline];
  model.trees.forEach(iteration=>iteration.forEach((nodes,classIndex)=>{
    let index=0;
    while(!nodes[index][6]){
      const [feature,threshold,left,right,,missingLeft]=nodes[index],observed=features[feature];
      index=Number.isNaN(observed)?(missingLeft?left:right):(observed<=threshold?left:right);
    }
    raw[classIndex]+=nodes[index][4];
  }));
  return softmax(raw);
}

function predictForest(model,features){
  const probabilities=Array(model.classes.length).fill(0);
  model.trees.forEach(nodes=>{
    let index=0;
    while(nodes[index][2]!==-1){
      const [feature,threshold,left,right]=nodes[index];
      index=features[feature]<=threshold?left:right;
    }
    nodes[index][4].forEach((value,classIndex)=>probabilities[classIndex]+=value);
  });
  return probabilities.map(value=>value/model.trees.length);
}

export function predictPortableModel(model,features){
  if(features.length!==456)throw new Error('expected 456 posture features');
  const probabilities=model.type==='hist_gradient_boosting_classifier'?predictHist(model,features):
    model.type==='random_forest_classifier'?predictForest(model,features):null;
  if(!probabilities)throw new TypeError(`unsupported portable model: ${model.type}`);
  const best=probabilities.reduce((winner,value,index)=>value>probabilities[winner]?index:winner,0);
  return {label:model.classes[best],confidence:probabilities[best],probabilities:Object.fromEntries(model.classes.map((label,index)=>[label,probabilities[index]]))};
}

export function classifyPose(artifact,landmarks){
  const features=poseFeatures(landmarks);
  return {upper:predictPortableModel(artifact.upper.model,features),lower:predictPortableModel(artifact.lower.model,features),version:artifact.version,confidenceThreshold:artifact.confidence_threshold};
}
