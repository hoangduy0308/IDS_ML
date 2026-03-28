# Spike Findings — ids_ml_new-ziz

## Question

Can v1 accept a limited, explicit set of upstream field-name aliases while still guaranteeing that missing required model features are never silently invented, default-filled, or passed through as valid?

## Result

YES

## Findings

- A strict alias layer is feasible with the current repo constraints because canonicalization can happen before validation using a small explicit rename map.
- The alias layer must be limited to one-to-one field-name normalization only.
- Missing canonical features remain missing after renaming and must stay on the quarantine path.
- Alias collisions must be treated as invalid input and quarantined.
- The alias layer must not compute derived features, inject defaults, or infer absent model values.

## Operational Constraints

- The canonical contract stays anchored to `artifacts/final_model/catboost_full_data_v1/feature_columns.json`.
- Supported aliases must be versioned and explicit in code, not heuristic.
- Validation still runs against the full canonical `72` feature names after alias normalization.
- Any record that cannot produce the complete required canonical feature set is not scored by the model.

## Why This Is Sufficient

An inline proof with a small alias map showed that simple renaming can normalize upstream field names without inventing missing features. This preserves strict schema enforcement and keeps the evasion boundary visible.
