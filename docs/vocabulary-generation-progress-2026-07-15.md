# Vocabulary Generation Progress — 2026-07-15

Audit timestamp: `2026-07-15T23:44:06+08:00`

Status: **REJECTED / NOT PROMOTABLE**

This ledger audits the ignored enrichment checkpoint at exact 20-batch boundaries. It records only derived evidence; no raw model output, imported source data, or review work directory is tracked.

## Prefix Audit

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 20 | `0000`–`0019` | 398 | 400 | PASS | FAIL | FAIL | 5 | 305 | `f553fd8db0c1153edd46d0a81352df0043644e66aca5f07cb401f5df7f42d04f` | FAIL |
| 40 | `0000`–`0039` | 797 | 800 | PASS | FAIL | FAIL | 9 | 560 | `a602aae9636bd1a7166223109919cfe0a852256092ab92078a62d66629cbcfd1` | FAIL |
| 60 | `0000`–`0059` | 1,192 | 1,200 | PASS | FAIL | FAIL | 17 | 783 | `535a0fb90697686ceedfd7a110295ba661c4d4b57d6490b3f5425cb3bd22d8f8` | FAIL |
| 80 | `0000`–`0079` | 1,590 | 1,600 | PASS | FAIL | FAIL | 27 | 1,010 | `4c0e90f08ef600d0efb83b9f84cbf5e74471f67facc6bb5d97d08b5bf7c5b9e6` | FAIL |
| 100 | `0000`–`0099` | 1,984 | 2,000 | PASS | FAIL | FAIL | 37 | 1,236 | `ed710299c57f3f77d654b94e29cb4b020741937b8973e856ec206013cc7440df` | FAIL |

Canonical hashes use sorted-key, compact UTF-8 JSONL for the exact prefix in ascending batch-ID order.

## First Failures

First item-ID mismatch, batch `0000`:

- Expected: `bank-basic-0013::bank-basic-0013-sense-1`
- Actual: `bank-basic-0013::action#n#14554805-n`

First validator failure, batch `0000`:

- Item: `bank-basic-0001::bank-basic-0001-sense-1`
- Error: `enrichment bank-basic-0001::bank-basic-0001-sense-1 has invalid plain expression`

## Decision

The checkpoint predates exact chunk-output enforcement. Although all batch IDs are consecutive and unique, output item identity and content validation fail at every audited boundary. None of these prefixes may be treated as reviewed, committed as vocabulary content, used for deterministic builds, or promoted.

Processing remains stopped. Regeneration must preserve the ignored input/work root, replace rejected model output only through the hardened checkpointed pipeline, and produce a PASS audit before the next progress commit.

## Regeneration — Boundary 20

Audit timestamp: `2026-07-16T00:12:00+08:00`

Current regeneration status: **PASS THROUGH BATCH `0019` / FULL BANK INCOMPLETE**

The historical FAIL evidence above remains the record for the rejected 100-batch checkpoint. After the hardened trust boundary and bounded singleton retry were committed, regeneration restarted from an empty active output and stopped cleanly after exactly 20 pending outer batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 20 | `0000`–`0019` | 400 | 400 | PASS | PASS | PASS | 0 | 0 | `b9ce605a3a876951b7737b264e67fc7d5e6be26bb07c4c7435ad8e06e6039302` | PASS |

Regeneration evidence:

- Enrichment command result: `{"batches": 667, "completed": 20, "processed": 20}`.
- Active output contains exactly 20 JSONL records and the batch IDs are exactly `0000` through `0019` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 400 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order, matching the historical audit method.
- Finish-enrichment and translation artifacts remain absent; this checkpoint is enrichment-only and is not yet promotable as a full vocabulary bank.
- The original rejected 100-batch output remains archived with SHA-256 `ed710299c57f3f77d654b94e29cb4b020741937b8973e856ec206013cc7440df`.
- The interrupted seven-batch regeneration attempt remains archived with SHA-256 `1ad09fbee97ca84b492e28cd022e52820629dd9be2f8f57f6bc136f323eb0898`.

## Regeneration — Boundary 40

Audit timestamp: `2026-07-16T00:26:14+08:00`

Current regeneration status: **PASS THROUGH BATCH `0039` / FULL BANK INCOMPLETE**

