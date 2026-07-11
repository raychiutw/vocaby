# Rich Offline Vocabulary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revalidate and enrich the complete bundled vocabulary bank so every quiz item has offline pronunciation, part of speech, bilingual meanings and examples, and post-answer explanation without adding any App runtime network or account path.

**Architecture:** Keep every external snapshot and validation operation in the existing maintainer-only Python pipeline. Add a targeted Wiktextract snapshot and structured canonical records, route all sources through one reviewed JSONL contract, then atomically promote the rich seed. The SwiftUI App decodes only the promoted seed, carries the selected sense inside each quiz question, and uses native `AVSpeechSynthesizer` for independent IPA-labeled pronunciation buttons.

**Tech Stack:** Python 3 standard library, existing OpenCC 1.4.0 maintainer tool, existing Swift `NaturalLanguage` helper, Swift 6, SwiftUI, AVFAudio, XCTest, iOS 17+.

## Global Constraints

- The App is fully offline and contains no account, login, API key, backend, sync, HTTP client, or remote question bank.
- External downloads run only from maintainer commands; raw and review files never enter an Xcode target.
- Users cannot add, edit, delete, import, or replace official vocabulary.
- Keep source-specific behavior before canonical JSONL; translation, examples, questions, validation, review, provenance, notices, and promotion remain shared.
- Replace the singular `meaning`, `example`, and `pronunciationText` seed fields with structured `senses` and `pronunciations`; do not keep duplicate stored sources of truth.
- Each item has one primary sense and at most two additional common senses.
- Each shipped sense has a part of speech, English and zh-Hant meaning, English and zh-Hant full-sentence example, and at least one valid pronunciation reference.
- Each pronunciation has bare IPA without slash/bracket delimiters, an English speech locale, an optional region label, and its own playback control.
- Preserve an existing item ID only when the expression and intended sense are unchanged. Never reuse a rejected ID for different content.
- Keep at least 5,000 promoted items; the target remains all 5,440 current slots after invalid entries are replaced.
- Wiktextract audio URLs and audio files are never bundled. Wiktionary quotation examples are validation-only and never copied into App content.
- No new App runtime dependency. Use `AVSpeechSynthesisIPANotationAttribute` and installed system voices.
- Use TDD for parser, validation, quiz, and playback logic. Run `git diff --check` before every commit.

---

## File Map

### Maintainer content pipeline

- `tools/vocabulary_sources.py`: targeted source snapshotting, Wiktextract adapter, structured canonical merge, review validation, build, promotion, and CLI commands.
- `tools/test_vocabulary_sources.py`: adapter, CMUdict cleanup, review-contract, rights, deterministic build, and promotion tests.
- `Content/Sources/source-manifest.json`: exact Wiktextract subset identity, hashes, rights, notice, and app-use decision; CMUdict pronunciation-use decision.
- `Content/Sources/Raw/wiktextract-en/`: tracked target-only raw JSONL subset and official license/source evidence; excluded from Xcode.
- `Content/Reviews/vocabulary-rich-2026-07-11.jsonl`: tracked Agent-reviewed, source-aligned records used to reproduce the App seed.
- `Content/VocabularyProvenance.json`: repository-only field evidence, validation sources, review status, and stable item identity.
- `WordingDailyApp/Resources/VocabularySeed.json`: promoted App-only rich bank.
- `WordingDailyApp/Resources/ThirdPartyNotices.txt`: generated notices for every shipping source.

### Swift App

- `WordingDailyApp/Models/VocabularyModels.swift`: rich seed DTOs and primary-sense lookup.
- `WordingDailyApp/Services/SeedLoader.swift`: sample data and fail-closed rich seed validation.
- `WordingDailyApp/Services/QuizEngine.swift`: quiz questions carry the selected item/sense and support language.
- `WordingDailyApp/Features/Shared/VocabularyEntryContentView.swift`: shared meaning/example/POS/pronunciation presentation and native speech utterance creation.
- `WordingDailyApp/Features/Practice/PracticeView.swift`: listening playback, post-answer explanation, and learn view integration.
- `WordingDailyApp/Features/Library/LibraryView.swift`: rich read-only detail integration.
- `WordingDailyApp/Resources/Localizable.xcstrings`: POS, pronunciation, meaning, example, and additional-sense labels.
- `WordingDailyApp.xcodeproj/project.pbxproj`: add the shared Swift file to formal and QA App targets only.

### Tests and docs

- `WordingDailyAppTests/VocabularySeedValidationTests.swift`: full-bank rich-schema and speech-utterance assertions.
- `WordingDailyAppTests/QuizEngineTests.swift`: selected-sense propagation and answer-feedback data.
- `WordingDailyAppTests/DailySelectionServiceTests.swift`: update rich seed fixture.
- `WordingDailyAppTests/LibraryServiceTests.swift`: update rich seed fixture.
- `WordingDailyAppTests/PersistenceGuardTests.swift`: update rich seed fixture.
- `WordingDailyAppTests/ReviewQueueServiceTests.swift`: update rich seed fixture.
- `WordingDailyAppTests/LocalizationCoverageTests.swift`: require new en/zh-Hant keys.
- `docs/question-bank-sources-and-levels.md`: rich review contract and source restrictions.
- `docs/content-review.md`: pronunciation, POS, multiple-sense, and full-sentence translation checks.
- `.agents/skills/wording-daily-vocabulary-import/SKILL.md`: repeatable Wiktextract and rich-review workflow.

---

### Task 1: Add the targeted Wiktextract snapshot and structured adapter

**Files:**
- Modify: `tools/test_vocabulary_sources.py`
- Modify: `tools/vocabulary_sources.py`
- Modify: `Content/Sources/source-manifest.json`
- Create: `Content/Sources/Raw/wiktextract-en/english-targets-2026-07-09.jsonl.gz`
- Create: `Content/Sources/Raw/wiktextract-en/source-page.html`
- Create: `Content/Sources/Raw/wiktextract-en/Wiktionary-Copyrights.html`

**Interfaces:**
- Produces CLI command `snapshot-wiktextract --source-url URL --seed PATH --output PATH`.
- Produces adapter `wiktextract_jsonl_gz` and parser `parse_wiktextract(path: Path, source_id: str) -> Iterable[dict]`.
- Canonical `pronunciations` contains `{notation, value, speechLocale, region, tags}` objects.
- Canonical `senses` contains `{id, partOfSpeech, glosses, tags, examples, translations}` objects.

- [ ] **Step 1: Write the failing targeted-snapshot and adapter tests**

Add local gzip fixtures so the test never uses the network:

