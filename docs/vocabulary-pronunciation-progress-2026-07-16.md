# Vocabulary pronunciation supplement

## Source expansion

- Target set: 15,334 expressions (13,336 current App items plus 1,998 pronunciation rejections).
- Source: the existing approved Wiktextract snapshot source, enwiktionary dump `2026-07-06`, extracted `2026-07-09`.
- Expanded snapshot: 31,535 records, 68,464,902 bytes, SHA-256 `2dcc15087cccb540435453c1cde8ff9ca1e9a9da009c0c90e2905dd2dc9d4d50`.
- Deterministic canonical import: 31,535 records, SHA-256 `bf7ed3c0391bac1249e26c7e6897ca20e6685c50b67243bd7e4b28b07a8f44e4`.
- Rebuilt all-available queue: 15,336 candidates. The shared pronunciation/sense gate accepts 728 new candidates, rejects `optionally` and `rock'n'roll`, and retains 1,269 earlier candidates plus `sublunary` without usable IPA.
- Supplemental review queue: 728 new candidates plus 3 existing basic-level distractors, 731 accepted drafts, 848 selected senses, 37 enrichment batches.

## Enrichment boundary 20

- Command: `enrich-local --workers 2 --max-batches 20`.
- Result: 20 completed batches, IDs `0000` through `0019`, 400 items.
- Input/output item IDs: PASS.
- Enrichment validator: PASS for all 400 items.
- Error records: 0.
- Output SHA-256: `50508047e624301362e218e1d49986699ee2eda5e0d6f10c0ee0c07287510fa3`.
- No enrichment process remained after the bounded invocation.

## Enrichment boundary 37

- Command: `enrich-local --workers 2 --max-batches 17`, resumed from boundary 20.
- Result: all 37 batches completed, IDs `0000` through `0036`, 731 items; final batch contains 11 items.
- Input/output item IDs: PASS.
- Enrichment validator: PASS for all 731 items.
- Error records: 0.
- Output SHA-256: `420537d3932aa3053db60844170b91a6a6a1772146a3e7cc53fa9b38c960b9f0`.
- No enrichment process remained after completion.

## Translation and review

- Command: `translate-local --workers 2`.
- Result: 1,696 of 1,696 segments translated with exact ID parity, valid Traditional Chinese output, and a matching helper/input fingerprint.
- Translation output SHA-256: `51ea0cc76c5de3abec99620c9bcb2c240a0b3d161654f889710f0f107c2c94e6`.
- Full reviewed bank: 14,064 approved items: basic 1,742, intermediate 3,312, advanced 9,010.
- Added: 728 items with verified pronunciation; every selected item has at least one pronunciation.
- Rejected: 1,272 of 15,336 candidates remain fail-closed as `no-verified-pronunciation`.

## Promotion and verification

- Two independent reviewed builds and promotions are byte-for-byte identical.
- Seed SHA-256: `0fad7a08386e7b9448448ce8dc2144dd6571d0614594a9c049d0e1147bb541d9`.
- Provenance SHA-256: `eacf3d158eec48fab86f437e74975f3feff55145427201d8a3d8bfc7aa45188f`; bank version `2026.07.5` and exact seed/provenance ID parity.
- Notices SHA-256: `3f152459c424d7451fc08c3ea65f17e7d368d335bd78a93afda2307408e55d5c`.
- Python: 109 tests passed; all 15 source snapshots verified.
- Swift: 111 tests passed with 0 failures and 0 skips on iPhone 17 Pro, iOS 26.5 simulator.
- Release simulator build: passed. Its App bundle contains the exact canonical seed and notices and no raw, import, review, report, manifest, provenance, enrichment, or translation artifact.
