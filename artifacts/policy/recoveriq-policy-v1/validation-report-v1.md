# RecoverIQ Policy V1 Validation

Policy config hash: `ddf875ea3406f62236b4a9fe91f9e40c0ad129ee60d6482c4524f64a0ed1e8b5`
Registered seeds: `20270601`-`20270610`
Overall frozen validation gate: **PASS**

## RecoverIQ first-intervention result

- Decisions: 27135
- Recovered: 11653 (0.429445)
- Simulated gross recovered minor: 2422746200
- Simulated net recovery value minor: 2409326450
- Human review: 186
- STOP: 85
- Deterministic policy violations: 0
- Mean oracle ERV regret minor: 7316.758

## Frozen gates

- deterministic_safety: PASS
- fixed_retry_value: PASS
- personalization_value: PASS
- abstention_transparency: PASS

## Strategy summary

- `fixed_retry_first`: recovered=6671, rate=0.245845, net_minor=1379738050, reviews=0, STOP=0
- `generic_reminder_first`: recovered=1653, rate=0.060918, net_minor=336166800, reviews=0, STOP=11129
- `best_global_action`: recovered=9542, rate=0.351649, net_minor=1953624100, reviews=0, STOP=0
- `failure_reason_rule`: recovered=11527, rate=0.424802, net_minor=2394187650, reviews=0, STOP=0
- `failure_reason_method_rule`: recovered=11400, rate=0.420122, net_minor=2368239450, reviews=0, STOP=0
- `model_probability_policy`: recovered=11649, rate=0.429298, net_minor=2409028450, reviews=186, STOP=0
- `recoveriq_erv_policy_v1`: recovered=11653, rate=0.429445, net_minor=2409326450, reviews=186, STOP=85
- `recoveriq_no_health_research`: recovered=11872, rate=0.437516, net_minor=2450967750, reviews=36, STOP=18
- `oracle_erv_upper_bound`: recovered=12604, rate=0.464492, net_minor=2622225100, reviews=0, STOP=675

All values are synthetic simulator evidence. Existing Phase 2 multi-action workflows are retained only in the separate secondary view.