```python
def test_wiktextract_snapshot_keeps_only_seed_targets(self):
    source = self.root / "all.jsonl.gz"
    rows = [
        {"word": "lead", "lang_code": "en", "pos": "noun", "senses": [{"glosses": ["A metal."]}]},
        {"word": "lead", "lang_code": "en", "pos": "verb", "senses": [{"glosses": ["To guide."]}]},
        {"word": "other", "lang_code": "en", "pos": "noun", "senses": [{"glosses": ["Another."]}]},
        {"word": "lead", "lang_code": "fr", "pos": "noun", "senses": [{"glosses": ["French row."]}]},
    ]
    with source.open("wb") as destination, gzip.GzipFile(fileobj=destination, mode="wb", mtime=0) as stream:
        for row in rows:
            stream.write((json.dumps(row) + "\n").encode())
    seed = self.root / "seed.json"
    seed.write_text(json.dumps([{"upgradedExpression": "lead"}]), encoding="utf-8")
    output = self.root / "targets.jsonl.gz"

    metadata = vocabulary_sources.snapshot_wiktextract(source.as_uri(), seed, output)

    with gzip.open(output, "rt", encoding="utf-8") as stream:
        kept = [json.loads(line) for line in stream]
    self.assertEqual([(row["word"], row["pos"]) for row in kept], [("lead", "noun"), ("lead", "verb")])
    self.assertEqual(metadata["sha256"], vocabulary_sources.sha256(output))
    self.assertEqual(metadata["bytes"], output.stat().st_size)

def test_wiktextract_adapter_preserves_pos_senses_and_ipa(self):
    source = self.root / "targets.jsonl.gz"
    row = {
        "word": "lead",
        "lang_code": "en",
        "pos": "verb",
        "sounds": [
            {"ipa": "/liːd/", "tags": ["General-American"]},
            {"ipa": "[lɛd]", "tags": ["UK"]},
        ],
        "senses": [{
            "senseid": ["lead-verb-guide"],
            "glosses": ["To guide or conduct."],
            "tags": ["transitive"],
            "examples": [{"text": "She will lead the meeting.", "type": "example"}],
            "translations": [{"code": "zh", "word": "引導"}],
        }],
    }
    with source.open("wb") as destination, gzip.GzipFile(fileobj=destination, mode="wb", mtime=0) as stream:
        stream.write((json.dumps(row) + "\n").encode())

    record = next(vocabulary_sources.parse_wiktextract(source, "wiktextract-test"))

    self.assertEqual(record["partOfSpeech"], "verb")
    self.assertEqual([item["value"] for item in record["pronunciations"]], ["liːd", "lɛd"])
    self.assertEqual(record["senses"][0]["glosses"], ["To guide or conduct."])
    self.assertEqual(record["senses"][0]["translations"]["zh"], ["引導"])
```

- [ ] **Step 2: Run the focused tests to verify RED**

Run:

```sh
python3 -m unittest \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_wiktextract_snapshot_keeps_only_seed_targets \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_wiktextract_adapter_preserves_pos_senses_and_ipa
```

Expected: FAIL because `snapshot_wiktextract` and `parse_wiktextract` do not exist.

- [ ] **Step 3: Implement deterministic streaming and parsing**

Add the standard-library implementation and register the parser:

```python
import gzip
import urllib.request


def bare_ipa(value: str) -> str:
    return value.strip().removeprefix("/").removesuffix("/").removeprefix("[").removesuffix("]").strip()


def snapshot_wiktextract(source_url: str, seed_path: Path, output: Path) -> dict:
    targets = {
        normalized(item["upgradedExpression"])
        for item in load_json(seed_path, list)
    }
    request = urllib.request.Request(source_url, headers={"User-Agent": "WordingDailyVocabularyBuilder/1.0"})
    kept: list[bytes] = []
    with urllib.request.urlopen(request) as response, gzip.GzipFile(fileobj=response) as source:
        for raw_line in source:
            item = json.loads(raw_line)
            if item.get("lang_code") == "en" and normalized(item.get("word", "")) in targets:
                kept.append(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    kept.sort()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as destination, gzip.GzipFile(fileobj=destination, mode="wb", mtime=0) as compressed:
        compressed.writelines(kept)
    return {"path": str(output), "sha256": sha256(output), "bytes": output.stat().st_size, "records": len(kept)}


def parse_wiktextract(path: Path, source_id: str) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            item = json.loads(line)
            if item.get("lang_code") != "en" or not item.get("word"):
                continue
            record = empty_record(source_id, f"line:{line_number}", item["word"])
            record["partOfSpeech"] = item.get("pos")
            record["pronunciations"] = [
                {
                    "notation": "ipa",
                    "value": bare_ipa(sound["ipa"]),
                    "speechLocale": "en-GB" if "UK" in sound.get("tags", []) else "en-US",
                    "region": next(iter(sound.get("tags", [])), None),
                    "tags": sorted(sound.get("tags", [])),
                }
                for sound in item.get("sounds", [])
                if bare_ipa(sound.get("ipa", ""))
            ]
            record["senses"] = [wiktextract_sense(item["word"], item.get("pos"), sense) for sense in item.get("senses", [])]
            record["definitions"] = [gloss for sense in record["senses"] for gloss in sense["glosses"]]
            yield record


def wiktextract_sense(word: str, part_of_speech: str | None, sense: dict) -> dict:
    glosses = [value.strip() for value in sense.get("glosses", []) if value.strip()]
    identity = next(iter(sense.get("senseid", [])), None)
    if identity is None:
        material = "|".join((normalized(word), part_of_speech or "", glosses[0] if glosses else ""))
        identity = hashlib.sha256(material.encode()).hexdigest()[:16]
    translations: dict[str, list[str]] = {}
    for translation in sense.get("translations", []):
        code = translation.get("code")
        value = translation.get("word")
        if code and value:
            translations.setdefault(code, []).append(value.strip())
    return {
        "id": identity,
        "partOfSpeech": part_of_speech,
        "glosses": glosses,
        "tags": sorted(set(sense.get("tags", []))),
        "examples": sorted(
            example["text"].strip()
            for example in sense.get("examples", [])
            if example.get("type", "example") == "example" and example.get("text", "").strip()
        ),
        "translations": {
            code: sorted(set(values), key=lambda value: (normalized(value), value))
            for code, values in sorted(translations.items())
        },
    }


PARSERS["wiktextract_jsonl_gz"] = parse_wiktextract
```

Add `"senses": []` to `empty_record`. Extend `merge_records` to deduplicate pronunciation and sense dictionaries by stable `json.dumps(value, sort_keys=True, ensure_ascii=False)` keys, then sort the merged dictionaries by ID/value. This keeps every adapter on the same canonical merge path.

- [ ] **Step 4: Fix CMUdict comments before cross-source comparison**

Add a regression test with `WORD W ER1 D # comment`, then change the parser line to:

```python
pronunciation = pronunciation.partition(" #")[0].strip()
if not pronunciation:
    continue
record["pronunciations"] = [{
    "notation": "arpabet",
    "value": pronunciation,
    "speechLocale": "en-US",
    "region": "US",
    "tags": [],
}]
```

Run:

```sh
python3 -m unittest tools.test_vocabulary_sources.VocabularySourcesTests.test_cmudict_adapter_strips_inline_comments
```

Expected: PASS with no `#` text in canonical pronunciation values.

- [ ] **Step 5: Create the tracked target subset and evidence**

Run:

```sh
curl -L https://kaikki.org/dictionary/rawdata.html \
  -o Content/Sources/Raw/wiktextract-en/source-page.html
curl -L https://en.wiktionary.org/wiki/Wiktionary:Copyrights \
  -o Content/Sources/Raw/wiktextract-en/Wiktionary-Copyrights.html
python3 tools/vocabulary_sources.py snapshot-wiktextract \
  --source-url https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz \
  --seed WordingDailyApp/Resources/VocabularySeed.json \
  --output Content/Sources/Raw/wiktextract-en/english-targets-2026-07-09.jsonl.gz
```

