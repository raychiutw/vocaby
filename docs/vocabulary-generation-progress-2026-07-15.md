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
