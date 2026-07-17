# Vocabulary 100,000 Progress

## Current baseline — 2026-07-18

- Branch: `feat/all-approved-vocabulary`
- Approved source entries: 16
- Frozen shipping lessons: 14,064
- Reviewed checkpoint rows: 1,800
- Unique lessons including the frozen seed: 15,403 / 100,000 (15.403%)
- Review cadence: 10 lessons per batch; audit, commit, and push after every 20 batches
- Selection priority: common everyday, business, travel, practical-life, general, then specialized

Checkpoint rows that already exist in the frozen seed are not double-counted in
the unique total.

| Frozen artifact | SHA-256 |
| --- | --- |
| `Vocaby/Resources/VocabularySeed.json` | `0fad7a08386e7b9448448ce8dc2144dd6571d0614594a9c049d0e1147bb541d9` |
| `Content/VocabularyProvenance.json` | `eacf3d158eec48fab86f437e74975f3feff55145427201d8a3d8bfc7aa45188f` |
| `Vocaby/Resources/ThirdPartyNotices.txt` | `3f152459c424d7451fc08c3ea65f17e7d368d335bd78a93afda2307408e55d5c` |
| `Content/Sources/source-manifest.json` | `6b31b1c9d0790dbe7335f43b8bd768f780d2d6211fd91d7fdb14ac10e7500ec3` |

The shipping seed, provenance, and notices remain frozen until the complete
100,000-item review index passes deterministic build and promotion gates.

## Reviewed checkpoint ledger

| Checkpoint | Batches | Rows | Cumulative reviewed | Unique with seed | Senses | Pronunciations | Multi-sense | CEFR | SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 0001 | 20 | 200 | 200 | 14,064 | 200 | 585 | 0 | A1 105, A2 94, B1 1 | `c855a0bdd53a2c86f7d189c107df24ecef9d10c04a7aa398e76a99e356a933ff` |
| 0002 | 40 | 200 | 400 | 14,064 | 200 | 589 | 0 | A1 84, A2 116 | `e0c81d400716a44dfce60d311a14ad583249ff32a7a3941020c716ffb5b2332c` |
| 0003 | 60 | 200 | 600 | 14,203 | 201 | 433 | 1 | A1 86, A2 109, B1 2, B2 3 | `ca2276b5a10ceeec1730006fa40bcb7efe9f48a044363551228c92e129c2838e` |
| 0004 | 80 | 200 | 800 | 14,403 | 200 | 331 | 0 | A1 21, A2 82, B1 92, B2 5 | `b79908a09bd144d0a897b0c685ee8c589c67f03c3fbc9c926fd5e7406c0b5f9c` |
| 0005 | 100 | 200 | 1,000 | 14,603 | 200 | 326 | 0 | A1 8, A2 21, B1 146, B2 22, C1 3 | `695e06878815bbdfdfbbc250e1b52c3bd99d6f43dd0466fa887a48a19af583f6` |
| 0006 | 120 | 200 | 1,200 | 14,803 | 200 | 357 | 0 | A1 11, A2 90, B1 67, B2 32 | `6e8536004c7ef7674f9b074ec98f5786ffe64d74f55e86f46c71273a67b2a0a3` |
| 0007 | 140 | 200 | 1,400 | 15,003 | 200 | 331 | 0 | B1 19, B2 177, C1 4 | `9c264f5337f7b8b912148187a07a669e93245a5510e8497d0a4a2b121c616047` |
| 0008 | 160 | 200 | 1,600 | 15,203 | 200 | 329 | 0 | B2 200 | `007c12716970f03c266a23a4663e21f257610c6275d5e61ef0ed3e614405a7c4` |
| 0009 | 180 | 200 | 1,800 | 15,403 | 200 | 252 | 0 | B2 200 | `66c4517621efc782c4555a26be5e25d00359ae5cfdde3505058f94ec5eece52d` |

Every listed shard has 200 approved rows, zero known placeholders, zero ID or
normalized-expression collisions against earlier content, and a matching entry
in `Content/Reviews/vocabulary-100k/index.json`.
