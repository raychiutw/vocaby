# Vocabulary 100,000 Progress

## Frozen baseline — 2026-07-17

- Branch: `feat/all-approved-vocabulary`
- Approved source entries: 15
- Canonical import records: 904,681
- Unique normalized headwords: 583,652
- Shipping rich lessons: 14,064
- Final target: 100,000 fully reviewed lessons
- Review cadence: 10 lessons per batch; audit, commit, and push after every 20 batches
- Selection priority: common everyday, business, travel, practical-life, general, then specialized

| Artifact | SHA-256 |
| --- | --- |
| `Vocaby/Resources/VocabularySeed.json` | `0fad7a08386e7b9448448ce8dc2144dd6571d0614594a9c049d0e1147bb541d9` |
| `Content/VocabularyProvenance.json` | `eacf3d158eec48fab86f437e74975f3feff55145427201d8a3d8bfc7aa45188f` |
| `Vocaby/Resources/ThirdPartyNotices.txt` | `3f152459c424d7451fc08c3ea65f17e7d368d335bd78a93afda2307408e55d5c` |
| `Content/Sources/source-manifest.json` | `033cca5fcd5d199ad34087e62ce21551ba48cbc4d9c1bc989d77e017897126cb` |

The frozen hashes are updated only by an intentional reviewed checkpoint. Raw,
imported, generated, or rejected drafts do not count toward the 100,000 target.

## Source checkpoint — Moby Pronunciator II

- Source ID: `moby-pronunciator-ii-3205`
- Raw records: 177,267
- Explicit malformed-row rejections: 15
- Canonical merged pronunciation records: 175,195
- Deterministic import SHA-256: `b34cf90693711b1144bb5ffd3c8cdc84fba845910e4c53fc25ee916760656afc`
- Updated manifest SHA-256: `91302e0632d29d24f402bc67b7009cf180983a98f73c55e67191cd60616a3261`
- Approved source entries after checkpoint: 16
- Canonical records after checkpoint: 1,079,876
- Unique normalized headwords after checkpoint: 670,996

## Baseline selection repair

- Requested baseline targets: 15,336
- Existing shipping lessons retained: 14,064
- Additional source-aligned candidates with verified pronunciation: 636
- Unpronounceable rare candidates replaced: 636
- Replacement priority: common everyday vocabulary
- Final prepared baseline: 15,336 accepted, 0 missing pronunciations
- Selected senses: 19,718
- Review batches: 1,534 at 10 lessons per batch

The rejected candidates were not assigned guessed IPA. A full Wiktextract probe
confirmed that 635 of the remaining 636 rare candidates still lacked source IPA,
so they were replaced by complete, higher-utility candidates from the approved
source pool.

## Review checkpoint 0001

- Completed batches: 20 / 1,534
- Approved lessons: 200 / 15,336 baseline; 200 / 100,000 final target
- Reviewed senses: 295
- Pronunciations: 586
- Multi-sense lessons: 95
- CEFR: A1 88, A2 111, B1 1
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0001.jsonl`
- Shard SHA-256: `6a26a5e1cac61b8ca3871386e49f1f1f4d395a3a7849cef7b65d71ae1e68675c`

## Review checkpoint 0002

- Completed batches: 40 / 1,534
- Approved lessons: 400 / 15,336 baseline; 400 / 100,000 final target
- Reviewed senses: 323
- Pronunciations: 585
- Multi-sense lessons: 123
- CEFR: A1 87, A2 112, B1 1
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0002.jsonl`
- Shard SHA-256: `214ac9a35c0728d04119030c88131e75cc6f3e459f801df5924bc857ea938765`

## Review checkpoint 0003

- Completed batches: 60 / 1,534
- Approved lessons: 600 / 15,336 baseline; 600 / 100,000 final target
- Reviewed senses: 296
- Pronunciations: 584
- Multi-sense lessons: 96
- CEFR: A1 90, A2 109, B1 1
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0003.jsonl`
- Shard SHA-256: `1929f7d61ae7bbd786d86a0764b03f5544a52d0ad626a7b4ca244312c779272a`

## Review checkpoint 0004

- Completed batches: 80 / 1,534
- Approved lessons: 800 / 15,336 baseline; 800 / 100,000 final target
- Reviewed senses: 300
- Pronunciations: 566
- Multi-sense lessons: 100
- CEFR: A1 104, A2 94, C1 2
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0004.jsonl`
- Shard SHA-256: `fe9476d5b921c092723b520d31356a847219cdc8f82f2a0e2575c21832927262`

## Review checkpoint 0005

- Completed batches: 100 / 1,534
- Approved lessons: 1,000 / 15,336 baseline; 1,000 / 100,000 final target
- Reviewed senses: 312
- Pronunciations: 571
- Multi-sense lessons: 112
- CEFR: A1 96, A2 104
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0005.jsonl`
- Shard SHA-256: `a8ab5ba1bcd40e2c2733239fe36a34d9bbe2b6c5cdb9dcfa4e982d8aee4aed01`

## Review checkpoint 0006

- Completed batches: 120 / 1,534
- Approved lessons: 1,200 / 15,336 baseline; 1,200 / 100,000 final target
- Reviewed senses: 312
- Pronunciations: 573
- Multi-sense lessons: 112
- CEFR: A1 90, A2 109, B2 1
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0006.jsonl`
- Shard SHA-256: `04ea5bf70076b62cbe6b8f4d5dafaff13fa2d7baab30cc4bc7cbde24b52a4e79`

## Review checkpoint 0007

- Completed batches: 140 / 1,534
- Approved lessons: 1,400 / 15,336 baseline; 1,400 / 100,000 final target
- Reviewed senses: 323
- Pronunciations: 557
- Multi-sense lessons: 123
- CEFR: A1 81, A2 118, B1 1
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0007.jsonl`
- Shard SHA-256: `ced23bdcbf87a30847a9c6dc6783da9fddfe72b79729514ed436cdf602bc22dd`

## Review checkpoint 0008

- Completed batches: 160 / 1,534
- Approved lessons: 1,600 / 15,336 baseline; 1,600 / 100,000 final target
- Reviewed senses: 314
- Pronunciations: 569
- Multi-sense lessons: 114
- CEFR: A1 104, A2 96
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0008.jsonl`
- Shard SHA-256: `8a17588a6955229ec8bfdab983c04e6205aad76fe72b3708acae7251632b5701`

## Review checkpoint 0009

- Completed batches: 180 / 1,534
- Approved lessons: 1,800 / 15,336 baseline; 1,800 / 100,000 final target
- Reviewed senses: 292
- Pronunciations: 568
- Multi-sense lessons: 92
- CEFR: A1 74, A2 67, B1 36, B2 23
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0009.jsonl`
- Shard SHA-256: `5fadaee0aedf6f9954acb2e0fd3710f89f62d44bc4f788558bfb6a6e7a98790a`

## Review checkpoint 0010

- Completed batches: 200 / 1,534
- Approved lessons: 2,000 / 15,336 baseline; 2,000 / 100,000 final target
- Reviewed senses: 262
- Pronunciations: 555
- Multi-sense lessons: 62
- CEFR: A2 1, B1 111, B2 88
- Rejections: 0
- Known generic examples: 0
- Examples missing the target expression: 0
- Shard: `Content/Reviews/vocabulary-100k/checkpoint-0010.jsonl`
- Shard SHA-256: `28779dce6c88e73a5b2c10fa62dffcb6489de2984496d727a44605b0634e6895`
