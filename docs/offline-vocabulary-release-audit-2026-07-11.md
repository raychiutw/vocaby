# Offline Vocabulary Release Audit — 2026-07-11

Status: pending physical offline QA and human Taiwan Traditional Chinese release review.

This audit maps the approved offline vocabulary design to current evidence. It
does not treat an Agent reviewer or a green simulator build as human sign-off.

## Automated evidence

| Requirement | Evidence | Result |
|---|---|---|
| At least 5,000 reviewed entries with traceability | `python3 tools/vocabulary_sources.py audit-reviewed --input Content/Reviews/vocabulary-rich-2026-07-11.jsonl` | 5,221 approved: 980 basic, 1,630 intermediate, 2,611 advanced. |
| Rejected slots are explicit | `docs/vocabulary-rejections-2026-07-11.md` | 219 slots rejected for missing verified or composable pronunciation. |
| Source integrity and rights boundary | `python3 tools/vocabulary_sources.py verify` | 14 source snapshots verified. |
| Reproducible canonical candidates | Two `import-all` runs to `/tmp/wording-import-a` and `/tmp/wording-import-b`, then `diff -qr` | 876,093 records per run; no differences. |
| Reproducible shipped resources | Two `build-reviewed` runs plus `cmp` for seed, provenance, and notices; promoted seed compared with the committed seed | All three outputs and the promoted seed match byte-for-byte. |
| One-to-one identity and ordering | Local ID/concept/sort-order assertion over committed seed and provenance | 5,221 unique seed IDs, provenance IDs, and concept keys; order contiguous per level. |
| Rich DTO and app behavior contracts | `xcodebuild clean test -project Vocaby.xcodeproj -scheme Vocaby -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A'` | `TEST SUCCEEDED`. |
| Shipping build | `xcodebuild build -project Vocaby.xcodeproj -scheme Vocaby -configuration Release -destination 'generic/platform=iOS Simulator'` | `BUILD SUCCEEDED`. |
| App resource boundary and static offline surface | Release bundle inspection plus Swift scan for HTTP, Network, CloudKit, authentication, credentials, and translation APIs | Seed and notices exist; raw/import/review/manifest/provenance absent; no matching runtime code. |
| Knowledge graph | Persisted `index_repository`, targeted graph search, and `zstd -t` | 1,605 nodes, 5,058 edges; graph archive valid. |

## Physical-device gate

The Debug QA App was built and installed on Ray's paired iPhone
`77F2E6C0-ECF9-5E25-81E4-5554094C6960`. `devicectl` launch is currently denied
by iOS because the device is locked. No product failure or signing failure was
reported.

After the phone is unlocked and Wi-Fi/cellular data are disabled, record all of
the following before release sign-off:

- all five quiz modes complete without network access;
- listening mode reveals neither expression nor IPA before answering;
- correct and wrong feedback freezes options and shows selected-sense POS,
  English/zh-Hant meanings, full bilingual example, pronunciations, and up to
  two additional senses;
- a deterministic multi-reading entry plays every displayed reading;
- Library detail, Dynamic Type, and VoiceOver pronunciation labels work; and
- human Taiwan Traditional Chinese review is explicitly signed off.

Until these observations are recorded, the release audit remains pending.
