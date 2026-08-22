# RecoverIQ Sequential Policy V2 One-Time Validation

All values are deterministic synthetic simulator evidence, not production revenue.

| Strategy | Recovery rate | Gross minor | Net minor | Retries | Contacts | Violations |
|---|---:|---:|---:|---:|---:|---:|
| fixed_retry_workflow | 0.4174 | 2572104700 | 2553198950 | 48103 | 0 | 0 |
| reminder_retry_workflow | 0.5309 | 3307089200 | 3278888000 | 38896 | 26037 | 0 |
| simple_sequential_observable_rule | 0.6460 | 4042270400 | 4010663110 | 30819 | 24493 | 0 |
| best_global_sequential | 0.6850 | 4270825600 | 4239971500 | 37154 | 18851 | 0 |
| sequential_probability_policy | 0.7618 | 4754648200 | 4726961640 | 28610 | 20010 | 0 |
| recoveriq_sequential_erv_v2 | 0.7597 | 4747032700 | 4719632070 | 28829 | 19519 | 0 |
| greedy_hidden_oracle | 0.7810 | 4882232200 | 4855411250 | 25543 | 20588 | 0 |

## Preregistered claims

- safety: **PASS**
- recovery: **PASS**
- strong_recovery: **PASS**
- ml_personalization: **PASS**
- friction_efficiency: **PASS**

The overall-final Buildathon seeds were not executed.
Detector V2 remained advisory and absent from primary Model V2.
