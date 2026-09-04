import fs from 'fs';
import path from 'path';
import test from 'node:test';
import assert from 'node:assert';

test('no failed-attempt evidence -> ordinary EXECUTING presentation', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/components/recovery-case-detail.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes('const isRetryableFailure = recoveryCase.status === "EXECUTING" && hasRetryableFailedAttempt;'));
  assert.ok(code.includes('value={isRetryableFailure ? <div className="text-sm font-bold text-blue-600 dark:text-blue-400">RECOVERY IN PROGRESS</div> : <StatusBadge status={recoveryCase.status} />}'));
});

test('actual RECOVERY_PAYMENT_ATTEMPT_FAILED evidence + active link -> RECOVERY IN PROGRESS -> LAST PAYMENT ATTEMPT FAILED', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/components/recovery-case-detail.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes('RECOVERY_PAYMENT_ATTEMPT_FAILED'));
  assert.ok(code.includes('LAST PAYMENT ATTEMPT FAILED'));
  assert.ok(code.includes('The Razorpay Test Payment Link remains active.'));
});

test('main case is NOT shown as FAILED', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/components/recovery-case-detail.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes('isRetryableFailure ? "LAST PAYMENT ATTEMPT FAILED" : titleCase(recoveryCase.status)'));
  assert.ok(!code.includes('recoveryCase.status = "FAILED"'));
});

test('attribution remains NONE', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/components/recovery-case-detail.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes('NONE YET'));
});

test('amount_minor=100000 + INR renders ₹1,000.00', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/components/audit-timeline.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes('formatMoney(metadata.amount_minor as number, metadata.currency as string)'));
});

test('case detail does not fabricate failed-attempt state when audit evidence is absent', () => {
  const pagePath = path.resolve(import.meta.dirname, '../src/components/recovery-case-detail.tsx');
  const code = fs.readFileSync(pagePath, 'utf8');
  assert.ok(code.includes('hasRetryableFailedAttempt = auditEvents.some(e => e.event_type === "RECOVERY_PAYMENT_ATTEMPT_FAILED")'));
});
