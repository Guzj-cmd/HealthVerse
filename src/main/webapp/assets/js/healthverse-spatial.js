import * as THREE from 'three';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { TGALoader } from 'three/addons/loaders/TGALoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const $ = s => document.querySelector(s);
const ctx = $('meta[name="app-context"]').content;
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const host = $('#spatialWorld');
let renderer;
try { renderer = new THREE.WebGLRenderer({antialias:true, alpha:true, powerPreference:'low-power'}); }
catch { host.remove(); document.body.classList.add('spatial-unavailable'); }
if (renderer) initialize();

function initialize() {
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setSize(innerWidth, innerHeight);
  renderer.setClearColor(0xeaf2ff, 1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .85;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.autoClear = false;
  host.append(renderer.domElement);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envRoom = new RoomEnvironment();
  const env = pmrem.fromScene(envRoom, .04);
  envRoom.dispose(); pmrem.dispose();
  const material = (color, roughness=.4, metalness=.05) => new THREE.MeshStandardMaterial({color, roughness, metalness});
  const white = material(0xe4eeff), blue = material(0x4279ef), pale = material(0x8cb4f4), ink = material(0x305ac0);
  const glass = new THREE.MeshPhysicalMaterial({color:0xb1d0ff, roughness:.15, metalness:.15, transparent:true, opacity:.35, side:THREE.DoubleSide});
  const world = new THREE.Scene(); world.background = new THREE.Color(0xc4dbff); world.environment = env.texture;
  world.fog = new THREE.Fog(0xc4dbff, 18, 44);
  const camera = new THREE.PerspectiveCamera(42, innerWidth/innerHeight, .1, 100);
  const background = new THREE.Group(); world.add(background);
  world.add(new THREE.HemisphereLight(0xffffff, 0x7ea4e9, 1.1));
  const light = new THREE.DirectionalLight(0xffffff, 2); light.position.set(-3,8,5); world.add(light);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(100,100), material(0xd8e7ff,.65));
  floor.rotation.x=-Math.PI/2; floor.position.y=-3; world.add(floor);
  for(let i=0;i<6;i++) {
    const arch = new THREE.Mesh(new THREE.TorusGeometry(4+i*.8,.06+i*.017,12,100), i%2 ? glass : pale);
    arch.position.set((i-3)*2.6, .6, -5-i*2); arch.rotation.y=.35; background.add(arch);
  }
  const floats=[];
  for(let i=0;i<14;i++) {
    const mesh = new THREE.Mesh(i%3===0 ? new THREE.TorusGeometry(.35,.13,20,48) : new THREE.SphereGeometry(.16+(i%4)*.12,24,18), i%3===0 ? blue : i%2 ? glass : white);
    mesh.position.set(Math.sin(i*2.4)*10, Math.cos(i*1.8)*4, -2-(i%5)*2);
    mesh.userData.base=mesh.position.clone(); background.add(mesh); floats.push(mesh);
  }
  const room = new THREE.Scene(); room.environment=env.texture;
  room.add(new THREE.HemisphereLight(0xffffff,0x93afff,1.15));
  const sun = new THREE.DirectionalLight(0xffffff,2.2); sun.position.set(-3,7,5); sun.castShadow=true;
  sun.shadow.mapSize.set(1024,1024); sun.shadow.camera.left=-5; sun.shadow.camera.right=5; sun.shadow.camera.top=5; sun.shadow.camera.bottom=-5; sun.shadow.bias=-.001; room.add(sun);
  const furniture = new THREE.Group(); room.add(furniture);
  function box(parent,w,h,d,x,y,z,mat=white,r=.05) {
    const m=new THREE.Mesh(new RoundedBoxGeometry(w,h,d,3,r),mat); m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;
  }
  function cylinder(parent,rt,rb,h,x,y,z,mat=white) {
    const m=new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,48),mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;parent.add(m);return m;
  }
  cylinder(furniture,2.7,2.8,.18,0,-.12,0,pale);
  const platform=cylinder(furniture,2.64,2.64,.035,0,-.015,0,white);
  box(furniture,2.25,.12,1.05,.3,1.02,-.3,white);
  for(const x of [-.65,1.25]) for(const z of [-.7,.1]) box(furniture,.065,1,.065,x,.49,z,pale,.015);
  const monitor = new THREE.Group(); furniture.add(monitor);
  box(monitor,.45,.045,.3,.45,1.1,-.5,pale);
  box(monitor,.075,.4,.06,.45,1.3,-.57,pale);
  box(monitor,1.04,.63,.07,.45,1.65,-.57,ink);
  box(monitor,.96,.55,.014,.45,1.65,-.524,material(0xc8dfff,.2));
  for(let i=0;i<4;i++) box(monitor,.6-i*.08,.025,.018,.36,1.76-i*.085,-.51,white,.01);
  box(furniture,.67,.025,.24,.4,1.1,-.02,pale,.01);
  box(furniture,.36,.07,.46,-.45,1.11,-.23,blue,.015);
  box(furniture,.34,.045,.44,-.45,1.115,-.22,white,.005);
  box(furniture,.36,.012,.46,-.45,1.143,-.23,blue,.005);
  const pencil=box(furniture,.014,.014,.28,-.2,1.1,.12,ink,.004);pencil.rotation.y=.3;
  for(let row=0;row<3;row++) for(let col=0;col<10;col++) box(furniture,.044,.009,.044,.12+col*.058,1.118,-.10+row*.065,white,.004);
  const cup = cylinder(furniture,.095,.075,.23,1.1,1.19,-.25,blue);
  const handle=new THREE.Mesh(new THREE.TorusGeometry(.075,.018,12,24),blue);handle.position.set(1.2,1.2,-.25);furniture.add(handle);
  const chair = new THREE.Group();furniture.add(chair);
  box(chair,.62,.12,.6,-.55,.62,.65,blue,.07);
  box(chair,.62,.65,.12,-.55,.98,.93,pale,.08);
  cylinder(chair,.055,.07,.48,-.55,.3,.65,pale);
  for(let i=0;i<5;i++){const leg=box(chair,.06,.05,.6,-.55,.07,.65,pale,.02);leg.rotation.y=i*Math.PI*2/5;}
  const rim=new THREE.Mesh(new THREE.TorusGeometry(2.66,.014,8,100),blue);rim.rotation.x=Math.PI/2;rim.position.y=.01;furniture.add(rim);
  // Objects stay conceptual until the user supplies real observations.
  const selectable=[{mesh:monitor,key:'monitor',label:'显示器 · 可调整高度'},{mesh:chair,key:'chair',label:'座椅 · 观察支撑与相对位置'},{mesh:cup,key:'cup',label:'水杯 · 比较可达位置'}];
  let human=null;
  const modelStatus=document.createElement('div'); modelStatus.className='spatial-model-status'; modelStatus.textContent='正在加载完整人体模型…'; $('#scenePlaceholder').append(modelStatus);
  const assetManager = new THREE.LoadingManager();
  assetManager.addHandler(/\.tga$/i,new TGALoader());
  const studentLoader=new FBXLoader(assetManager).setResourcePath(`${ctx}/assets/models/student/`);
  studentLoader.load(`${ctx}/assets/models/student/student.fbx`, model=>{
    human=model;
    human.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;const convert=m=>new THREE.MeshStandardMaterial({map:m.map,normalMap:m.normalMap,color:m.color,roughness:.76,metalness:0,transparent:m.transparent,opacity:m.opacity,side:m.side,envMapIntensity:.55});o.material=Array.isArray(o.material)?o.material.map(convert):convert(o.material);}});
    human.updateMatrixWorld(true);
    const bounds=new THREE.Box3().setFromObject(human); const size=bounds.getSize(new THREE.Vector3());
    human.scale.multiplyScalar(1.7/size.y); human.updateMatrixWorld(true);
    const b=new THREE.Box3().setFromObject(human);const center=b.getCenter(new THREE.Vector3());
    human.position.set(-1.45-center.x,-b.min.y,.15-center.z);
    room.add(human); modelStatus.textContent='学生角色示意 · 非本人重建或身高测量';
    document.body.dataset.humanModel='loaded';
  },undefined,()=>{modelStatus.textContent='人体模型加载失败，请刷新重试';document.body.dataset.humanModel='error';});
  const slots = ['#scenePlaceholder','.body-stage','#compareScene'].map((selector,index)=>{
    const el=$(selector);el.classList.add('spatial-slot');
    const cam=new THREE.PerspectiveCamera(38,1,.05,50);cam.position.set(4,3.2,5.5);
    const controls=new OrbitControls(cam,el);controls.target.set(0,.9,0);controls.enableDamping=true;controls.enableZoom=false;controls.enablePan=false;controls.minPolarAngle=.25;controls.maxPolarAngle=1.48;controls.update();
    const toolbar=document.createElement('div');toolbar.className='spatial-tools';
    toolbar.innerHTML='<span>拖动旋转 · 点选物体</span><button type="button" data-camera="human">人物细节</button><button type="button" data-camera="front">正面</button><button type="button" data-camera="side">侧面</button><button type="button" data-camera="top">俯视</button><button type="button" data-camera="reset">复位</button>';
    el.append(toolbar);
    const hint=document.createElement('div');hint.className='spatial-hint';hint.textContent=index===1?'人体示意 · 校准数据来自真实输入':'概念空间 · 不是相机三维重建';el.append(hint);
    let destination=null;
    toolbar.addEventListener('pointerdown',e=>e.stopPropagation());
    toolbar.addEventListener('click',e=>{const k=e.target.dataset.camera;if(k){const hx=index===1?0:-1.45;controls.target.set(k==='human'?hx:0,k==='human'?1.35:.9,0);destination=new THREE.Vector3(...(k==='human'?[hx,1.65,2.5]:k==='front'?[0,2.1,6.2]:k==='side'?[6,2.4,0]:k==='top'?[0,7,1.9]:[4,3.2,5.5]));}});
    const ray=new THREE.Raycaster();let down;
    el.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];destination=null;});
    el.addEventListener('pointerup',e=>{
      if(e.target.closest('button') || !down || Math.hypot(e.clientX-down[0],e.clientY-down[1])>6)return;
      const r=el.getBoundingClientRect();ray.setFromCamera(new THREE.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),cam);
      const hit=ray.intersectObjects(selectable.map(o=>o.mesh),true)[0];if(!hit)return;
      const selected=selectable.find(o=>{let m=hit.object;while(m){if(m===o.mesh)return true;m=m.parent;}return false;});
      if(selected){hint.textContent=selected.label;document.querySelector(`[data-object="${selected.key}"]`)?.click();}
    });
    return {el,cam,controls,index,update:()=>{if(destination){cam.position.lerp(destination,reduced.matches?1:.085);if(cam.position.distanceTo(destination)<.01)destination=null;}controls.update();}};
  });
  // Straight connectors with a single aligned arrowhead, replacing hand-drawn paths.
  document.querySelectorAll('.method-flow-arrow').forEach((svg,i)=>{
    svg.innerHTML=`<defs><marker id="spatialArrow${i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="#799ce3" stroke-width="1.6"/></marker></defs><path d="M12 36H130" fill="none" stroke="#799ce3" stroke-width="2" marker-end="url(#spatialArrow${i})"/>`;
  });
  document.body.classList.add('spatial-ready');
  const screenTargets={sense:[0,1.3,14],body:[-2,1.8,13],design:[2,1.2,13],experiment:[0,3,15],memory:[-3,1,14],research:[0,1,16]};
  camera.position.set(0,1.3,14);
  let pointer=new THREE.Vector2(), paused=false, last=0;
  const motionButton=document.createElement('button');motionButton.type='button';motionButton.className='quiet-btn';motionButton.textContent='暂停空间动效';motionButton.setAttribute('aria-pressed','false');$('.chrome-actions').prepend(motionButton);
  motionButton.addEventListener('click',()=>{paused=!paused;motionButton.textContent=paused?'开启空间动效':'暂停空间动效';motionButton.setAttribute('aria-pressed',String(paused));});
  window.addEventListener('pointermove',e=>{pointer.set((e.clientX/innerWidth-.5)*2,(e.clientY/innerHeight-.5)*2);},{passive:true});
  let activePanel;
  document.addEventListener('pointermove',e=>{
    const p=e.target.closest('.panel');if(activePanel&&activePanel!==p){activePanel.style.removeProperty('--tilt-x');activePanel.style.removeProperty('--tilt-y');}activePanel=p;
    if(p&&!paused&&!reduced.matches&&!e.target.closest('.spatial-slot,input,video')){const r=p.getBoundingClientRect();p.style.setProperty('--tilt-x',`${-(e.clientY-r.top-r.height/2)/r.height*1.5}deg`);p.style.setProperty('--tilt-y',`${(e.clientX-r.left-r.width/2)/r.width*1.5}deg`);}
  },{passive:true});
  window.addEventListener('resize',()=>renderer.setSize(innerWidth,innerHeight));
  renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();document.body.classList.remove('spatial-ready');modelStatus.textContent='3D 显示已暂停；刷新可恢复，真实输入仍可使用';});
  function frame(ms){
    requestAnimationFrame(frame);if(document.hidden||ms-last<32)return;last=ms;
    const motion=!paused&&!reduced.matches;const time=ms*.0003;
    const current=$('.view.active')?.dataset.screen||'sense'; const target=screenTargets[current]||screenTargets.sense;
    camera.position.lerp(new THREE.Vector3(target[0]+(motion?pointer.x*.65:0),target[1]+(motion?-pointer.y*.3:0),target[2]),reduced.matches?1:.04);
    camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();camera.lookAt(0,0,-4);
    if(motion)floats.forEach((m,i)=>{m.position.y=m.userData.base.y+Math.sin(time+i)*.3;m.rotation.x=time*.2+i;m.rotation.y=time*.3;});
    renderer.setScissorTest(false);renderer.setViewport(0,0,innerWidth,innerHeight);renderer.clear();renderer.render(world,camera);
    slots.forEach(slot=>{
      if(!slot.el.checkVisibility()||slot.el.closest('[hidden]'))return;
      const r=slot.el.getBoundingClientRect();if(r.bottom<0||r.top>innerHeight||r.width===0)return;
      slot.update();slot.cam.aspect=r.width/r.height;slot.cam.updateProjectionMatrix();
      furniture.visible=slot.index!==1;
      if(human)human.position.x=slot.index===1?0:-1.45;
      const after=$('#compareScene').classList.contains('after');
      const lift=slot.index===2&&after?Number($('#heightInput').value)*.018:0;
      monitor.position.y=THREE.MathUtils.lerp(monitor.position.y,lift,reduced.matches?1:.18);
      cup.position.x=slot.index===2&&after&&$('.plan-card.active')?.dataset.plan==='b' ? .82 : 1.1;
      handle.position.x=cup.position.x+.1;
      renderer.setScissorTest(true);renderer.setScissor(r.left,Math.max(0,innerHeight-r.bottom),r.width,Math.min(innerHeight,r.bottom)-Math.max(0,r.top));
      renderer.setViewport(r.left,innerHeight-r.bottom,r.width,r.height);renderer.clearDepth();renderer.render(room,slot.cam);
    });
    renderer.setScissorTest(false);
  }
  requestAnimationFrame(frame);
  window.addEventListener('pagehide',()=>{renderer.dispose();env.dispose();slots.forEach(s=>s.controls.dispose());},{once:true});
}