The validated boundary-20 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 40 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 40 | `0000`–`0039` | 800 | 800 | PASS | PASS | PASS | 0 | 0 | `23aae51d863f12c43cb6ab8be72dc5bc854fd8ab19e49b14756a7b4ef48ab047` | PASS |

Boundary-40 evidence:

- Enrichment command result: `{"batches": 667, "completed": 40, "processed": 20}`.
- Active output contains exactly 40 JSONL records and the batch IDs are exactly `0000` through `0039` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 800 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 60

Audit timestamp: `2026-07-16T00:52:51+08:00`

Current regeneration status: **PASS THROUGH BATCH `0059` / FULL BANK INCOMPLETE**

The validated boundary-40 prefix was preserved. The first continuation checkpointed batches `0040` through `0048` before Apple Foundation Models stopped on a safety gate for batch `0049`. After the fail-closed deterministic safety fallback was committed, one bounded enrichment-only invocation processed exactly the remaining 11 pending batches and stopped cleanly at 60 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 60 | `0000`–`0059` | 1,200 | 1,200 | PASS | PASS | PASS | 0 | 0 | `eacac0bf0b91704a36c7a346d505ff8d7f3afd855eb42580eb9e62fd4f1c800a` | PASS |

Boundary-60 evidence:

- Resume command result: `{"batches": 667, "completed": 60, "processed": 11}`.
- Active output contains exactly 60 JSONL records and the batch IDs are exactly `0000` through `0059` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 1,200 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- The resumed CLI did not emit branch-level fallback logging. None of batch `0049`'s 20 output items exactly matched its deterministic fallback output, so this ledger does not claim that the fallback branch ran during the successful resume.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 80

Audit timestamp: `2026-07-16T01:05:17+08:00`

Current regeneration status: **PASS THROUGH BATCH `0079` / FULL BANK INCOMPLETE**

The validated boundary-60 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 80 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 80 | `0000`–`0079` | 1,600 | 1,600 | PASS | PASS | PASS | 0 | 0 | `ab6312a7aa3cfac11196f8ab8be3484001e8ee2e3121aba10df26e2d5c118e59` | PASS |

Boundary-80 evidence:

- Enrichment command result: `{"batches": 667, "completed": 80, "processed": 20}`.
- Active output contains exactly 80 JSONL records and the batch IDs are exactly `0000` through `0079` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 1,600 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 100

Audit timestamp: `2026-07-16T01:15:18+08:00`

Current regeneration status: **PASS THROUGH BATCH `0099` / FULL BANK INCOMPLETE**

The validated boundary-80 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 100 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 100 | `0000`–`0099` | 2,000 | 2,000 | PASS | PASS | PASS | 0 | 0 | `02d3f6c165b353677b446570e83a0c45acc018de65a3b092f4e779db888b15e9` | PASS |

Boundary-100 evidence:

- Enrichment command result: `{"batches": 667, "completed": 100, "processed": 20}`.
- Active output contains exactly 100 JSONL records and the batch IDs are exactly `0000` through `0099` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 2,000 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 120

Audit timestamp: `2026-07-16T01:26:53+08:00`

Current regeneration status: **PASS THROUGH BATCH `0119` / FULL BANK INCOMPLETE**

The validated boundary-100 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 120 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 120 | `0000`–`0119` | 2,400 | 2,400 | PASS | PASS | PASS | 0 | 0 | `5fc0e14b5e541207739aab6df737bab3e533329e384982fe6e409b10617af307` | PASS |

Boundary-120 evidence:

- Enrichment command result: `{"batches": 667, "completed": 120, "processed": 20}`.
- Active output contains exactly 120 JSONL records and the batch IDs are exactly `0000` through `0119` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 2,400 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 140

Audit timestamp: `2026-07-16T01:37:19+08:00`

Current regeneration status: **PASS THROUGH BATCH `0139` / FULL BANK INCOMPLETE**

The validated boundary-120 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 140 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 140 | `0000`–`0139` | 2,800 | 2,800 | PASS | PASS | PASS | 0 | 0 | `6218243bb8230286e4eac05bd67c90a293fedbebd20da3b1428edab3cb5a0f49` | PASS |

Boundary-140 evidence:

- Enrichment command result: `{"batches": 667, "completed": 140, "processed": 20}`.
- Active output contains exactly 140 JSONL records and the batch IDs are exactly `0000` through `0139` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 2,800 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 160

