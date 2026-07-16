# Vocabulary pronunciation supplement

## Source expansion

- Target set: 15,334 expressions (13,336 current App items plus 1,998 pronunciation rejections).
- Source: the existing approved Wiktextract snapshot source, enwiktionary dump `2026-07-06`, extracted `2026-07-09`.
- Expanded snapshot: 31,535 records, 68,464,902 bytes, SHA-256 `2dcc15087cccb540435453c1cde8ff9ca1e9a9da009c0c90e2905dd2dc9d4d50`.
- Deterministic canonical import: 31,535 records, SHA-256 `bf7ed3c0391bac1249e26c7e6897ca20e6685c50b67243bd7e4b28b07a8f44e4`.
- Rebuilt all-available queue: 15,336 candidates. The shared pronunciation/sense gate accepts 728 new candidates, rejects `optionally` and `rock'n'roll`, and retains 1,269 earlier candidates without usable IPA.
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