Expected: the command prints exact path, SHA-256, byte count, and retained record count. Insert those emitted values into the new manifest entry `wiktextract-en-2026-07-09`. Record enwiktionary dump date `2026-07-06`, extraction date `2026-07-09`, Wiktextract commits `e62056b` and `e7887d5`, license `CC BY-SA 4.0`, repository redistribution `allowed`, and a required attribution/share-alike notice. Restrict the decision to POS, cleaned glosses, translations, and IPA; exclude audio and quotation examples.

- [ ] **Step 6: Verify source integrity, deterministic import, and Xcode exclusion**

Run:

```sh
python3 tools/vocabulary_sources.py verify --source wiktextract-en-2026-07-09
python3 tools/vocabulary_sources.py import-source wiktextract-en-2026-07-09 --output /tmp/wiktextract-a.jsonl
python3 tools/vocabulary_sources.py import-source wiktextract-en-2026-07-09 --output /tmp/wiktextract-b.jsonl
cmp /tmp/wiktextract-a.jsonl /tmp/wiktextract-b.jsonl
! rg -n 'Content/Sources' WordingDailyApp.xcodeproj/project.pbxproj
python3 -m unittest tools/test_vocabulary_sources.py
```

Expected: all commands pass, imports are byte-identical, and the project file contains no source-folder reference.

- [ ] **Step 7: Commit the source and adapter**

```sh
git add tools/vocabulary_sources.py tools/test_vocabulary_sources.py \
  Content/Sources/source-manifest.json Content/Sources/Raw/wiktextract-en
git diff --cached --check
git commit -m "feat: import targeted Wiktextract evidence"
```

---

### Task 2: Make rich review the one shared promotion contract

**Files:**
- Modify: `tools/test_vocabulary_sources.py`
- Modify: `tools/vocabulary_sources.py`
- Create: `Content/Reviews/.gitkeep`

**Interfaces:**
- `prepare-enrichment` adds `--current-seed PATH` and emits one rich review packet per stable item ID.
- `build-reviewed --input PATH` accepts complete reviewed JSONL, not an auto-generated usage-note fallback.
- `audit-reviewed --input PATH` returns nonzero for unresolved, malformed, or source-mismatched records.
- Review records contain final `pronunciations`, `senses`, `primarySenseID`, `quiz`, `sourceRefs`, `validationSourceIDs`, `reviewStatus`, and reviewers.

- [ ] **Step 1: Write failing rich-contract tests**

Use one valid record and mutate one field per assertion:

```python
def rich_review_record(self) -> dict:
    return {
        "id": "bank-basic-0001",
        "level": "basic",
        "sortOrder": 31,
        "contentLanguageCode": "en",
        "supportLanguageCodes": ["zh-Hant"],
        "plainExpression": "guide",
        "upgradedExpression": "lead",
        "primarySenseID": "lead-verb-guide",
        "pronunciations": [{"id": "lead-us-1", "ipa": "liːd", "speechLocale": "en-US", "region": "US"}],
        "senses": [{
            "id": "lead-verb-guide",
            "partOfSpeech": "verb",
            "meaning": {"en": "To guide or conduct.", "zh-Hant": "引導或帶領。"},
            "example": {"text": "She will lead the meeting.", "translation": {"zh-Hant": "她將主持這場會議。"}},
            "pronunciationIDs": ["lead-us-1"],
        }],
        "quiz": {"prompt": {"en": "Which expression means guide?", "zh-Hant": "哪個詞表示引導？"}, "options": ["lead", "leave", "lend", "lean"], "correctOptionIndex": 0},
        "sourceRefs": [{"sourceID": "oewn-2025", "sourceEntryRef": "lead-v-1"}],
        "validationSourceIDs": ["wiktextract-en-2026-07-09", "cmudict-7479086"],
        "reviewStatus": "approved",
        "englishReviewer": "codex-content-review-2026-07-11",
        "zhHantReviewer": "codex-content-review-2026-07-11",
    }

def test_rich_review_rejects_dangling_pronunciation_reference(self):
    item = self.rich_review_record()
    item["senses"][0]["pronunciationIDs"] = ["missing"]
    with self.assertRaisesRegex(vocabulary_sources.SourceError, "unknown pronunciation"):
        vocabulary_sources.validate_reviewed_item(item)

def test_rich_review_rejects_usage_note_instead_of_sentence_translation(self):
    item = self.rich_review_record()
    item["senses"][0]["example"]["translation"]["zh-Hant"] = "例句中的 lead 表示引導。"
    with self.assertRaisesRegex(vocabulary_sources.SourceError, "full-sentence translation"):
        vocabulary_sources.validate_reviewed_item(item)

def test_rich_review_rejects_more_than_three_senses(self):
    item = self.rich_review_record()
    item["senses"] = item["senses"] * 4
    with self.assertRaisesRegex(vocabulary_sources.SourceError, "one to three senses"):
        vocabulary_sources.validate_reviewed_item(item)
```

Also test duplicate sense IDs, duplicate pronunciation IDs, missing IPA, unsupported POS, missing bilingual fields, invalid primary sense, more than eight words in `plainExpression`, ambiguous options, unapproved shipping sources, and reference-only sources inside `sourceRefs`.

- [ ] **Step 2: Run the focused contract tests to verify RED**

Run:

```sh
python3 -m unittest \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_rich_review_rejects_dangling_pronunciation_reference \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_rich_review_rejects_usage_note_instead_of_sentence_translation \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_rich_review_rejects_more_than_three_senses
```

Expected: FAIL because `validate_reviewed_item` does not exist.

- [ ] **Step 3: Implement one fail-closed validator**

Add exact canonical tokens and validation:

```python
PARTS_OF_SPEECH = {
    "noun", "verb", "adjective", "adverb", "preposition",
    "conjunction", "interjection", "pronoun", "determiner", "phrase",
}
USAGE_NOTE_PREFIX = "例句中的"


def validate_reviewed_item(item: dict) -> None:
    validate_seed_item(item)
    if len(item["plainExpression"].split()) > 8:
        raise SourceError(f"seed item {item['id']} plain expression is not concise")
    if item.get("reviewStatus") != "approved" or any(
        not isinstance(item.get(key), str) or not item[key].strip()
        for key in ("englishReviewer", "zhHantReviewer")
    ):
        raise SourceError(f"seed item {item['id']} is not reviewed")
    pronunciations = item.get("pronunciations")
    senses = item.get("senses")
    if not isinstance(pronunciations, list) or not pronunciations:
        raise SourceError(f"seed item {item['id']} requires pronunciations")
    if not isinstance(senses, list) or not 1 <= len(senses) <= 3:
        raise SourceError(f"seed item {item['id']} requires one to three senses")
    pronunciation_ids = [value.get("id") for value in pronunciations]
    if None in pronunciation_ids or len(set(pronunciation_ids)) != len(pronunciation_ids):
        raise SourceError(f"seed item {item['id']} has duplicate pronunciation IDs")
    for pronunciation in pronunciations:
        if not all(isinstance(pronunciation.get(key), str) and pronunciation[key].strip() for key in ("id", "ipa", "speechLocale")):
            raise SourceError(f"seed item {item['id']} has malformed pronunciation")
        if pronunciation["ipa"] != bare_ipa(pronunciation["ipa"]):
            raise SourceError(f"seed item {item['id']} IPA must not contain delimiters")
    sense_ids = [value.get("id") for value in senses]
    if item.get("primarySenseID") not in sense_ids or len(set(sense_ids)) != len(sense_ids):
        raise SourceError(f"seed item {item['id']} has invalid primary sense")
    for sense in senses:
        if sense.get("partOfSpeech") not in PARTS_OF_SPEECH:
            raise SourceError(f"seed item {item['id']} has unsupported part of speech")
        references = sense.get("pronunciationIDs")
        if not references or any(value not in pronunciation_ids for value in references):
            raise SourceError(f"seed item {item['id']} references unknown pronunciation")
        meaning = sense.get("meaning", {})
        example = sense.get("example", {})
        translation = example.get("translation", {})
        texts = (meaning.get("en"), meaning.get("zh-Hant"), example.get("text"), translation.get("zh-Hant"))
        if any(not isinstance(value, str) or not value.strip() for value in texts):
            raise SourceError(f"seed item {item['id']} has incomplete bilingual sense")
        if (
            translation["zh-Hant"].startswith(USAGE_NOTE_PREFIX)
            or re.search(r'[.!?]["’”)]?$', example["text"].strip()) is None
            or re.search(r'[。！？!?]["’”)]?$', translation["zh-Hant"].strip()) is None
        ):
            raise SourceError(f"seed item {item['id']} requires a full-sentence translation")
```

