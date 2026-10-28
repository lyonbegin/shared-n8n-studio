import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {patchCanvas} from '../scripts/apply-pan-patch.mjs';
import {CANVAS_PAN} from '../packages/pan/pan-contract.mjs';

const fixture = await readFile(new URL('./fixtures/Canvas.vue', import.meta.url), 'utf8');
test('enables blank pane left/middle Pan while retaining handlers', () => {
  const out = patchCanvas(fixture);
  assert.equal(out.status, 'patched');
  assert.match(out.content, /pan-on-drag="panningMouseButton"/);
  assert.match(out.content, /isMobileDevice \? true : \[0, 1\]/);
  assert.match(out.content, /selectionKeyCode = ref<string \| true \| null>\('Shift'\)/);
  assert.match(out.content, /selectionKeyCode.value = 'Shift';\n\tpanningMouseButton.value = \[0, 1\]/);
  assert.match(out.content, /function switchToPanningMode/);
});
test('patch is idempotent', () => {
  const once = patchCanvas(fixture).content;
  const again = patchCanvas(once);
  assert.equal(again.status, 'already-patched');
  assert.equal(again.content, once);
});
test('rejects unrecognized upstream source rather than overwriting', () => {
  assert.throws(() => patchCanvas(fixture.replace('isMobileDevice ? true : [1]', 'true')), /Unsupported or ambiguous/);
});
test('Pan/selection contract preserves separate node and handle behavior', () => {
  assert.deepEqual(CANVAS_PAN.panButtons, [0, 1]);
  assert.equal(CANVAS_PAN.marqueeModifier, 'Shift');
  assert.equal(CANVAS_PAN.pointerTarget, 'pane');
});
