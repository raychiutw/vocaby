# External vocabulary sources

`Raw/` contains exact upstream snapshots used by maintainers. These files are
tracked for reproducibility but are never added to an Xcode target or read by the
app. `source-manifest.json` records their source, version, license evidence,
checksum, parser, and current app-use decision.

Run from the repository root:

```sh
python3 tools/vocabulary_sources.py verify
python3 tools/vocabulary_sources.py import-source cefr-j-1.6
python3 tools/vocabulary_sources.py import-all
python3 tools/vocabulary_sources.py report
python3 -m unittest tools/test_vocabulary_sources.py
```

Generated candidate JSONL belongs under `Imported/` and is ignored by Git. It is
research input, not shipping content. An entry can reach
`WordingDailyApp/Resources/VocabularySeed.json` only through `promote`, after a
reviewed seed and provenance file pass every fail-closed gate. A source marked
`reference_only` or `blocked` cannot be promoted directly.

See `.agents/skills/wording-daily-vocabulary-import/SKILL.md` for the repeatable
one-source workflow. Licensing decisions in the manifest are engineering gates,
not legal advice.