Change `validate_seed_item` required fields to `primarySenseID`, `pronunciations`, `senses`, and `quiz`; remove all singular meaning/example/pronunciation checks.

- [ ] **Step 4: Make preparation preserve stable identity and source evidence**

Add `current_seed_path` to `prepare_enrichment`. Index current items by normalized upgraded expression and carry `id`, `sortOrder`, and the current primary sense into the review packet only when the intended OEWN/ILI sense still matches. For a rejected or changed sense, allocate `f"bank-{level}-{hashlib.sha256(concept_key.encode()).hexdigest()[:12]}"` and leave the retired ID out of the promoted output.

The review packet must include:

```python
packet = {
    "id": stable_id,
    "level": level,
    "sortOrder": sort_order,
    "plainExpression": plain,
    "upgradedExpression": target,
    "candidateSenses": ranked_senses[:3],
    "candidatePronunciations": ranked_pronunciations,
    "sourceRefs": shipping_source_refs,
    "validationSourceIDs": sorted(validation_source_ids),
    "issues": sorted(validation_issues),
}
```

Rank the existing exact OEWN/ILI primary sense first. Rank additional senses by Wiktextract order only after lemma/POS alignment. Exclude obsolete, archaic, proper-name-only, offensive-without-context, form-of-only, malformed, or duplicate normalized glosses.

- [ ] **Step 5: Make `build-reviewed` consume complete review records**

Delete the generated Chinese usage-note fallback and all automatic fabrication of final meaning/example fields. The build loop becomes:

```python
reviewed = read_jsonl(reviewed_path)
for item in reviewed:
    validate_reviewed_item(item)
seed = sorted(
    [{key: item[key] for key in SEED_KEYS} for item in reviewed],
    key=lambda item: (LEVEL_ORDER[item["level"]], item["sortOrder"], item["id"]),
)
provenance_items = [provenance_item_from_review(item) for item in reviewed]
```

Set `SEED_KEYS` to the final Swift DTO keys only. Keep `sourceRefs`, `validationSourceIDs`, issues, reviewers, and review status in provenance, never in the App seed.

- [ ] **Step 6: Add `audit-reviewed` and CLI arguments**

Add:

```python
def audit_reviewed(path: Path) -> dict:
    items = read_jsonl(path)
    for item in items:
        validate_reviewed_item(item)
    counts = {level: sum(item["level"] == level for item in items) for level in LEVEL_ORDER}
    if len(items) < 5_000:
        raise SourceError("reviewed bank must contain at least 5000 items")
    return {"items": len(items), "levels": counts, "approved": sum(item["reviewStatus"] == "approved" for item in items)}
```

Expose `--current-seed` on `prepare-enrichment`, and add `audit-reviewed --input PATH`. Print JSON with sorted keys so CI output is stable.

- [ ] **Step 7: Verify the common pipeline and determinism**

Run:

```sh
python3 -m unittest tools/test_vocabulary_sources.py
python3 tools/vocabulary_sources.py verify
python3 tools/vocabulary_sources.py prepare-enrichment \
  --input-dir Content/Sources/Imported \
  --existing-seed Content/Baselines/legacy-90.json \
  --current-seed WordingDailyApp/Resources/VocabularySeed.json \
  --output /tmp/vocabulary-rich-review-queue.jsonl
```

Expected: all tests pass and the queue contains 5,440 stable review packets or an explicit replacement issue for each rejected slot.

- [ ] **Step 8: Commit the shared review contract**

```sh
git add tools/vocabulary_sources.py tools/test_vocabulary_sources.py Content/Reviews/.gitkeep
git diff --cached --check
git commit -m "feat: validate rich vocabulary reviews"
```

---

### Task 3: Produce and audit the complete Agent-reviewed bank

**Files:**
- Create: `Content/Reviews/vocabulary-rich-2026-07-11.jsonl`
- Modify: `WordingDailyApp/Resources/VocabularySeed.json`
- Modify: `Content/VocabularyProvenance.json`
- Modify: `WordingDailyApp/Resources/ThirdPartyNotices.txt`

**Interfaces:**
- Consumes `/tmp/vocabulary-rich-review-queue.jsonl` from Task 2.
- Produces 5,440 approved review records or at least 5,000 only after every omitted current slot has a documented replacement/rejection.
- Produces `/tmp/VocabularySeed.rich.json`, `/tmp/VocabularyProvenance.rich.json`, and `/tmp/ThirdPartyNotices.rich.txt` for Task 4.

- [ ] **Step 1: Split the deterministic review queue into 100-item batches**

Run:

```sh
rm -rf /tmp/wording-rich-review
mkdir -p /tmp/wording-rich-review/input /tmp/wording-rich-review/output
split -l 100 -d -a 3 /tmp/vocabulary-rich-review-queue.jsonl /tmp/wording-rich-review/input/batch-
```

Expected: 55 input files, with the last containing 40 records.

- [ ] **Step 2: Review every batch with the same Agent contract**

Use this exact batch instruction:

```text
For each JSONL record, preserve id, level, sortOrder, plainExpression, upgradedExpression,
sourceRefs, and validationSourceIDs. Select one primary sense and no more than two common
additional senses from candidateSenses. Reject source conflicts instead of guessing.
For every selected sense provide: stable sense id, canonical POS token, concise natural
English meaning, Taiwan Traditional Chinese meaning for the same sense, one natural English
full-sentence example, a faithful Taiwan Traditional Chinese full-sentence translation, and
the applicable pronunciation IDs. Do not write a usage note. Do not use Mainland wording.
plainExpression must be a natural simpler expression of no more than eight words, not a
dictionary definition. Keep only validated IPA readings, label US/UK when supported, and do
not copy Wiktionary quotations. Generate four unique same-level quiz options with one correct
answer. Set reviewStatus=approved and both reviewer IDs to codex-content-review-2026-07-11.
Output JSONL only, in input order.
```

Run `audit-reviewed` on each output batch immediately. If a repeated issue appears, fix the shared instruction or pipeline rule and regenerate every affected batch; do not patch only the first visible row.

- [ ] **Step 3: Merge and audit the complete reviewed file**

