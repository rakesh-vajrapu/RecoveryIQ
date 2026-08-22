# Development Degradation Detection Report

Detector version: `1.0.0`
Configuration hash: `886c9eb4c45b7b3a2f88b30ff3d6b0356190a039135d989ee65497504e48fbcb`

## Episode metrics

- Hidden incidents: 180
- Eligible incidents: 66
- All incident recall: 5.56%
- Eligible incident recall: 12.12%
- Predicted incident precision: 2.83%
- False issuer incidents: 343
- False incidents per scope-day: 0.017748
- Mean detection delay: 704.88 minutes
- Median detection delay: 590.10 minutes
- P90 detection delay: 1455.38 minutes

## Baseline comparison

- RELATIVE_DROP: eligible recall 28.79%; precision 1.31%; false incidents per scope-day 0.089670.
- STATIC_THRESHOLD: eligible recall 30.30%; precision 1.39%; false incidents per scope-day 0.102658.

## Diagnostics and performance

- False-positive causes: {'baseline_instability': 17, 'random_fluctuation': 295, 'sparse_sample': 31}
- Recall by hidden severity: {'CRITICAL': {'detected': 1, 'incidents': 8, 'recall': 0.125}, 'MILD': {'detected': 1, 'incidents': 78, 'recall': 0.01282051282051282}, 'MODERATE': {'detected': 4, 'incidents': 58, 'recall': 0.06896551724137931}, 'SEVERE': {'detected': 4, 'incidents': 36, 'recall': 0.1111111111111111}}
- Recall by traffic volume: {'0-2': {'detected': 0, 'incidents': 78, 'recall': 0.0}, '10+': {'detected': 8, 'incidents': 32, 'recall': 0.25}, '3-4': {'detected': 2, 'incidents': 33, 'recall': 0.06060606060606061}, '5-9': {'detected': 0, 'incidents': 37, 'recall': 0.0}}
- Dominant failure shift: {'detected_incidents': 10, 'incidents_with_supported_shift': 10, 'support_coverage': 1.0, 'top_reason_accuracy_when_supported': 0.4}
- Throughput: 7178.03 events/second
- Mean update latency: 0.1393 ms

All values are simulator evaluation evidence. Hidden incident truth was joined only after observable replay completed.
