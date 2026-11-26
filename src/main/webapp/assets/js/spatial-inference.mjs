const OBJECT_TYPES = {
  tv: ['screen', '显示屏'],
  laptop: ['screen', '笔记本电脑'],
  chair: ['chair', '座椅'],
  'dining table': ['table', '桌面'],
  keyboard: ['keyboard', '键盘'],
  mouse: ['mouse', '鼠标'],
  cup: ['cup', '水杯'],
  bottle: ['bottle', '水瓶'],
  book: ['book', '书本'],
  'cell phone': ['phone', '手机']
};

const clamp = (value, low = 0, high = 1) => Math.min(high, Math.max(low, value));

function visible(point) {
  return Boolean(point) && (point.visibility == null || point.visibility >= 0.35);
}

function midpoint(first, second) {
  if (!visible(first) || !visible(second)) return null;
  return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
}

function distance(first, second) {
  return Math.hypot(first.x - second.x, first.y - second.y);
}

function confidenceOf(...values) {
  const finite = values.filter(Number.isFinite);
  return finite.length ? Math.min(...finite.map((value) => clamp(value))) : 0;
}

export function normalizeDetections(result, width, height, minimumScore = 0.35) {
  if (!width || !height) return [];
  const detections = Array.isArray(result?.detections) ? result.detections : [];
  return detections.flatMap((detection, index) => {
    const category = detection?.categories?.[0];
    const mapping = OBJECT_TYPES[category?.categoryName];
    const box = detection?.boundingBox;
    if (!mapping || !box || !Number.isFinite(category?.score) || category.score < minimumScore) return [];
    const normalized = {
      x: clamp(box.originX / width),
      y: clamp(box.originY / height),
      width: clamp(box.width / width),
      height: clamp(box.height / height)
    };
    normalized.width = Math.min(normalized.width, 1 - normalized.x);
    normalized.height = Math.min(normalized.height, 1 - normalized.y);
    return [{
      id: `${mapping[0]}-${index}`,
      type: mapping[0],
      label: mapping[1],
      sourceLabel: category.categoryName,
      score: category.score,
      box: normalized,
      center: { x: normalized.x + normalized.width / 2, y: normalized.y + normalized.height / 2 }
    }];
  }).sort((first, second) => second.score - first.score);
}

function containsWithMargin(box, point, margin = 0) {
  return point.x >= box.x - margin && point.x <= box.x + box.width + margin
    && point.y >= box.y - margin && point.y <= box.y + box.height + margin;
}

function firstObject(detections, type) {
  return detections.find((item) => item.type === type);
}

export function inferSpatialRelations(landmarks, detections) {
  if (!Array.isArray(landmarks) || landmarks.length < 25) return [];
  const relations = [];
  const shoulders = midpoint(landmarks[11], landmarks[12]);
  const hips = midpoint(landmarks[23], landmarks[24]);
  const eyes = midpoint(landmarks[2], landmarks[5]) || (visible(landmarks[0]) ? landmarks[0] : null);
  const shoulderWidth = visible(landmarks[11]) && visible(landmarks[12])
    ? Math.max(0.04, distance(landmarks[11], landmarks[12])) : 0.16;
  const poseConfidence = confidenceOf(
    landmarks[11]?.visibility ?? 1,
    landmarks[12]?.visibility ?? 1,
    landmarks[23]?.visibility ?? 1,
    landmarks[24]?.visibility ?? 1
  );

  const screen = firstObject(detections, 'screen');
  if (screen && eyes) {
    const verticalOffset = (screen.center.y - eyes.y) / shoulderWidth;
    const horizontalOffset = Math.abs(screen.center.x - eyes.x) / shoulderWidth;
    let type = 'screen_eye_aligned';
    let label = '屏幕与视线大致对齐';
    let severity = 'ok';
    let recommendation = '当前二维位置未显示明显高度偏移。';
    if (verticalOffset > 0.45) {
      type = 'screen_below_eye';
      label = '屏幕中心低于视线';
      severity = 'review';
      recommendation = '可预览小幅抬高屏幕的方案，再由你确认。';
    } else if (verticalOffset < -0.55) {
      type = 'screen_above_eye';
      label = '屏幕中心高于视线';
      severity = 'review';
      recommendation = '可预览小幅降低屏幕的方案，再由你确认。';
    }
    relations.push({
      id: 'eye-screen-height', type, label, severity,
      confidence: confidenceOf(screen.score, poseConfidence), objectId: screen.id,
      evidence: `屏幕中心相对眼部的纵向偏移为 ${verticalOffset.toFixed(2)} 个肩宽`,
      recommendation,
      measures: { verticalOffsetShoulderWidths: verticalOffset }
    });
    if (horizontalOffset > 1.35) {
      relations.push({
        id: 'eye-screen-horizontal', type: 'screen_off_center', label: '屏幕偏离身体中线', severity: 'review',
        confidence: confidenceOf(screen.score, poseConfidence), objectId: screen.id,
        evidence: `屏幕与眼部中点的水平偏移为 ${horizontalOffset.toFixed(2)} 个肩宽`,
        recommendation: '可先将主要内容移近身体中线，不会自动移动设备。',
        measures: { horizontalOffsetShoulderWidths: horizontalOffset }
      });
    }
  }

  const chair = firstObject(detections, 'chair');
  if (chair && hips) {
    const seated = containsWithMargin(chair.box, hips, 0.08);
    relations.push({
      id: 'person-chair-contact',
      type: seated ? 'seated_contact' : 'chair_nearby',
      label: seated ? '骨盆与座椅区域重合' : '检测到座椅，但未确认坐姿接触',
      severity: seated ? 'ok' : 'uncertain',
      confidence: confidenceOf(chair.score, poseConfidence), objectId: chair.id,
      evidence: seated ? '髋部中点落在座椅检测框的扩展区域内' : '髋部中点不在座椅检测框的扩展区域内',
      recommendation: seated ? '已建立人–座椅二维关系。' : '需要调整镜头或由用户确认是否坐在该座椅上。',
      measures: { hipInsideChairRegion: seated }
    });
  }

  const reachTargets = detections.filter((item) => ['keyboard', 'mouse', 'cup', 'bottle', 'book', 'phone'].includes(item.type));
  const wrists = [landmarks[15], landmarks[16]].filter(visible);
  if (wrists.length) {
    reachTargets.slice(0, 4).forEach((target) => {
      const nearest = Math.min(...wrists.map((wrist) => distance(wrist, target.center))) / shoulderWidth;
      relations.push({
        id: `reach-${target.id}`, type: nearest <= 1.8 ? 'within_visual_reach' : 'outside_visual_reach',
        label: `${target.label}${nearest <= 1.8 ? '位于手部附近' : '距当前手部较远'}`,
        severity: nearest <= 1.8 ? 'ok' : 'review',
        confidence: confidenceOf(target.score, poseConfidence), objectId: target.id,
        evidence: `最近手腕与${target.label}中心的二维距离为 ${nearest.toFixed(2)} 个肩宽`,
        recommendation: nearest <= 1.8 ? '仅能确认二维画面上较近。' : '如果该物体需要频繁使用，可预览将它移近的方案。',
        measures: { wristDistanceShoulderWidths: nearest }
      });
    });
  }

  return relations.sort((first, second) => {
    const order = { review: 0, uncertain: 1, ok: 2 };
    return order[first.severity] - order[second.severity] || second.confidence - first.confidence;
  });
}

