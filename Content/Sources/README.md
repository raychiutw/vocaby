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
python3 tools/vocabulary_sources.py prepare-enrichment \
  --input-dir Content/Sources/Imported \
  --existing-seed Content/Baselines/legacy-90.json \
  --current-seed Vocaby/Resources/VocabularySeed.json \
  --output /tmp/vocabulary-rich-review-queue.jsonl
python3 tools/review_vocabulary.py prepare \
  --queue /tmp/vocabulary-rich-review-queue.jsonl \
  --cmudict Content/Sources/Imported/cmudict-7479086.jsonl \
  --work-dir /tmp/wording-rich-review --batch-size 20
python3 tools/review_vocabulary.py run-local \
  --work-dir /tmp/wording-rich-review --workers 2
python3 tools/review_vocabulary.py build-reviewed \
  --work-dir /tmp/wording-rich-review \
  --output Content/Reviews/vocabulary-rich-2026-07-15.jsonl \
  --rejection-report docs/vocabulary-rejections-2026-07-15.md
python3 tools/vocabulary_sources.py build-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-15.jsonl \
  --existing-seed Vocaby/Resources/VocabularySeed.json \
  --seed-output /tmp/wording-seed.json \
  --provenance-output /tmp/wording-provenance.json \
  --notices-output /tmp/wording-notices.txt
python3 tools/vocabulary_sources.py promote \
  --reviewed /tmp/wording-seed.json \
  --provenance /tmp/wording-provenance.json \
  --notices /tmp/wording-notices.txt \
  --output /tmp/VocabularySeed.json
python3 -m unittest tools/test_vocabulary_sources.py tools/test_review_vocabulary.py
```

Generated candidate JSONL belongs under `Imported/` and is ignored by Git. It is
research input, not shipping content. An entry can reach
`Vocaby/Resources/VocabularySeed.json` only through `promote`, after a
reviewed seed, provenance, and notices pass every fail-closed gate. A source
marked `reference_only` or `blocked` cannot contribute shipping fields.

The current reviewed bank aligns Chinese Open WordNet senses to Open English
WordNet through the exact Open Multilingual Wordnet ILI map. CEFR-J calibrates
levels, CC-CEDICT supplies secondary gloss-review evidence, and selected Tatoeba
English-Mandarin pairs supply context-aligned example translations. The bundled
notice is generated from every source that actually contributes to the bank.
FreeDict contributes reviewed Chinese dictionary evidence to this release;
reference-only and blocked sources cannot contribute shipping fields.

The maintainer pipeline requires Python 3, `opencc` with `s2twp.json`, and Xcode's
macOS Swift toolchain. `NaturalLanguage` performs local sense matching. The rich
review stage can use the checked-in Apple language helper with an already
installed English-to-Traditional-Chinese Translation language pair. It resumes by
ID and checkpoints each completed 100-segment parallel chunk, or every 200
segments in single-worker mode. Foundation Models support targeted maintainer
corrections but are not required for a deterministic full-bank build. None of
these tools, language services, review files, or source snapshots is linked into
the iOS app. The shipping App remains fully offline.

See `.agents/skills/vocaby-vocabulary-import/SKILL.md` for the repeatable
one-source workflow. Licensing decisions in the manifest are engineering gates,
not legal advice.