Merge batch files in numeric order into `Content/Reviews/vocabulary-rich-2026-07-11.jsonl`, then run:

```sh
python3 tools/vocabulary_sources.py audit-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-11.jsonl
```

Expected JSON: `items` is 5,440, `approved` is 5,440, and level counts remain 980 basic, 1,630 intermediate, and 2,830 advanced unless a documented replacement changes only an ID, never a quota.

- [ ] **Step 4: Run deterministic build and promotion twice**

Run:

```sh
python3 tools/vocabulary_sources.py build-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-11.jsonl \
  --existing-seed Content/Baselines/legacy-90.json \
  --seed-output /tmp/VocabularySeed.rich-a.json \
  --provenance-output /tmp/VocabularyProvenance.rich-a.json \
  --notices-output /tmp/ThirdPartyNotices.rich-a.txt
python3 tools/vocabulary_sources.py build-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-11.jsonl \
  --existing-seed Content/Baselines/legacy-90.json \
  --seed-output /tmp/VocabularySeed.rich-b.json \
  --provenance-output /tmp/VocabularyProvenance.rich-b.json \
  --notices-output /tmp/ThirdPartyNotices.rich-b.txt
cmp /tmp/VocabularySeed.rich-a.json /tmp/VocabularySeed.rich-b.json
cmp /tmp/VocabularyProvenance.rich-a.json /tmp/VocabularyProvenance.rich-b.json
cmp /tmp/ThirdPartyNotices.rich-a.txt /tmp/ThirdPartyNotices.rich-b.txt
python3 tools/vocabulary_sources.py promote \
  --reviewed /tmp/VocabularySeed.rich-a.json \
  --provenance /tmp/VocabularyProvenance.rich-a.json \
  --notices /tmp/ThirdPartyNotices.rich-a.txt \
  --output /tmp/VocabularySeed.rich.json
```

Expected: all comparisons and promotion pass; `/tmp/VocabularySeed.rich.json` contains exactly the reviewed IDs.

- [ ] **Step 5: Perform deterministic content sampling and release review**

Review the first, middle, last, and seeded-random records from each level plus every record with multiple POS values or multiple pronunciations. Record samples and repeated corrections in `docs/content-review.md`. Present the sample report to Ray Chiu and record human release approval only after explicit confirmation.

- [ ] **Step 6: Leave rich artifacts staged for the Swift schema cutover**

Do not replace the App seed in this task because the current Swift DTO cannot decode it. Keep the three `/tmp/*rich*` artifacts and commit only the reviewed repository input:

```sh
git add Content/Reviews/vocabulary-rich-2026-07-11.jsonl docs/content-review.md
git diff --cached --check
git commit -m "content: review rich offline vocabulary bank"
```

---

### Task 4: Cut over the Swift seed DTO and promote the rich resource atomically

**Files:**
- Modify: `WordingDailyApp/Models/VocabularyModels.swift`
- Modify: `WordingDailyApp/Services/SeedLoader.swift`
- Modify: `WordingDailyAppTests/VocabularySeedValidationTests.swift`
- Modify: `WordingDailyAppTests/QuizEngineTests.swift`
- Modify: `WordingDailyAppTests/DailySelectionServiceTests.swift`
- Modify: `WordingDailyAppTests/LibraryServiceTests.swift`
- Modify: `WordingDailyAppTests/PersistenceGuardTests.swift`
- Modify: `WordingDailyAppTests/ReviewQueueServiceTests.swift`
- Modify: `WordingDailyApp/Resources/VocabularySeed.json`
- Modify: `Content/VocabularyProvenance.json`
- Modify: `WordingDailyApp/Resources/ThirdPartyNotices.txt`

**Interfaces:**
- Produces `VocabularyPronunciation`, `VocabularyPartOfSpeech`, and `VocabularySense`.
- `VocabularySeedItem.primarySense` resolves `primarySenseID` without fallback.
- Removes stored `meaning`, `example`, and `pronunciationText`.

- [ ] **Step 1: Write failing rich DTO and validator tests**

Add assertions:

```swift
func testBundledSeedHasCompleteRichEntries() throws {
    let items = try SeedLoader().loadBundledSeed()
    XCTAssertEqual(items.count, 5_440)
    for item in items {
        XCTAssertFalse(item.pronunciations.isEmpty, item.id)
        XCTAssertTrue((1...3).contains(item.senses.count), item.id)
        XCTAssertEqual(item.primarySense.id, item.primarySenseID, item.id)
        let pronunciationIDs = Set(item.pronunciations.map(\.id))
        XCTAssertTrue(item.senses.allSatisfy { sense in
            !sense.pronunciationIDs.isEmpty
                && Set(sense.pronunciationIDs).isSubset(of: pronunciationIDs)
                && !sense.meaning["en", default: ""].isEmpty
                && !sense.meaning["zh-Hant", default: ""].isEmpty
                && !sense.example.text.isEmpty
                && !sense.example.translation["zh-Hant", default: ""].isEmpty
        }, item.id)
    }
}

func testValidationRejectsUnknownPronunciationReference() throws {
    var item = try XCTUnwrap(SeedLoader.sampleItems.first)
    item.senses[0].pronunciationIDs = ["missing"]
    XCTAssertThrowsError(try SeedValidator.validate([item]))
}
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```sh
xcodebuild test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A' \
  -only-testing:WordingDailyAppTests/VocabularySeedValidationTests
```

Expected: compile failure because the rich DTO properties do not exist.

- [ ] **Step 3: Replace the seed model with rich types**

Use:

```swift
enum VocabularyPartOfSpeech: String, Codable, CaseIterable, Equatable {
    case noun, verb, adjective, adverb, preposition, conjunction
    case interjection, pronoun, determiner, phrase
}

struct VocabularyPronunciation: Codable, Identifiable, Equatable {
    var id: String
    var ipa: String
    var speechLocale: String
    var region: String?
}

struct VocabularySense: Codable, Identifiable, Equatable {
    var id: String
    var partOfSpeech: VocabularyPartOfSpeech
    var meaning: [String: String]
    var example: VocabularyExample
    var pronunciationIDs: [String]
}

struct VocabularySeedItem: Codable, Identifiable, Equatable {
    var id: String
    var level: VocabularyLevel
    var sortOrder: Int
    var contentLanguageCode: String
    var supportLanguageCodes: [String]
    var plainExpression: String
    var upgradedExpression: String
    var primarySenseID: String
    var pronunciations: [VocabularyPronunciation]
    var senses: [VocabularySense]
    var quiz: VocabularyQuiz

