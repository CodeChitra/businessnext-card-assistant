# Component eval: retrieval

Generated 2026-10-30T09:25:20+00:00 · 28 goldens · corpus `8e7bd5dc614a29ce` · `BAAI/bge-small-en-v1.5` · top_k=5

LLM judge: **openai:gpt-5-2025-08-07**, skipped (--no-llm)

## Gates (`expanded` config): PASS

| Gate | Threshold | Actual | |
|---|---|---|---|
| mean Chunk Recall@k | 0.9 | 1.0 | ✅ |
| mean Reciprocal Rank | 0.7 | 0.9375 | ✅ |
| mean Miss Detection | 1.0 | 1.0 | ✅ |

## Raw question vs. expanded (question + intent rewrite)

| Metric | raw | expanded |
|---|---|---|
| full recall rate | 0.9583 | 1.0 |
| mean Chunk Precision@k | 0.2417 | 0.25 |
| mean Chunk Recall@k | 0.9792 | 1.0 |
| mean Miss Detection | 1.0 | 1.0 |
| mean Reciprocal Rank | 0.8576 | 0.9375 |

## Cases (`expanded`)

| Case | Recall | RR | Prec | Miss ok | Retrieved |
|---|---|---|---|---|---|
| EV-001 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-FEE-007#body`, `POL-OPS-012#body`, `POL-PRD-010#signature-card`, `POL-CRD-001#1`, `POL-SVC-005#body` |
| EV-002 | 1.00 | 1.00 | 0.40 | 1.00 | `POL-CRD-001#3`, `POL-CRD-001#2`, `POL-CRD-001#1`, `POL-CRD-003#5`, `POL-CRD-001#4`, `POL-CON-004#body`, `POL-GOV-009#body` |
| EV-003 | 1.00 | 0.50 | 0.20 | 1.00 | `POL-CRD-001#2`, `POL-CRD-001#1`, `POL-CRD-001#3`, `POL-CRD-003#5`, `POL-CRD-011#body`, `POL-CON-004#body` |
| EV-004 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-CRD-001#3`, `POL-CRD-011#body`, `POL-CRD-001#2`, `POL-CRD-001#1`, `POL-CRD-003#5`, `POL-CON-004#body` |
| EV-005 | 1.00 | 1.00 | 0.40 | 1.00 | `POL-CRD-001#2`, `POL-CRD-003#5`, `POL-CRD-001#3`, `POL-CRD-011#body`, `POL-CRD-001#1`, `POL-CON-004#body` |
| EV-006 | 1.00 | 0.50 | 0.20 | 1.00 | `POL-CRD-001#2`, `POL-CRD-002#body`, `POL-CRD-001#3`, `POL-CRD-011#body`, `POL-CRD-001#1`, `POL-CRD-003#5`, `POL-CON-004#body` |
| EV-007 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-SVC-005#body`, `POL-OPS-012#body`, `POL-CRD-001#4`, `POL-SVC-006#body`, `POL-CRD-001#1`, `POL-GOV-009#body` |
| EV-008 | 1.00 | 1.00 | 0.40 | 1.00 | `POL-PRD-010#classic-card`, `POL-PRD-010#signature-card`, `POL-PRD-010#personal-loan`, `POL-OPS-012#body`, `POL-FEE-007#body` |
| EV-009 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-FEE-007#body`, `POL-OPS-012#body`, `POL-PRD-010#signature-card`, `POL-PRD-010#classic-card`, `POL-SVC-005#body` |
| EV-010 | — | — | — | 1.00 | `POL-FEE-007#body`, `POL-CRD-001#1`, `POL-PRD-010#signature-card`, `POL-PRD-010#classic-card`, `POL-OPS-012#body` |
| EV-011 | 1.00 | 1.00 | 0.40 | 1.00 | `POL-CRD-001#4`, `POL-CRD-001#1`, `POL-GOV-009#body`, `POL-CRD-003#5`, `POL-CON-004#body` |
| EV-012 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-OPS-012#body`, `POL-SVC-006#body`, `POL-SVC-005#body`, `POL-CRD-011#body`, `POL-CRD-001#4`, `POL-GOV-009#body` |
| RG-001 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-FEE-007#body`, `POL-CRD-001#1`, `POL-PRD-010#personal-loan`, `POL-CRD-001#4`, `POL-KYC-008#body`, `POL-GOV-009#body` |
| RG-002 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-FEE-007#body`, `POL-PRD-010#signature-card`, `POL-SVC-005#body`, `POL-PRD-010#classic-card`, `POL-CRD-001#1` |
| RG-003 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-SVC-005#body`, `POL-SVC-006#body`, `POL-CRD-001#3`, `POL-CRD-011#body`, `POL-CRD-001#1`, `POL-CON-004#body` |
| RG-004 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-SVC-006#body`, `POL-FEE-007#body`, `POL-OPS-012#body`, `POL-SVC-005#body`, `POL-PRD-010#classic-card` |
| RG-005 | 1.00 | 0.50 | 0.40 | 1.00 | `POL-OPS-012#body`, `POL-FEE-007#body`, `POL-SVC-006#body`, `POL-SVC-005#body`, `POL-CRD-001#1` |
| RG-006 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-KYC-008#body`, `POL-CRD-001#3`, `POL-SVC-005#body`, `POL-CRD-002#body`, `POL-GOV-009#body`, `POL-CON-004#body`, `POL-CRD-003#5` |
| RG-007 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-FEE-007#body`, `POL-GOV-009#body`, `POL-CRD-003#5`, `POL-CRD-001#4`, `POL-PRD-010#signature-card` |
| RG-008 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-PRD-010#personal-loan`, `POL-FEE-007#body`, `POL-CRD-001#3`, `POL-CRD-001#4`, `POL-CRD-003#5`, `POL-CON-004#body`, `POL-GOV-009#body` |
| RG-009 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-PRD-010#signature-card`, `POL-OPS-012#body`, `POL-FEE-007#body`, `POL-CRD-001#1`, `POL-PRD-010#classic-card` |
| RG-010 | — | — | — | 1.00 | `POL-OPS-012#body`, `POL-PRD-010#signature-card`, `POL-CON-004#body`, `POL-SVC-006#body`, `POL-FEE-007#body` |
| RG-011 | 1.00 | 1.00 | 0.40 | 1.00 | `POL-CRD-011#body`, `POL-CRD-001#3`, `POL-CRD-001#1`, `POL-CRD-001#2`, `POL-PRD-010#personal-loan`, `POL-CON-004#body` |
| RG-012 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-CRD-003#5`, `POL-CRD-002#body`, `POL-GOV-009#body`, `POL-CON-004#body`, `POL-FEE-007#body`, `POL-CRD-001#3` |
| RG-013 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-CON-004#body`, `POL-CRD-001#3`, `POL-CRD-001#4`, `POL-CRD-011#body`, `POL-GOV-009#body` |
| RG-014 | 1.00 | 1.00 | 0.20 | 1.00 | `POL-FEE-007#body`, `POL-PRD-010#signature-card`, `POL-OPS-012#body`, `POL-PRD-010#classic-card`, `POL-SVC-006#body` |
| RG-015 | — | — | — | 1.00 | (miss) |
| RG-016 | — | — | — | 1.00 | (miss) |

## Below threshold (with reasons)

- **EV-003** · Reciprocal Rank = 0.50: first relevant at rank 2 (POL-CRD-001#1)
- **EV-006** · Reciprocal Rank = 0.50: first relevant at rank 2 (POL-CRD-002#body)
- **RG-005** · Reciprocal Rank = 0.50: first relevant at rank 2 (POL-FEE-007#body)

## Reading this report

- Chunk Precision@k is bounded by design (top_k=5, usually 1-2 relevant chunks); it is reported, not gated.
- `uncovered` cases (EV-010, RG-010) have no expected chunks: retrieval cannot detect them (they look in-domain); refusal is enforced at generation by the citation validator.
- `rewrite` strings are hand-written stand-ins for the intent classifier until M2; re-run once the classifier produces them.
