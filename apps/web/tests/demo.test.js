import fs from 'fs';
import path from 'path';
import test from 'node:test';
import assert from 'node:assert';

test('Quick Recovery Demo explicitly renders DEMO_SYNTHETIC', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/app/demo/page.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes("selectedPreset === 'quick-recovery-demo' ? 'DEMO · SYNTHETIC'"), "Must label Quick Demo as DEMO_SYNTHETIC");
});

test('Sealed replay paths use SEALED_SIMULATED_REPLAY', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/app/demo/page.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes("'SEALED · SIMULATED REPLAY'"), "Must have SEALED badge");
});

test('Quick Recovery Demo preserves the exact distribution and explicitly documents it', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/app/demo/page.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes("PRESENTATION DEMO behavior"), "Must document PRESENTATION DEMO behavior");
  assert.ok(code.includes("The 80% first-action demo distribution is not a sealed benchmark metric"), "Must disclaim benchmark metric");
});

test('Sequential recovery and Bounded safety do not mutate traces', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/app/demo/page.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes(`if (selectedPreset === "quick-recovery-demo") {`), "Must isolate mutation to quick-recovery-demo");
  assert.ok(code.includes(`// For preset-sequential-v2, bounded-failure-trace-v2, microscope`), "Must explicitly state that others are unmutated");
  assert.ok(code.includes(`setTrace(data);`), "Must pass unmutated trace for sealed modes");
});