    var primarySense: VocabularySense {
        senses.first { $0.id == primarySenseID }!
    }
}
```

The force unwrap is safe only because `SeedLoader` validates before exposing items. Do not add a silent fallback to the wrong sense.

- [ ] **Step 4: Make `SeedValidator` fail closed on rich references**

Validate one to three senses, unique IDs, nonempty bare IPA, English locale prefix, primary sense membership, supported bilingual fields, full sentence translations, and every sense pronunciation reference. Add explicit `SeedValidationError.invalidPrimarySense(String)` and `invalidPronunciationReference(String)` cases.

- [ ] **Step 5: Update sample and test fixtures**

Replace every old fixture's singular fields with:

```swift
primarySenseID: "sample-sense-1",
pronunciations: [
    VocabularyPronunciation(id: "sample-us-1", ipa: "ˈɛksələnt", speechLocale: "en-US", region: "US")
],
senses: [
    VocabularySense(
        id: "sample-sense-1",
        partOfSpeech: .adjective,
        meaning: ["en": "Extremely good.", "zh-Hant": "極好、出色。"],
        example: VocabularyExample(
            text: "Your summary was excellent.",
            translation: ["zh-Hant": "你的摘要寫得很出色。"]
        ),
        pronunciationIDs: ["sample-us-1"]
    )
],
```

In each existing test helper, derive `pronunciationID = "\(id)-pronunciation-1"` and `senseID = "\(id)-sense-1"`; use those exact IDs in `primarySenseID`, `pronunciations`, and `pronunciationIDs`. Preserve the helper's existing expression, meaning, example, level, and quiz values. Use `.phrase` when the fixture's upgraded expression contains a space and `.noun` for its single-word synthetic test value. Do not add a production-only compatibility initializer.

- [ ] **Step 6: Replace resources in the same change**

Run:

```sh
cp /tmp/VocabularySeed.rich.json WordingDailyApp/Resources/VocabularySeed.json
cp /tmp/VocabularyProvenance.rich-a.json Content/VocabularyProvenance.json
cp /tmp/ThirdPartyNotices.rich-a.txt WordingDailyApp/Resources/ThirdPartyNotices.txt
```

This is a bulk generated-resource replacement, not a hand edit. Confirm `VocabularySeed.json` has no singular top-level meaning/example/pronunciation keys.

- [ ] **Step 7: Run full DTO and existing service tests**

Run:

```sh
xcodebuild test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A'
```

Expected: all tests pass with 5,440 rich entries and unchanged persisted item IDs for unchanged senses.

- [ ] **Step 8: Commit the atomic schema and resource cutover**

```sh
git add WordingDailyApp/Models/VocabularyModels.swift \
  WordingDailyApp/Services/SeedLoader.swift WordingDailyAppTests \
  WordingDailyApp/Resources/VocabularySeed.json \
  WordingDailyApp/Resources/ThirdPartyNotices.txt Content/VocabularyProvenance.json
git diff --cached --check
git commit -m "feat: ship rich offline vocabulary entries"
```

---

### Task 5: Carry the selected sense through every quiz question

**Files:**
- Modify: `WordingDailyApp/Services/QuizEngine.swift`
- Modify: `WordingDailyAppTests/QuizEngineTests.swift`

**Interfaces:**
- `QuizQuestion.item` carries the complete immutable seed item for a ten-item run.
- `QuizQuestion.senseID` identifies the question sense.
- `QuizQuestion.supportLanguageCode` selects bilingual feedback.
- `QuizQuestion.itemID` remains a computed persistence key.

- [ ] **Step 1: Write failing sense-propagation tests**

Add:

```swift
func testQuestionCarriesPrimarySenseAndSupportLanguage() throws {
    let item = try XCTUnwrap(SeedLoader.sampleItems.first)
    let question = try XCTUnwrap(QuizEngine().makeQuestions(
        for: [item],
        candidates: SeedLoader.sampleItems,
        mode: .meaningChoice,
        supportLanguageCode: "zh-Hant"
    ).first)

    XCTAssertEqual(question.item, item)
    XCTAssertEqual(question.itemID, item.id)
    XCTAssertEqual(question.senseID, item.primarySenseID)
    XCTAssertEqual(question.selectedSense, item.primarySense)
    XCTAssertEqual(question.supportLanguageCode, "zh-Hant")
}
```

- [ ] **Step 2: Run the focused test to verify RED**

Run:

```sh
xcodebuild test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A' \
  -only-testing:WordingDailyAppTests/QuizEngineTests
```

Expected: compile failure because `item`, `senseID`, and `selectedSense` do not exist.

- [ ] **Step 3: Replace duplicated quiz context with the seed item**

Use:

```swift
struct QuizQuestion: Identifiable, Equatable {
    let id: String
    let item: VocabularySeedItem
    let senseID: String
    let supportLanguageCode: String
    let mode: PracticeMode
    let prompt: String
    let options: [String]
    let correctAnswer: String

    var itemID: String { item.id }
    var selectedSense: VocabularySense { item.senses.first { $0.id == senseID }! }
    var correctOptionIndex: Int? { options.firstIndex(of: correctAnswer) }
}
```

In `makeQuestions`, pass `item`, `item.primarySenseID`, and `supportLanguageCode`. Remove `spokenText`; listening playback reads `question.item.upgradedExpression` and the primary sense pronunciation.

- [ ] **Step 4: Update meaning prompts and distractors to use the selected sense**

Change `localizedMeaning` to:

```swift
private func localizedMeaning(for item: VocabularySeedItem, supportLanguageCode: String) -> String {
    item.primarySense.meaning[supportLanguageCode]
        ?? item.primarySense.meaning["en"]
        ?? ""
}
```

Keep the existing same-level distractor and persistence behavior unchanged.

- [ ] **Step 5: Run QuizEngine and persistence tests**

Run:

```sh
xcodebuild test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A' \
  -only-testing:WordingDailyAppTests/QuizEngineTests \
  -only-testing:WordingDailyAppTests/PersistenceGuardTests
```

Expected: PASS; spelling, retry, timeout, and saved quiz indices remain unchanged.

- [ ] **Step 6: Commit quiz context**

```sh
git add WordingDailyApp/Services/QuizEngine.swift WordingDailyAppTests/QuizEngineTests.swift
git diff --cached --check
git commit -m "feat: preserve sense context in quizzes"
```

---

### Task 6: Add native pronunciation and bilingual post-answer details

**Files:**
- Create: `WordingDailyApp/Features/Shared/VocabularyEntryContentView.swift`
- Modify: `WordingDailyApp/Features/Practice/PracticeView.swift`
- Modify: `WordingDailyApp/Features/Library/LibraryView.swift`
- Modify: `WordingDailyApp/Resources/Localizable.xcstrings`
- Modify: `WordingDailyApp.xcodeproj/project.pbxproj`
- Modify: `WordingDailyAppTests/VocabularySeedValidationTests.swift`
- Modify: `WordingDailyAppTests/LocalizationCoverageTests.swift`

**Interfaces:**
- `PronunciationSpeaker.makeUtterance(expression:pronunciation:availableVoices:)` creates native offline speech.
- `VocabularyEntryContentView(item:senseID:supportLanguageCode:showsAdditionalSenses:synthesizer:)` renders one shared read-only detail surface.

- [ ] **Step 1: Write failing utterance and localization tests**

Add:

```swift
func testPronunciationUtteranceUsesIPAAndRequestedInstalledLocale() {
    let pronunciation = VocabularyPronunciation(
        id: "lead-us-1", ipa: "liːd", speechLocale: "en-US", region: "US"
    )
    let voices = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("en") }
    let utterance = PronunciationSpeaker.makeUtterance(
        expression: "lead",
        pronunciation: pronunciation,
        availableVoices: voices
    )

    XCTAssertEqual(utterance.speechString, "lead")
    XCTAssertTrue(utterance.voice?.language.hasPrefix("en") == true)
    let key = NSAttributedString.Key(AVSpeechSynthesisIPANotationAttribute)
    XCTAssertEqual(utterance.attributedSpeechString.attribute(key, at: 0, effectiveRange: nil) as? String, "liːd")
}
```

Require en and zh-Hant localizations for:

```text
vocabulary.pronunciation
vocabulary.meaning.english
vocabulary.meaning.support
vocabulary.example
vocabulary.additionalSenses
vocabulary.region.general
vocabulary.pos.noun
vocabulary.pos.verb
vocabulary.pos.adjective
vocabulary.pos.adverb
vocabulary.pos.preposition
vocabulary.pos.conjunction
vocabulary.pos.interjection
vocabulary.pos.pronoun
vocabulary.pos.determiner
vocabulary.pos.phrase
```

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```sh
xcodebuild test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A' \
  -only-testing:WordingDailyAppTests/VocabularySeedValidationTests \
  -only-testing:WordingDailyAppTests/LocalizationCoverageTests
