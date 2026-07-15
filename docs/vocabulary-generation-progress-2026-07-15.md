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
