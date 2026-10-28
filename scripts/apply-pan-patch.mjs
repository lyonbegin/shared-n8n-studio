#!/usr/bin/env node
import {readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {CANVAS_PAN} from '../packages/pan/pan-contract.mjs';

/** Deterministic and fail-closed patch for upstream n8n@2.44.5/2.44.6 Canvas.vue. */
export function patchCanvas(text) {
  const patches = [
    [
      'const panningMouseButton = ref<number[] | true>(isMobileDevice ? true : [1]);',
      'const panningMouseButton = ref<number[] | true>(isMobileDevice ? true : [' + CANVAS_PAN.panButtons.join(', ') + ']);',
    ],
    [
      "const selectionKeyCode = ref<string | true | null>(isMobileDevice ? 'Shift' : true);",
      "const selectionKeyCode = ref<string | true | null>('" + CANVAS_PAN.marqueeModifier + "');",
    ],
    [
      '\tselectionKeyCode.value = true;\n\tpanningMouseButton.value = [1];\n\tisInPanningMode.value = false;',
      "\tselectionKeyCode.value = '" + CANVAS_PAN.marqueeModifier + "';\n\tpanningMouseButton.value = [" + CANVAS_PAN.panButtons.join(', ') + "];\n\tisInPanningMode.value = false;",
    ],
  ];
  let next = text;
  let already = 0;
  for (const [before, after] of patches) {
    const beforeCount = next.split(before).length - 1;
    const afterCount = next.split(after).length - 1;
    if (beforeCount === 1 && afterCount === 0) next = next.replace(before, after);
    else if (beforeCount === 0 && afterCount === 1) already++;
    else throw Error('Unsupported or ambiguous upstream Canvas.vue: ' + before.slice(0, 80));
  }
  for (const fragment of [
    ':pan-on-drag="panningMouseButton"',
    ':selection-key-code="selectionKeyCode"',
    ':pan-activation-key-code="panningKeyCode"',
    'function switchToPanningMode()',
    'function switchToSelectionMode()',
  ]) {
    if (!next.includes(fragment)) throw Error('Upstream canvas contract missing: ' + fragment);
  }
  return {content: next, status: already === patches.length ? 'already-patched' : 'patched'};
}

if (process.argv[1] && import.meta.url === new URL('file://' + resolve(process.argv[1])).href) {
  const src = process.argv[2];
  const dryRun = process.argv.includes('--check');
  if (!src) {
    console.error('Usage: node scripts/apply-pan-patch.mjs <upstream Canvas.vue> [--check]');
    process.exitCode = 2;
  } else {
    try {
      const old = await readFile(src, 'utf8');
      const {content, status} = patchCanvas(old);
      if (!dryRun && content !== old) await writeFile(src, content, 'utf8');
      console.log('PAN_PATCH_' + (dryRun ? 'CHECK_' : '') + status.toUpperCase().replace('-', '_') + ': ' + src);
    } catch (error) {
      console.error('PAN_PATCH_FAILED: ' + error.message);
      process.exitCode = 1;
    }
  }
}