Audit timestamp: `2026-07-16T01:46:57+08:00`

Current regeneration status: **PASS THROUGH BATCH `0159` / FULL BANK INCOMPLETE**

The validated boundary-140 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 160 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 160 | `0000`–`0159` | 3,200 | 3,200 | PASS | PASS | PASS | 0 | 0 | `f494e45f84992cd00e8f6b34a6039c3696b923338d908fdb7c7b2b744cbeace4` | PASS |

Boundary-160 evidence:

- Enrichment command result: `{"batches": 667, "completed": 160, "processed": 20}`.
- Active output contains exactly 160 JSONL records and the batch IDs are exactly `0000` through `0159` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 3,200 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 180

Audit timestamp: `2026-07-16T01:58:43+08:00`

Current regeneration status: **PASS THROUGH BATCH `0179` / FULL BANK INCOMPLETE**

The validated boundary-160 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 180 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 180 | `0000`–`0179` | 3,600 | 3,600 | PASS | PASS | PASS | 0 | 0 | `244833441960d1d0f53a1c962765fab904b4e9aff531abcb76b5541615c4c91b` | PASS |

Boundary-180 evidence:

- Enrichment command result: `{"batches": 667, "completed": 180, "processed": 20}`.
- Active output contains exactly 180 JSONL records and the batch IDs are exactly `0000` through `0179` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 3,600 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 200

Audit timestamp: `2026-07-16T02:09:53+08:00`

Current regeneration status: **PASS THROUGH BATCH `0199` / FULL BANK INCOMPLETE**

The validated boundary-180 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 200 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 200 | `0000`–`0199` | 4,000 | 4,000 | PASS | PASS | PASS | 0 | 0 | `8cba4e40081de71849cd23f87ec4890f248583adaac2b9d0599f966b9a5c4a53` | PASS |

Boundary-200 evidence:

- Enrichment command result: `{"batches": 667, "completed": 200, "processed": 20}`.
- Active output contains exactly 200 JSONL records and the batch IDs are exactly `0000` through `0199` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 4,000 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 220

Audit timestamp: `2026-07-16T02:21:14+08:00`

Current regeneration status: **PASS THROUGH BATCH `0219` / FULL BANK INCOMPLETE**

The validated boundary-200 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 220 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 220 | `0000`–`0219` | 4,400 | 4,400 | PASS | PASS | PASS | 0 | 0 | `1a5eaf9da60e3a07e4b1fb7e7b2185ab9cd35eb4f93f465450ae60190649f31b` | PASS |

Boundary-220 evidence:

- Enrichment command result: `{"batches": 667, "completed": 220, "processed": 20}`.
- Active output contains exactly 220 JSONL records and the batch IDs are exactly `0000` through `0219` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 4,400 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 240

Audit timestamp: `2026-07-16T02:30:58+08:00`

Current regeneration status: **PASS THROUGH BATCH `0239` / FULL BANK INCOMPLETE**

The validated boundary-220 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 240 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 240 | `0000`–`0239` | 4,800 | 4,800 | PASS | PASS | PASS | 0 | 0 | `b222b5a14baf1fb7bc7f8fb1142030c0b537e01e3c1fe8bb72a5b01f5258881e` | PASS |

Boundary-240 evidence:

- Enrichment command result: `{"batches": 667, "completed": 240, "processed": 20}`.
- Active output contains exactly 240 JSONL records and the batch IDs are exactly `0000` through `0239` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 4,800 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 260

Audit timestamp: `2026-07-16T02:41:16+08:00`

Current regeneration status: **PASS THROUGH BATCH `0259` / FULL BANK INCOMPLETE**

The validated boundary-240 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 260 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 260 | `0000`–`0259` | 5,200 | 5,200 | PASS | PASS | PASS | 0 | 0 | `d012a860036a144a2ade7e2c3e65e185a5a4652d16d73730eeca34e608864678` | PASS |

Boundary-260 evidence:

- Enrichment command result: `{"batches": 667, "completed": 260, "processed": 20}`.
- Active output contains exactly 260 JSONL records and the batch IDs are exactly `0000` through `0259` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 5,200 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 280

Audit timestamp: `2026-07-16T02:51:31+08:00`

Current regeneration status: **PASS THROUGH BATCH `0279` / FULL BANK INCOMPLETE**

