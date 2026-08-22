# Validation Degradation Detection Report

Detector version: `1.0.0`
Configuration hash: `886c9eb4c45b7b3a2f88b30ff3d6b0356190a039135d989ee65497504e48fbcb`

## Episode metrics

- Hidden incidents: 180
- Eligible incidents: 53
- All incident recall: 4.44%
- Eligible incident recall: 13.21%
- Predicted incident precision: 2.85%
- False issuer incidents: 273
- False incidents per scope-day: 0.014123
- Mean detection delay: 692.35 minutes
- Median detection delay: 547.58 minutes
- P90 detection delay: 952.59 minutes

## Baseline comparison

- RELATIVE_DROP: eligible recall 24.53%; precision 1.00%; false incidents per scope-day 0.087067.
- STATIC_THRESHOLD: eligible recall 24.53%; precision 1.03%; false incidents per scope-day 0.094620.

## Diagnostics and performance

- False-positive causes: {'baseline_instability': 9, 'random_fluctuation': 236, 'sparse_sample': 28}
- Recall by hidden severity: {'CRITICAL': {'detected': 4, 'incidents': 10, 'recall': 0.4}, 'MILD': {'detected': 0, 'incidents': 79, 'recall': 0.0}, 'MODERATE': {'detected': 2, 'incidents': 63, 'recall': 0.031746031746031744}, 'SEVERE': {'detected': 2, 'incidents': 28, 'recall': 0.07142857142857142}}
- Recall by traffic volume: {'0-2': {'detected': 0, 'incidents': 96, 'recall': 0.0}, '10+': {'detected': 7, 'incidents': 24, 'recall': 0.2916666666666667}, '3-4': {'detected': 1, 'incidents': 29, 'recall': 0.034482758620689655}, '5-9': {'detected': 0, 'incidents': 31, 'recall': 0.0}}
- Dominant failure shift: {'detected_incidents': 8, 'incidents_with_supported_shift': 5, 'support_coverage': 0.625, 'top_reason_accuracy_when_supported': 0.4}
- Throughput: 7349.33 events/second
- Mean update latency: 0.1361 ms

All values are simulator evaluation evidence. Hidden incident truth was joined only after observable replay completed.
