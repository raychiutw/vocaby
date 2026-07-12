# Baseline RED evidence

Before this skill and importer existed, the ten external files were downloaded
and checksummed manually. There was no manifest, no reusable command, no format
adapter registry, no deterministic JSONL, and no mechanical boundary preventing
candidate data from being treated as App content.

The first executable test run failed with:

```text
can't open file 'tools/vocabulary_sources.py': [Errno 2] No such file or directory
```

The user correction that exposed the process failure was: "利用一個個外部來源檔建立匯入詞庫的過程skill 與 重複執行程式".

The GREEN condition is one documented command path for every source, checksum
and license evidence validation before parsing, deterministic output, explicit
promotion gates, and proof that source folders are not in the Xcode project.

Before the 2026-07-11 update, the skill stopped each source at candidate JSONL
and described translation, example, and question work as out of scope. It did
not require `prepare-enrichment`, `build-reviewed`, generated notices, or a
single post-adapter path. That old behavior fails the two-format eval because an
agent could add separate source-specific enrichment branches or ask the user to
supply already reviewed artifacts.

Before the rich-review update on 2026-07-11, eval 5 also failed 10 of 11 static
expectations. The old skill mentioned OEWN but did not define target-only
Wiktextract snapshotting, structured `pronunciations` and `senses`, CMUdict
comment stripping, the three-sense limit, per-sense pronunciation IDs,
quotation/audio and usage-note exclusions, `audit-reviewed`, or review JSONL
Xcode exclusion. This is the RED baseline for the current skill revision.