The validated boundary-260 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 280 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 280 | `0000`–`0279` | 5,600 | 5,600 | PASS | PASS | PASS | 0 | 0 | `c8fb09b9c2bc4f2866252cd97bbf7aba91943431ab439a8fbe1946286cb6ce2f` | PASS |

Boundary-280 evidence:

- Enrichment command result: `{"batches": 667, "completed": 280, "processed": 20}`.
- Active output contains exactly 280 JSONL records and the batch IDs are exactly `0000` through `0279` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 5,600 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 300

Audit timestamp: `2026-07-16T03:01:52+08:00`

Current regeneration status: **PASS THROUGH BATCH `0299` / FULL BANK INCOMPLETE**

The validated boundary-280 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 300 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 300 | `0000`–`0299` | 6,000 | 6,000 | PASS | PASS | PASS | 0 | 0 | `7525629c818903b588a30b536047a37ef3daf94afe77700499ceec62cbcf9e02` | PASS |

Boundary-300 evidence:

- Enrichment command result: `{"batches": 667, "completed": 300, "processed": 20}`.
- Active output contains exactly 300 JSONL records and the batch IDs are exactly `0000` through `0299` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 6,000 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- Both rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Rejected Attempt — Boundary 320

Audit timestamp: `2026-07-16T03:14:21+08:00`

Attempt status: **FAIL / REJECTED / NOT PROMOTABLE**

The bounded boundary-320 invocation stopped when Apple Foundation Models failed batch `0310` with `LanguageModelSession.GenerationError error -1`. Unified logging shows the prompt guardrail completed successfully before the model-service XPC connection was interrupted; the underlying errors were `ModelManagerServices.ModelManagerError Code=1041` and `SensitiveContentAnalysisML Code=15`. This is an environmental Apple ModelManager interruption, not the recognized unsafe-content fallback path, so no broad `GenerationError` retry was added.

The concurrent workers checkpointed a sparse set before the failed future surfaced. The ignored active output contains 312 individually valid batches and 6,240 items with IDs `0000` through `0309`, followed by `0311` and `0312`. Batch `0310` and batches `0313` through `0319` are missing. The sparse canonical SHA-256 is `38d6d46ace0611dd4ba0179e990f7109d9bd520245ee203d25b2c924d579d49b`.

The last accepted exact consecutive 20-batch boundary prefix remains boundary 300: 300 batches, 6,000 items, and canonical SHA-256 `7525629c818903b588a30b536047a37ef3daf94afe77700499ceec62cbcf9e02`, matching the boundary-300 ledger entry. All post-boundary-300 output from this failed attempt is rejected until the active output is restored and a fresh boundary-320 audit passes.

No enrichment process remains live. The sparse raw output remains ignored and is not tracked; this ledger records derived failure evidence only. No finish-enrichment or translation artifact was created, and nothing from this attempt may be promoted.

## Regeneration — Boundary 320

Audit timestamp: `2026-07-16T03:27:15+08:00`

Current regeneration status: **PASS THROUGH BATCH `0319` / FULL BANK INCOMPLETE**

After the rejected boundary-320 attempt above was tracked, its sparse ignored output was archived with canonical SHA-256 `38d6d46ace0611dd4ba0179e990f7109d9bd520245ee203d25b2c924d579d49b`. The active output was restored to the validated boundary-300 prefix, whose canonical SHA-256 remained `7525629c818903b588a30b536047a37ef3daf94afe77700499ceec62cbcf9e02`. One bounded enrichment-only recovery invocation then processed exactly 20 pending outer batches and stopped cleanly at 320 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 320 | `0000`–`0319` | 6,400 | 6,400 | PASS | PASS | PASS | 0 | 0 | `0fa3537794a334b81d5be08da42f01acb8fb00fdb582d5323925e3156e8d4d2c` | PASS |

Boundary-320 recovery evidence:

- Enrichment command result: `{"batches": 667, "completed": 320, "processed": 20}`.
- Active output contains exactly 320 JSONL records and the batch IDs are exactly `0000` through `0319` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 6,400 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- All three rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Regeneration — Boundary 340

Audit timestamp: `2026-07-16T03:38:26+08:00`

Current regeneration status: **PASS THROUGH BATCH `0339` / FULL BANK INCOMPLETE**

