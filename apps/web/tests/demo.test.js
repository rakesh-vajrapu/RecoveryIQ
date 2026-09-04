import fs from 'fs';
import path from 'path';
import test from 'node:test';
import assert from 'node:assert';

test('Quick Recovery Demo explicitly renders DEMO_SYNTHETIC', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/app/demo/page.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes("isDemo ? 'DEMO · SYNTHETIC' : 'SEALED · SIMULATED REPLAY'"), "Must label Quick Demo as DEMO_SYNTHETIC");
});

test('Sealed replay paths use SEALED_SIMULATED_REPLAY', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/app/demo/page.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes("'SEALED · SIMULATED REPLAY'"), "Must have SEALED badge");
});

test('Quick Recovery Demo explicitly documents synthetic mix', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/app/demo/page.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes("Synthetic demo mix: 80% of presentation scenarios resolve on the first intervention."), "Must document PRESENTATION DEMO behavior");
  assert.ok(code.includes("Presentation distribution only — not a sealed benchmark metric."), "Must disclaim benchmark metric");
});

test('Quick Recovery Demo is decoupled from trace fetching', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/app/demo/page.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes(`20 EXACT SCENARIOS`), "Must define EXACT 20 deterministic scenarios");
  assert.ok(code.includes(`const trace = isDemo ? SYNTHETIC_SCENARIOS[quickDemoIndex] : apiTrace;`), "Must decouple Quick Demo from getReplayTrace");
});
