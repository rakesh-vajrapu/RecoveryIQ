# Policy V1 Development Personalization Audit

Decisions: 27635
Best global ERV action: `OFFER_ALTERNATE_METHOD`
Best global probability action: `OFFER_ALTERNATE_METHOD`
Model top-action dominance: 0.263687

Model top-1 oracle-probability agreement: 0.685290
Model top-2 oracle-probability coverage: 0.831916
Model pairwise ranking accuracy: 0.883612

## Development ERV-regret comparison

- `model_v1_top_probability`: mean oracle ERV 109681.35; mean regret 9946.11; top-1 0.683047
- `no_health_top_probability`: mean oracle ERV 110568.82; mean regret 9058.63; top-1 0.688764
- `best_global_action`: mean oracle ERV 76350.88; mean regret 43276.57; top-1 0.032314
- `failure_reason_rule`: mean oracle ERV 107204.69; mean regret 12422.77; top-1 0.567505
- `failure_reason_method_rule`: mean oracle ERV 105678.42; mean regret 13949.04; top-1 0.524046

Conclusion: **DEVELOPMENT_SUGGESTS_CONTEXT_VALUE; VALIDATION_REQUIRED**

Hidden oracle values were used only in the development evaluation layer.
No RecoverIQ policy configuration or validation result exists yet.