```

Expected: compile failure for `PronunciationSpeaker` and missing localization keys.

- [ ] **Step 3: Implement native utterance creation**

Use:

```swift
import AVFAudio
import SwiftUI

enum PronunciationSpeaker {
    static func makeUtterance(
        expression: String,
        pronunciation: VocabularyPronunciation,
        availableVoices: [AVSpeechSynthesisVoice] = AVSpeechSynthesisVoice.speechVoices()
    ) -> AVSpeechUtterance {
        let attributed = NSMutableAttributedString(string: expression)
        attributed.addAttribute(
            NSAttributedString.Key(AVSpeechSynthesisIPANotationAttribute),
            value: pronunciation.ipa,
            range: NSRange(location: 0, length: attributed.length)
        )
        let utterance = AVSpeechUtterance(attributedString: attributed)
        let englishVoices = availableVoices.filter { $0.language.hasPrefix("en") }
        utterance.voice = englishVoices.first { $0.language == pronunciation.speechLocale }
            ?? englishVoices.first
            ?? AVSpeechSynthesisVoice(language: "en-US")
        return utterance
    }
}
```

This uses installed voices only. Do not add a download or network fallback.

- [ ] **Step 4: Implement the shared entry content**

Use this shared view; it shows the selected sense expanded and no more than two additional senses:

```swift
struct VocabularyEntryContentView: View {
    let item: VocabularySeedItem
    let senseID: String
    let supportLanguageCode: String
    let showsAdditionalSenses: Bool
    let synthesizer: AVSpeechSynthesizer

    private var selectedSense: VocabularySense {
        item.senses.first { $0.id == senseID }!
    }

    private var additionalSenses: [VocabularySense] {
        guard showsAdditionalSenses else { return [] }
        return Array(item.senses.filter { $0.id != senseID }.prefix(2))
    }

