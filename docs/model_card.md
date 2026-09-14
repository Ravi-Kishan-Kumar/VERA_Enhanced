# VERA model card — release evidence pending

## Intended use

Research/demo analysis of English-language earbud reviews: estimate reported experience,
identify aspect sentiment, communicate uncertainty, and compare products using review evidence.
Scores are model estimates, not verified facts, fraud findings, or a purchasing guarantee.
Do not use for safety-critical decisions, author credibility judgments, or moderation sanctions.

## Data and labeling

Review text, star ratings, and optional product/review metadata come from the project dataset.
The release owner must document source version, license/permission, filtering, deduplication,
sample counts, split membership, and retention policy before publication. Missing metadata uses
the established training-set imputation contract; avoid interpreting missing values as negatives.

LLM-generated labels supply supervision. **Reference annotations are Claude-generated, NOT human
annotations. `human_validated=false`.** Agreement with Claude or another model measures surrogate
consistency, not agreement with an independent human ground truth. Preserve provider/model/prompt
version and annotator provenance with every release. Independent human evaluation remains open.

## Training and inference procedure

The pipeline uses text/metadata signal agents, fine-tuned text models, out-of-fold crossfit signals,
fusion, split-conformal calibration, and product aggregation. Feature extraction must use
`app.ml.pipeline.extract_signals` followed by `app.ml.features.build_feature_vector`; split
separation must prevent leakage into fitting, calibration, and evaluation. Training dependencies
stay out of the production backend. Production uses accepted exported artifacts; quantized
DeBERTa is not eligible unless its export gate passes.

The owner must attach training configuration, seeds, split hashes, artifact manifest/checksums,
export decisions, dependency versions, and the accepted Hub revision. This skeleton does not
certify any active round or existing model.

## Evaluation

| Measure | Result |
| --- | --- |
| Reference labeling agreement / G1 | TBD — reports/agreement_report.json |
| Export fidelity and acceptance / G2 | TBD — reports/experience_export.json |
| CPU inference latency / G3 | TBD — reports/evaluation_report.json |
| Error versus stars-only baseline | TBD — reports/evaluation_report.json |
| Statistical significance and win rate / G4 | TBD — reports/evaluation_report.json |
| Prediction interval coverage and width | TBD — reports/evaluation_report.json |
| Aspect sentiment performance | TBD — reports/evaluation_report.json |
| Evaluation split and slice support | TBD — reports/evaluation_report.json |

Paths are evidence placeholders, not assertions that files exist or contain those fields. Publish
only values actually present in the owner's accepted reports. Do not label surrogate-reference
results as human validation. Report uncertainty, sample support, and failures, not only averages.

## Limitations and ethics

- English earbuds are the supported domain; other languages, products, sarcasm, mixed experiences,
  short text, and distribution shift can degrade results.
- Provider bias, correlated LLM errors, review selection bias, and uncertain metadata can propagate
  into scores. High agreement between models is not proof of correctness.
- Conformal coverage depends on evaluation assumptions and exchangeability; a nominal interval
  is not a guarantee for an individual review or a shifted product population.
- Review volume and author selection affect rankings. Small samples and missing aspects should
  remain visible, not presented as confidently negative or positive evidence.
- Public demo submissions are stored; product-linked reviews are publicly readable. Remove personal
  information and use data with appropriate rights. Define deletion/retention and contact procedures
  before opening the service beyond an approved demo.
- Document bias/robustness testing, independent human review, and misuse monitoring before making
  strong claims. A green software test suite does not establish model quality.
