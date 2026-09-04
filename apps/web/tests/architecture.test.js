import { describe, it } from 'node:test';
import assert from 'node:assert';
import { SCENARIOS, ARCHITECTURE_STAGES } from '../src/lib/architecture-data';

describe('Architecture Rules & Constraints', () => {

  it('Quick Demo is correctly labeled as DEMO · SYNTHETIC', () => {
    const demo = SCENARIOS.find(s => s.id === 'synthetic');
    assert.ok(demo, 'Synthetic scenario exists');
    
    // Verify all active stages in demo are strictly from the synthetic lane
    for (const stageId of demo.activeStageIds) {
      const stage = ARCHITECTURE_STAGES.find(s => s.id === stageId);
      assert.strictEqual(stage?.lane, 'synthetic', `Stage ${stageId} must be in synthetic lane`);
    }
  });

  it('Sealed replay is correctly labeled as SEALED · SIMULATED', () => {
    const replay = SCENARIOS.find(s => s.id === 'sequential');
    assert.ok(replay, 'Sequential scenario exists');
    
    // Verify all active stages in replay are from simulated lane (except human/stop boundaries)
    for (const stageId of replay.activeStageIds) {
      const stage = ARCHITECTURE_STAGES.find(s => s.id === stageId);
      assert.ok(['simulated'].includes(stage?.lane || ''), `Stage ${stageId} should be simulated`);
    }
  });

  it('Provider Test Mode flow does NOT falsely require a Model V2 decision', () => {
    const providerSuccess = SCENARIOS.find(s => s.id === 'provider-success');
    assert.ok(providerSuccess, 'Provider success exists');
    
    assert.ok(!providerSuccess.activeStageIds.includes('sim-model'), 'Model V2 should not be in provider test mode path');
    assert.ok(providerSuccess.activeStageIds.includes('test-operator'), 'Must start with operator initiation');
  });

  it('Retryable failed attempt ends AWAITING RETRY, not terminal FAILED', () => {
    const retryable = SCENARIOS.find(s => s.id === 'retryable');
    assert.ok(retryable, 'Retryable scenario exists');
    
    assert.strictEqual(retryable.finalOutcome, 'EXECUTING / AWAITING RETRY');
    assert.ok(retryable.activeStageIds.includes('exc-awaiting'), 'Must include the awaiting retry boundary');
  });

  it('Provider mismatch ends FAIL CLOSED', () => {
    const truthNode = ARCHITECTURE_STAGES.find(s => s.id === 'test-truth');
    assert.ok(truthNode?.whatHappens.includes('FAIL CLOSED'), 'Provider truth must assert fail closed on mismatch');
  });

  it('Human Review path works', () => {
    const human = SCENARIOS.find(s => s.id === 'human');
    assert.ok(human, 'Human scenario exists');
    assert.strictEqual(human.finalOutcome, 'HUMAN REVIEW');
    assert.ok(human.activeStageIds.includes('exc-human'));
  });

  it('Bounded Stop path works', () => {
    const stop = SCENARIOS.find(s => s.id === 'bounded-stop');
    assert.ok(stop, 'Bounded stop scenario exists');
    assert.strictEqual(stop.finalOutcome, 'STOP');
    assert.ok(stop.activeStageIds.includes('exc-stop'));
  });

});