    var body: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                Text(verbatim: item.upgradedExpression)
                    .font(.title2.bold())
                Text(verbatim: item.plainExpression)
                    .foregroundStyle(.secondary)
            }
            senseDetails(selectedSense)
        }

        if !additionalSenses.isEmpty {
            Section {
                DisclosureGroup("vocabulary.additionalSenses") {
                    ForEach(additionalSenses) { sense in
                        senseDetails(sense)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func senseDetails(_ sense: VocabularySense) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(partOfSpeechKey(sense.partOfSpeech))
                .font(.subheadline.weight(.semibold))

            ForEach(pronunciations(for: sense)) { pronunciation in
                let region = pronunciation.region ?? String(localized: "vocabulary.region.general")
                Button {
                    synthesizer.speak(PronunciationSpeaker.makeUtterance(
                        expression: item.upgradedExpression,
                        pronunciation: pronunciation
                    ))
                } label: {
                    Label {
                        Text(verbatim: "\(region) /\(pronunciation.ipa)/")
                    } icon: {
                        Image(systemName: "speaker.wave.2")
                            .accessibilityHidden(true)
                    }
                    .frame(minHeight: 44)
                }
                .buttonStyle(.bordered)
                .accessibilityLabel(Text(verbatim: "\(item.upgradedExpression), \(region), /\(pronunciation.ipa)/"))
            }

            LabeledContent("vocabulary.meaning.english") {
                Text(verbatim: sense.meaning["en"] ?? "")
            }
            if supportLanguageCode != "en" {
                LabeledContent("vocabulary.meaning.support") {
                    Text(verbatim: localized(sense.meaning))
                }
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("vocabulary.example")
                    .font(.subheadline.weight(.semibold))
                Text(verbatim: sense.example.text)
                Text(verbatim: localized(sense.example.translation))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }

    private func pronunciations(for sense: VocabularySense) -> [VocabularyPronunciation] {
        let ids = Set(sense.pronunciationIDs)
        return item.pronunciations.filter { ids.contains($0.id) }
    }

    private func localized(_ values: [String: String]) -> String {
        values[supportLanguageCode] ?? values["en"] ?? values.values.first ?? ""
    }

    private func partOfSpeechKey(_ value: VocabularyPartOfSpeech) -> LocalizedStringKey {
        switch value {
        case .noun: "vocabulary.pos.noun"
        case .verb: "vocabulary.pos.verb"
        case .adjective: "vocabulary.pos.adjective"
        case .adverb: "vocabulary.pos.adverb"
        case .preposition: "vocabulary.pos.preposition"
        case .conjunction: "vocabulary.pos.conjunction"
        case .interjection: "vocabulary.pos.interjection"
        case .pronoun: "vocabulary.pos.pronoun"
        case .determiner: "vocabulary.pos.determiner"
        case .phrase: "vocabulary.pos.phrase"
        }
    }
}
```

The pronunciation VoiceOver label includes expression, region, and IPA; the speaker icon is accessibility-hidden.

- [ ] **Step 5: Integrate Practice without revealing answers early**

In listening mode before answer, play only the selected sense's first pronunciation and do not show expression or IPA. After `runState.currentFeedback` becomes non-nil, append:

```swift
private func speak(_ question: QuizQuestion) {
    guard let pronunciationID = question.selectedSense.pronunciationIDs.first,
          let pronunciation = question.item.pronunciations.first(where: { $0.id == pronunciationID }) else {
        return
    }
    speechSynthesizer.speak(PronunciationSpeaker.makeUtterance(
        expression: question.item.upgradedExpression,
        pronunciation: pronunciation
    ))
}

VocabularyEntryContentView(
    item: feedback.question.item,
    senseID: feedback.question.senseID,
    supportLanguageCode: feedback.question.supportLanguageCode,
    showsAdditionalSenses: true,
    synthesizer: speechSynthesizer
)
```

Keep options frozen, correct/wrong icon/text, correct answer, and manual `Next`. Replace `DailyPracticeView.learnView` singular meaning/example/speech code with the same shared view.

- [ ] **Step 6: Integrate Library read-only detail**

Import AVFAudio, add `@State private var speechSynthesizer = AVSpeechSynthesizer()`, and replace the existing definition/example sections with:

```swift
VocabularyEntryContentView(
    item: item.seedItem,
    senseID: item.seedItem.primarySenseID,
    supportLanguageCode: supportLanguageCode,
    showsAdditionalSenses: true,
    synthesizer: speechSynthesizer
)
```

Keep save toggle and review statistics unchanged. Add no edit/import/download control.

- [ ] **Step 7: Add localization and Xcode membership**

Add natural en/zh-Hant strings. Add `VocabularyEntryContentView.swift` to the formal App and QA App source phases, not the widget or test target.

- [ ] **Step 8: Run tests and simulator accessibility smoke checks**

Run:

```sh
xcodebuild test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A'
xcodebuild build -project WordingDailyApp.xcodeproj -scheme WordingDailyAppQA \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A'
```

Manually verify zh-Hant and English at normal and accessibility Dynamic Type, VoiceOver pronunciation labels, 44-point targets, primary sense expanded, additional senses disclosed, and no pre-answer reveal.

- [ ] **Step 9: Commit UI and native speech**

```sh
git add WordingDailyApp/Features/Shared/VocabularyEntryContentView.swift \
  WordingDailyApp/Features/Practice/PracticeView.swift \
  WordingDailyApp/Features/Library/LibraryView.swift \
  WordingDailyApp/Resources/Localizable.xcstrings \
  WordingDailyApp.xcodeproj/project.pbxproj WordingDailyAppTests
git diff --cached --check
git commit -m "feat: explain and pronounce quiz answers"
```

---

### Task 7: Update the reusable import skill and content policy

**Files:**
- Modify: `.agents/skills/wording-daily-vocabulary-import/SKILL.md`
- Modify: `.agents/skills/wording-daily-vocabulary-import/assets/evals/evals.json`
- Modify: `.agents/skills/wording-daily-vocabulary-import/references/quality_checklist.md`
- Modify: `docs/question-bank-sources-and-levels.md`
- Modify: `docs/content-review.md`

**Interfaces:**
- Skill documents target-only Wiktextract snapshotting, structured canonical fields, Agent review JSONL, full-bank audit, and atomic promotion.

- [ ] **Step 1: Add a failing skill eval case**

Add a prompt requiring one Wiktextract source plus CMUdict/OEWN cross-check, multiple IPA readings, three senses maximum, full bilingual examples, and proof that raw/review files stay outside Xcode. Record the current skill as RED because it only describes singular seed fields.

- [ ] **Step 2: Update workflow and policies**

Document exact commands from Tasks 1-3. State that Wiktextract quotations/audio are excluded, Agent output is not approved until `audit-reviewed` and release review pass, CMUdict comments are stripped, every sense references pronunciation IDs, and no usage-note translation can be promoted.

- [ ] **Step 3: Run all skill validation commands**

Use the repository's existing strict format, eval, reference, packaging, and archive-integrity checks listed in the skill quality checklist. Record exact pass evidence and current bank/source counts.

- [ ] **Step 4: Commit docs and skill**

```sh
git add .agents/skills/wording-daily-vocabulary-import docs/question-bank-sources-and-levels.md docs/content-review.md
git diff --cached --check
git commit -m "docs: document rich vocabulary review workflow"
```

---

### Task 8: Run the full offline completion audit on simulator and phone

**Files:**
- Modify only files required by a failing gate.

**Interfaces:**
- Produces authoritative evidence for source integrity, 5,440 reviewed entries, deterministic resources, App bundle exclusion, all tests, offline playback, and UI behavior.

- [ ] **Step 1: Run every maintainer gate**

```sh
python3 -m unittest tools/test_vocabulary_sources.py
python3 tools/vocabulary_sources.py verify
python3 tools/vocabulary_sources.py audit-reviewed --input Content/Reviews/vocabulary-rich-2026-07-11.jsonl
python3 tools/vocabulary_sources.py import-all --output-dir /tmp/wording-import-a
python3 tools/vocabulary_sources.py import-all --output-dir /tmp/wording-import-b
diff -qr /tmp/wording-import-a /tmp/wording-import-b
```

Expected: all tests/sources pass, review audit reports 5,440 approved items, and imports are identical.

- [ ] **Step 2: Prove seed/provenance/notices determinism and counts**

Rebuild twice using the Task 3 commands, compare every output, promote to `/tmp/VocabularySeed.audit.json`, and compare it byte-for-byte with the committed App seed. Verify one-to-one seed/provenance IDs, unique expressions/concepts, contiguous sort order, and exact level totals.

- [ ] **Step 3: Run the complete simulator stack**

```sh
xcodebuild clean test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A'
xcodebuild build -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -configuration Release -destination 'generic/platform=iOS Simulator'
```

Expected: all XCTest targets pass and Release builds.

- [ ] **Step 4: Inspect built resources and runtime source code**

Run:

```sh
APP=$(find ~/Library/Developer/Xcode/DerivedData -path '*Release-iphonesimulator/WordingDailyApp.app' -print -quit)
test -f "$APP/VocabularySeed.json"
test -f "$APP/ThirdPartyNotices.txt"
! find "$APP" -iname '*Raw*' -o -iname '*Imported*' -o -iname '*Provenance*' -o -iname '*source-manifest*' | grep .
! rg -n 'URLSession|import Network|NWConnection|CloudKit|CKContainer|ASAuthorization|apiKey|https?://' \
  WordingDailyApp WordingDailyWidget --glob '*.swift'
```

Expected: only seed/notices ship and Swift runtime contains no network/account/cloud path.

- [ ] **Step 5: Build, install, and launch QA on the paired phone**

Run:

```sh
rm -rf /tmp/WordingDailyQA-device
xcodebuild build -project WordingDailyApp.xcodeproj -scheme WordingDailyAppQA \
  -configuration Debug -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/WordingDailyQA-device \
  DEVELOPMENT_TEAM=8Z6WVFJ574 CODE_SIGN_STYLE=Automatic CODE_SIGN_ENTITLEMENTS=
xcrun devicectl device install app \
  --device 77F2E6C0-ECF9-5E25-81E4-5554094C6960 \
  /tmp/WordingDailyQA-device/Build/Products/Debug-iphoneos/WordingDailyAppQA.app
xcrun devicectl device process launch \
  --device 77F2E6C0-ECF9-5E25-81E4-5554094C6960 \
  com.raychiutw.WordingDaily.QA
```

Expected: Personal Team build installs and launches without App Group entitlement.

- [ ] **Step 6: Perform physical offline QA**

Disable Wi-Fi and cellular data on Ray's iPhone. Complete all five quiz modes. Verify before-answer secrecy; correct/wrong freeze; English/zh-Hant meaning; POS; bilingual example; multiple-sense disclosure; every pronunciation button in a deterministic multi-reading sample; Library detail; Dynamic Type; and VoiceOver. Re-enable connectivity only after QA evidence is recorded.

- [ ] **Step 7: Refresh the persistent knowledge graph after code lands**

Run:

```sh
codebase-memory-mcp cli index_repository \
  --repo-path /Users/ray/Projects/wording-daily-complete-v1 \
  --persistence true --mode full
codebase-memory-mcp cli search_graph \
  --project Users-ray-Projects-wording-daily-complete-v1 \
  --query VocabularyEntryContentView --limit 5
zstd -t .codebase-memory/graph.db.zst
```

If the persisted artifact changes, commit it separately:

```sh
git add .codebase-memory
git diff --cached --check
git commit -m "chore: refresh vocabulary knowledge graph"
```

- [ ] **Step 8: Final requirement audit**

Map every requirement in `docs/superpowers/specs/2026-07-11-offline-vocabulary-validation-design.md` to a command result, committed file, simulator result, or phone observation. Treat missing or indirect evidence as incomplete. Run:

```sh
git diff --check
git status --short --branch
```

Expected: no unresolved requirement, no unstaged change, and a clean `codex/complete-v1` branch. Do not push unless requested.
