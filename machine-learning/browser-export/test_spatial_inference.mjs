import assert from 'node:assert/strict';
import {
  TemporalEvidenceTracker,
  deriveBodyProfile,
  inferSpatialRelations,
  normalizeDetections,
  summarizeObjects
} from '../../src/main/webapp/assets/js/spatial-inference.mjs';

const result = {
  detections: [
    { boundingBox: { originX: 600, originY: 300, width: 200, height: 120 }, categories: [{ categoryName: 'tv', score: 0.91 }] },
    { boundingBox: { originX: 300, originY: 470, width: 380, height: 240 }, categories: [{ categoryName: 'chair', score: 0.86 }] },
    { boundingBox: { originX: 830, originY: 520, width: 80, height: 90 }, categories: [{ categoryName: 'cup', score: 0.77 }] },
    { boundingBox: { originX: 20, originY: 20, width: 90, height: 90 }, categories: [{ categoryName: 'cat', score: 0.99 }] }
  ]
};
const detections = normalizeDetections(result, 1000, 800);
assert.deepEqual(detections.map((item) => item.type), ['screen', 'chair', 'cup']);
assert.match(summarizeObjects(detections), /显示屏/);

const landmarks = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, visibility: 0.95 }));
landmarks[2] = { x: 0.47, y: 0.22, visibility: 0.95 };
landmarks[5] = { x: 0.53, y: 0.22, visibility: 0.95 };
landmarks[11] = { x: 0.42, y: 0.38, visibility: 0.95 };
landmarks[12] = { x: 0.58, y: 0.38, visibility: 0.95 };
landmarks[23] = { x: 0.46, y: 0.63, visibility: 0.95 };
landmarks[24] = { x: 0.54, y: 0.63, visibility: 0.95 };
landmarks[15] = { x: 0.72, y: 0.62, visibility: 0.95 };
landmarks[16] = { x: 0.66, y: 0.61, visibility: 0.95 };

const relations = inferSpatialRelations(landmarks, detections);
assert.equal(relations.some((item) => item.type === 'screen_below_eye'), true);
assert.equal(relations.some((item) => item.type === 'seated_contact'), true);
assert.equal(relations.some((item) => item.objectId === 'cup-2'), true);

const tracker = new TemporalEvidenceTracker();
tracker.update('TLF', 0.8, 1000);
tracker.update('TLF', 0.9, 5000);
tracker.update('TUP', 0.7, 7000);
const snapshot = tracker.snapshot(9000);
assert.equal(snapshot.totals.TLF, 6000);
assert.equal(snapshot.current.label, 'TUP');
assert.equal(snapshot.current.durationMs, 2000);

const bodyProfile = deriveBodyProfile([
  { action: 'natural', landmarks },
  { action: 'reach', landmarks: landmarks.map((point, index) => index === 15 ? { ...point, x: 0.88 } : point) }
]);
assert.equal(bodyProfile.sampleCount, 2);
assert.deepEqual(bodyProfile.capturedActions, ['natural', 'reach']);
assert.equal(bodyProfile.source, 'local-mediapipe-landmarks');

console.log('spatial inference: 11 assertions passed');
