import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { classifyPose } from '../../../../../sites/healthverse/dist/posture-inference.mjs';

const root = new URL('.', import.meta.url);
const artifact = JSON.parse(await readFile(new URL('../../../../../sites/healthverse/dist/models/posture-classifiers-v1.json', root), 'utf8'));
const fixture = JSON.parse(await readFile(new URL('test-fixtures/parity-120.json', root), 'utf8'));
let maximumError = 0;

for (const sample of fixture.samples) {
  const actual = classifyPose(artifact, sample.landmarks);
  for (const target of ['upper', 'lower']) {
    assert.equal(actual[target].label, sample[target].label, `${sample.sample_id} ${target} prediction`);
    artifact[target].model.classes.forEach((label, index) => {
      const error = Math.abs(actual[target].probabilities[label] - sample[target].probabilities[index]);
      maximumError = Math.max(maximumError, error);
      assert.ok(error < 1e-5, `${sample.sample_id} ${target}/${label} probability error ${error}`);
    });
  }
}

console.log(JSON.stringify({status: 'passed', samples: fixture.samples.length, maximum_probability_error: maximumError}));