The recovered and validated boundary-320 prefix was preserved. One bounded enrichment-only invocation processed exactly the next 20 pending outer batches and stopped cleanly at 340 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 340 | `0000`–`0339` | 6,800 | 6,800 | PASS | PASS | PASS | 0 | 0 | `25154d1f48ec730ef20f58996df1d4a93bdb6d66ebd5a81752cd67b7dfec1c86` | PASS |

Boundary-340 evidence:

- Enrichment command result: `{"batches": 667, "completed": 340, "processed": 20}`.
- Active output contains exactly 340 JSONL records and the batch IDs are exactly `0000` through `0339` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 6,800 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- All three rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.

## Rejected Attempt — Boundary 360

Audit timestamp: `2026-07-16T03:47:01+08:00`

Attempt status: **FAIL / REJECTED / NOT PROMOTABLE**

The bounded boundary-360 invocation stopped when batch `0348` exhausted three singleton structural-output attempts. The Apple helper returned parseable output with exit status zero, but the generated singleton item count, order, or ID did not match the immutable input contract. Unified logging contains no model-service, guardrail, or XPC failure for this attempt. The actual invalid response is discarded by the current trust boundary, so this evidence does not claim which singleton field was changed.

The concurrent workers checkpointed a sparse set before the failed future surfaced. The ignored active output contains 347 individually valid batches and 6,940 items with IDs `0000` through `0345`, followed by `0347`. Batch `0346` and batches `0348` through `0359` are missing. The sparse canonical SHA-256 is `b0dcb004edeb0757df7042bad5ab96ccd70139ec71d9f05f6d19d4ded6454156`.

The last accepted exact consecutive 20-batch boundary prefix remains boundary 340, whose canonical SHA-256 is `25154d1f48ec730ef20f58996df1d4a93bdb6d66ebd5a81752cd67b7dfec1c86`, matching the boundary-340 ledger entry. An offline call to the existing `deterministic_input_enrichment` for all 20 batch-`0348` inputs preserved exact IDs and order and produced zero `validate_enrichment` errors; it did not alter the active output.

No enrichment process remains live. The sparse raw output remains ignored and is not tracked; this ledger records derived failure evidence only. No finish-enrichment or translation artifact was created, and nothing from this attempt may be promoted.

## Regeneration — Boundary 360

Audit timestamp: `2026-07-16T04:01:28+08:00`

Current regeneration status: **PASS THROUGH BATCH `0359` / FULL BANK INCOMPLETE**

After the rejected boundary-360 attempt above was tracked, its sparse ignored output was archived with canonical SHA-256 `b0dcb004edeb0757df7042bad5ab96ccd70139ec71d9f05f6d19d4ded6454156`. The active output was restored to the validated boundary-340 prefix, whose canonical SHA-256 remained `25154d1f48ec730ef20f58996df1d4a93bdb6d66ebd5a81752cd67b7dfec1c86`. A strict-TDD trust-boundary change now uses validated deterministic input enrichment only after three invalid singleton structural outputs; it does not retry or convert unrelated helper errors. One bounded enrichment-only recovery invocation then processed exactly 20 pending outer batches and stopped cleanly at 360 completed batches.

| Boundary | Batch prefix | Output items | Expected items | Consecutive unique batch IDs | Input/output item IDs | Schema/content validation | Mismatched batches | Validator errors | Canonical prefix SHA-256 | Result |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| 360 | `0000`–`0359` | 7,200 | 7,200 | PASS | PASS | PASS | 0 | 0 | `e5b9913b2711f47c0c3d12afc3a64272c6b9096723e733e9fcab82772d61b5c5` | PASS |

Boundary-360 recovery evidence:

- Enrichment command result: `{"batches": 667, "completed": 360, "processed": 20}`.
- Active output contains exactly 360 JSONL records and the batch IDs are exactly `0000` through `0359` in order.
- Every output batch has the same item count and item-ID order as its corresponding immutable input batch.
- All 7,200 output items pass `validate_enrichment` against their corresponding input targets.
- Canonical hashing uses sorted-key, compact UTF-8 JSONL in ascending batch-ID order.
- No enrichment process remains live, and finish-enrichment and translation artifacts remain absent.
- All four rejected output archives and all earlier historical FAIL/PASS ledger records remain unchanged.