export class TemporalEvidenceTracker {
  constructor(maxEvents = 120) {
    this.maxEvents = maxEvents;
    this.current = null;
    this.events = [];
    this.totals = {};
  }

  update(label, confidence, atMs) {
    if (!label || !Number.isFinite(atMs)) return this.snapshot(atMs);
    if (!this.current) {
      this.current = { label, confidence, startedAt: atMs, updatedAt: atMs };
      return this.snapshot(atMs);
    }
    if (this.current.label === label) {
      this.current.updatedAt = atMs;
      this.current.confidence = Math.max(this.current.confidence, confidence || 0);
      return this.snapshot(atMs);
    }
    this.close(atMs);
    this.current = { label, confidence, startedAt: atMs, updatedAt: atMs };
    return this.snapshot(atMs);
  }

  close(atMs) {
    if (!this.current) return;
    const endedAt = Math.max(atMs, this.current.startedAt);
    const durationMs = endedAt - this.current.startedAt;
    const event = { ...this.current, endedAt, durationMs };
    this.events.push(event);
    if (this.events.length > this.maxEvents) this.events.shift();
    this.totals[event.label] = (this.totals[event.label] || 0) + durationMs;
    this.current = null;
  }

  reset() {
    this.current = null;
    this.events = [];
    this.totals = {};
  }

  snapshot(atMs = this.current?.updatedAt || 0) {
    const current = this.current ? {
      ...this.current,
      durationMs: Math.max(0, atMs - this.current.startedAt)
    } : null;
    const totals = { ...this.totals };
    if (current) totals[current.label] = (totals[current.label] || 0) + current.durationMs;
    return { current, totals, recent: this.events.slice(-8) };
  }
}

export function summarizeObjects(detections) {
  if (!detections.length) return '未检测到支持的工作区物体';
  return detections.slice(0, 5).map((item) => `${item.label} ${Math.round(item.score * 100)}%`).join('、');
}

function median(values) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function deriveBodyProfile(samples) {
  const valid = (samples || []).filter((sample) => Array.isArray(sample?.landmarks) && sample.landmarks.length >= 25);
  const measurements = valid.map((sample) => {
    const points = sample.landmarks;
    const shoulders = midpoint(points[11], points[12]);
    const hips = midpoint(points[23], points[24]);
    const shoulderWidth = visible(points[11]) && visible(points[12]) ? distance(points[11], points[12]) : null;
    const leftReach = visible(points[11]) && visible(points[15]) ? distance(points[11], points[15]) : null;
    const rightReach = visible(points[12]) && visible(points[16]) ? distance(points[12], points[16]) : null;
    const torsoLength = shoulders && hips ? distance(shoulders, hips) : null;
    return { shoulderWidth, leftReach, rightReach, torsoLength };
  });
  const profile = {
    sampleCount: valid.length,
    capturedActions: [...new Set(valid.map((sample) => sample.action).filter(Boolean))],
    shoulderWidthNorm: median(measurements.map((item) => item.shoulderWidth)),
    leftReachNorm: median(measurements.map((item) => item.leftReach)),
    rightReachNorm: median(measurements.map((item) => item.rightReach)),
    torsoLengthNorm: median(measurements.map((item) => item.torsoLength)),
    source: 'local-mediapipe-landmarks',
    units: 'normalized-image-coordinates',
    updatedAt: new Date().toISOString()
  };
  return profile;
}
