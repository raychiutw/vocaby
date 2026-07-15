# All-Approved Vocabulary Parallel Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve all 10,021 existing lesson identities, append every newly eligible lesson from approved sources, make FreeDict contribute only through aligned evidence, and process enrichment and translation with two resumable local workers.

**Architecture:** Extend the existing shared Python pipeline instead of adding another importer or concurrency layer. `prepare-enrichment --all-available` filters normalized records to manifest-approved sources, rebuilds existing packets, and appends deterministic candidates after each level's current ID and sort-order maxima. `run-local` delegates translation to the already checkpointed `run_local_translation` function; the existing audit, build, promotion, Swift validation, and bundle gates remain authoritative.

**Tech Stack:** Python 3 standard library and `unittest`, existing OpenCC and Apple `NaturalLanguage`/Swift helpers, JSON/JSONL resources, Swift 6/SwiftUI, XCTest, and `xcodebuild`.

## Global Constraints

- Preserve every current lesson's `id`, `level`, `sortOrder`, and upgraded-expression identity.
- The final bank is the current 10,021 lessons plus every newly eligible unique candidate; do not impose level quotas in append-all mode.
- Verify all 15 pinned source snapshots, but allow shipping evidence from only the ten manifest entries whose `appUse` is `approved`.
- The blocked IDs `bsl-1.2`, `gcide-0.54`, `nawl-1.2`, `ngsl-1.2`, and `tsl-1.2` must not enter `sourceRefs`, `validationSourceIDs`, provenance catalog entries, or notices.
- FreeDict evidence requires compatible headword, part of speech when present, and definition/sense alignment; a headword-only match is insufficient.
- Use one review process and exactly two internal workers for enrichment and translation; never run concurrent CLIs against the same work directory.
- Resume only with unchanged queue and Swift helper inputs.
- Build shipping artifacts twice and require byte-identical seed, provenance, and notices before promotion.
- Ship only `VocabularySeed.json` and `ThirdPartyNotices.txt`; never add source, import, review, report, or provenance paths to the Xcode target.
- Set provenance `bankVersion` to `2026.07.4` and review metadata to 2026-07-15.
- Add no dependency, runtime network path, importer abstraction, worker framework, or app runtime feature.

---

## File Map

- `tools/review_vocabulary.py`: reuse checkpointed parallel translation, preserve source IDs in rejection accounting, and stamp the current review date.
- `tools/test_review_vocabulary.py`: prove worker forwarding, translation completeness, resume behavior, and rejection accounting.
- `tools/vocabulary_sources.py`: add approved-source filtering, append-all candidate selection, FreeDict fallback alignment, blocked validation-source gates, and current bank metadata.
- `tools/test_vocabulary_sources.py`: prove identity preservation, deterministic append behavior, FreeDict alignment, blocked-source exclusion, notices, and metadata.
- `Content/Reviews/vocabulary-rich-2026-07-15.jsonl`: tracked complete reviewed bank produced by the pipeline.
- `docs/vocabulary-rejections-2026-07-15.md`: tracked selected/rejected reconciliation grouped by source and reason.
- `Vocaby/Resources/VocabularySeed.json`: promoted app seed.
- `Content/VocabularyProvenance.json`: promoted repository-only evidence.
- `Vocaby/Resources/ThirdPartyNotices.txt`: promoted app notices.
- `docs/question-bank-sources-and-levels.md`: current counts, all 15 sources, FreeDict use, and the reproducible two-worker command sequence.
- `VocabyTests/VocabularySeedValidationTests.swift`: bank expansion floor and full rich-entry validation.

---

### Task 1: Reuse Checkpointed Parallel Translation from `run-local`

**Files:**
- Modify: `tools/review_vocabulary.py:489-626`
- Test: `tools/test_review_vocabulary.py:22-64`

**Interfaces:**
- Consumes: `run_local_translation(work_dir: Path, swift_source: Path, workers: int) -> int`.
- Produces: `run_local_services(work_dir: Path, swift_source: Path, workers: int) -> dict[str, int]` with the same worker count applied to enrichment and translation.

- [ ] **Step 1: Update the service-resume test so translation delegation fails first**

Replace the patch/call/assertion portion of `test_run_local_services_resumes_completed_enrichment_batches` with:

```python
            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ), mock.patch.object(
                review_vocabulary,
                "finish_enrichment",
                side_effect=finish,
            ), mock.patch.object(
                review_vocabulary,
                "run_local_translation",
                return_value=3,
            ) as translate:
                result = review_vocabulary.run_local_services(
                    work, root / "helper.swift", 2
                )

            self.assertEqual(
                result, {"batches": 2, "items": 2, "translations": 3}
            )
            translate.assert_called_once_with(work, root / "helper.swift", 2)
```

Retain the existing assertion that only `batch-2` is enriched.

Add direct parallel resume and exact-ID tests:

```python
    def test_run_local_translation_resumes_parallel_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            requests = [
                {"id": f"segment-{index:03d}", "text": "text"}
                for index in range(401)
            ]
            (work / "translation-input.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in requests),
                encoding="utf-8",
            )
            (work / "translation-output.jsonl").write_text(
                json.dumps({"id": "segment-000", "text": "done"}) + "\n",
                encoding="utf-8",
            )
            calls = []

            def helper(_executable, mode, payload):
                self.assertEqual(mode, "translate")
                chunk = [json.loads(line) for line in payload.splitlines()]
                calls.append({item["id"] for item in chunk})
                return "".join(
                    json.dumps({"id": item["id"], "text": "translated"}) + "\n"
                    for item in chunk
                )

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ):
                count = review_vocabulary.run_local_translation(
                    work, root / "helper.swift", 2
                )

            self.assertEqual(count, 401)
            self.assertEqual(len(calls), 2)
            self.assertNotIn("segment-000", set().union(*calls))
            completed = review_vocabulary.sources.read_jsonl(
                work / "translation-output.jsonl"
            )
            self.assertEqual(
                {item["id"] for item in completed},
                {item["id"] for item in requests},
            )

    def test_run_local_translation_rejects_incomplete_parallel_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            (work / "translation-input.jsonl").write_text(
                json.dumps({"id": "segment-001", "text": "text"}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", return_value=""
            ):
                with self.assertRaisesRegex(
                    review_vocabulary.sources.SourceError, "incomplete IDs"
                ):
                    review_vocabulary.run_local_translation(
                        work, root / "helper.swift", 2
                    )

            self.assertFalse((work / "translation-output.jsonl").exists())
```

- [ ] **Step 2: Run the focused tests and confirm delegation fails**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools.test_review_vocabulary.ReviewVocabularyTests.test_run_local_services_resumes_completed_enrichment_batches \
  tools.test_review_vocabulary.ReviewVocabularyTests.test_run_local_translation_resumes_parallel_chunks \
  tools.test_review_vocabulary.ReviewVocabularyTests.test_run_local_translation_rejects_incomplete_parallel_ids
```

Expected: the two direct translation tests pass against the existing helper, while the service test fails because `run_local_services` does not delegate and returns the request count from `finish_enrichment`.

- [ ] **Step 3: Replace the duplicate serial translation block with the existing helper**

In `run_local_services`, replace:

```python
        translation_payload = (work_dir / "translation-input.jsonl").read_text(encoding="utf-8")
        translated = run_helper(executable, "translate", translation_payload)
        sources.atomic_write(work_dir / "translation-output.jsonl", translated)
```

with:

```python
        translated = run_local_translation(work_dir, swift_source, workers)
```

Return the completed count:

```python
    return {
        "batches": len(batches),
        "items": finish["items"],
        "translations": translated,
    }
```

Do not refactor compilation or add another executor; the existing translation function already owns chunking, exact-ID validation, checkpoint writes, and resume behavior.

- [ ] **Step 4: Run the review pipeline tests**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tools.test_review_vocabulary
```

Expected: all review-vocabulary tests pass.

- [ ] **Step 5: Commit the worker reuse**

```sh
git add tools/review_vocabulary.py tools/test_review_vocabulary.py
git commit -m "fix: parallelize vocabulary translation"
```

---

### Task 2: Add Manifest-Approved Append-All Selection

**Files:**
- Modify: `tools/vocabulary_sources.py:1256-1895,2390-2498`
- Test: `tools/test_vocabulary_sources.py:655-769,1489-1570`

**Interfaces:**
- Consumes: normalized JSONL records, `current_seed_path`, and the manifest-derived approved source-ID set.
- Produces: `prepare_enrichment(input_dir: Path, existing_seed_path: Path, quotas: dict[str, int], output: Path, current_seed_path: Path | None = None, all_available: bool = False, approved_source_ids: set[str] | None = None) -> int` and CLI flag `prepare-enrichment --all-available`.

- [ ] **Step 1: Make enrichment fixtures legally representative**

In `make_enrichment_sources`, change the fixture source entries from:

```python
                    "appUse": "reference_only",
```

to:

```python
                    "appUse": "approved",
```

This fixture is used to test shipping candidate preparation, not reference-only imports.

- [ ] **Step 2: Add a failing append-all identity and determinism test**

Add this test beside the existing current-seed identity test:

```python
    def test_prepare_enrichment_all_available_preserves_and_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            lexical_path = input_dir / "oewn-2025.jsonl"
            lexical = json.loads(lexical_path.read_text().splitlines()[0])
            appended = {
                **lexical,
                "sourceEntryRef": "superb#a",
                "headword": "superb",
                "definitions": ["of very high quality"],
                "examples": ["The team delivered a superb result."],
                "relatedTerms": ["superb", "very good"],
                "senseRefs": ["0002-a"],
            }
            lexical_path.write_text(
                lexical_path.read_text()
                + json.dumps(appended, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            freedict_path = input_dir / "freedict.jsonl"
            freedict = json.loads(freedict_path.read_text().splitlines()[0])
            freedict_path.write_text(
                freedict_path.read_text()
                + json.dumps(
                    {
                        **freedict,
                        "sourceEntryRef": "entry-superb",
                        "headword": "superb",
                        "definitions": ["of very high quality"],
                        "translations": {"zh": ["極好的"]},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            cefr_path = input_dir / "cefr.jsonl"
            cefr = json.loads(cefr_path.read_text().splitlines()[0])
            cefr_path.write_text(
                cefr_path.read_text()
                + json.dumps(
                    {
                        **cefr,
                        "sourceEntryRef": "superb#adjective#A2",
                        "headword": "superb",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["sources"].append(
                {
                    "id": "blocked",
                    "name": "blocked",
                    "version": "1",
                    "canonicalURL": "https://example.invalid/blocked",
                    "license": "Demo license",
                    "licenseURL": "https://example.invalid/license",
                    "appUse": "reference_only",
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (input_dir / "blocked.jsonl").write_text(
                json.dumps(
                    {
                        **appended,
                        "sourceID": "blocked",
                        "sourceEntryRef": "blocked-superb",
                        "pronunciations": [
                            {
                                "notation": "ipa",
                                "value": "suːˈpɜːb",
                                "speechLocale": "en-US",
                                "region": "US",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            current_seed = root / "current-seed.json"
            current_seed.write_text(
                json.dumps(
                    [
                        {
                            "id": "bank-basic-1588",
                            "level": "basic",
                            "sortOrder": 1,
                            "plainExpression": "very good",
                            "upgradedExpression": "excellent",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            arguments = (
                "prepare-enrichment",
                "--input-dir",
                str(input_dir),
                "--existing-seed",
                str(existing_seed),
                "--current-seed",
                str(current_seed),
                "--all-available",
                "--output",
            )

            result = self.run_cli(root, *arguments, str(first), hash_seed="1")
            self.assertEqual(result.returncode, 0, result.stderr)
            for path in input_dir.glob("*.jsonl"):
                lines = path.read_text(encoding="utf-8").splitlines()
                path.write_text(
                    "".join(line + "\n" for line in reversed(lines)),
                    encoding="utf-8",
                )
            result = self.run_cli(root, *arguments, str(second), hash_seed="2")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            by_target = {
                item["target"]: item
                for item in map(json.loads, first.read_text().splitlines())
            }
            self.assertEqual(set(by_target), {"excellent", "superb"})
            self.assertEqual(by_target["excellent"]["id"], "bank-basic-1588")
            self.assertEqual(by_target["excellent"]["sortOrder"], 1)
            self.assertEqual(by_target["superb"]["id"], "bank-basic-1589")
            self.assertEqual(by_target["superb"]["sortOrder"], 2)
            self.assertNotIn(
                "blocked", by_target["superb"]["validationSourceIDs"]
            )
            self.assertNotIn(
                "blocked",
                {ref["sourceID"] for ref in by_target["superb"]["sourceRefs"]},
            )
```

- [ ] **Step 3: Add a failing CLI contract test**

Add:

```python
    def test_all_available_requires_current_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            result = self.run_cli(
                root,
                "prepare-enrichment",
                "--input-dir",
                str(input_dir),
                "--existing-seed",
                str(existing_seed),
                "--all-available",
                "--output",
                str(root / "queue.jsonl"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--current-seed", result.stderr)
```

- [ ] **Step 4: Run the new tests and confirm the flag is missing**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_prepare_enrichment_all_available_preserves_and_appends \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_all_available_requires_current_seed
```

Expected: both tests fail because `--all-available` is not recognized.

- [ ] **Step 5: Add the minimum append-all parameters and approved-record filter**

Change the function signature to:

```python
def prepare_enrichment(
    input_dir: Path,
    existing_seed_path: Path,
    quotas: dict[str, int],
    output: Path,
    current_seed_path: Path | None = None,
    all_available: bool = False,
    approved_source_ids: set[str] | None = None,
) -> int:
```

After loading `records`, filter only when the caller supplies the manifest gate:

```python
    if approved_source_ids is not None:
        records = [
            record
            for record in records
            if record.get("sourceID") in approved_source_ids
        ]
    index_keys = None if all_available else current_keys
```

Change the first record-index condition to:

```python
        if not key or (index_keys is not None and key not in index_keys):
            continue
```

Delete `reference_sources`, the blocked-list population branch, and its scoring term. Blocked inputs no longer influence ranking because they are removed once at the shared trust boundary.

- [ ] **Step 6: Append deterministic candidates without changing existing packets**

At the end of the `current_seed is not None` branch, before the quota branch, add:

```python
        if all_available:
            used_ids = {item["id"] for item in current_seed}
            for level in LEVEL_ORDER:
                next_sort_order = max(
                    (
                        item["sortOrder"]
                        for item in current_seed
                        if item["level"] == level
                    ),
                    default=0,
                )
                numeric_ids = []
                for item in current_seed:
                    if item["level"] != level:
                        continue
                    match = re.fullmatch(rf"bank-{re.escape(level)}-(\d+)", item["id"])
                    if match:
                        numeric_ids.append(int(match.group(1)))
                next_id_number = max(numeric_ids, default=0)
                available = sorted(
                    (
                        item
                        for key, item in candidates.items()
                        if key not in current_keys and item["level"] == level
                    ),
                    key=lambda item: item["_score"],
                )
                for candidate in available:
                    item = {
                        key: value
                        for key, value in candidate.items()
                        if key != "_score"
                    }
                    next_sort_order += 1
                    next_id_number += 1
                    item["id"] = f"bank-{level}-{next_id_number:04d}"
                    while item["id"] in used_ids:
                        next_id_number += 1
                        item["id"] = f"bank-{level}-{next_id_number:04d}"
                    used_ids.add(item["id"])
                    item["sortOrder"] = next_sort_order
                    item["issues"] = []
                    selected.append(item)
```

The existing common tail continues to attach senses, pronunciations, plain candidates, validation IDs, and stable JSON ordering to both old and appended packets.

- [ ] **Step 7: Wire the CLI to the manifest gate**

Add the parser flag:

```python
    prepare_parser.add_argument("--all-available", action="store_true")
```

Before calling `prepare_enrichment`, validate and derive the approved IDs:

```python
        if args.all_available and args.current_seed is None:
            raise SourceError("--all-available requires --current-seed")
        approved_source_ids = {
            source["id"]
            for source in manifest["sources"]
            if source.get("appUse") == "approved"
        }
```

Pass the two new arguments:

```python
        count = prepare_enrichment(
            args.input_dir,
            args.existing_seed,
            quotas,
            args.output,
            args.current_seed,
            args.all_available,
            approved_source_ids,
        )
```

- [ ] **Step 8: Run the focused and complete vocabulary-source suites**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_prepare_enrichment_all_available_preserves_and_appends \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_all_available_requires_current_seed
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tools.test_vocabulary_sources
```

Expected: all tests pass; existing quota behavior remains covered by `test_prepare_enrichment_fails_when_a_level_quota_is_unavailable`.

- [ ] **Step 9: Commit approved append-all selection**

```sh
git add tools/vocabulary_sources.py tools/test_vocabulary_sources.py
git commit -m "feat: append all approved vocabulary candidates"
```

---

### Task 3: Allow Only Sense-Aligned FreeDict Fallback

**Files:**
- Modify: `tools/vocabulary_sources.py:1360-1630`
- Test: `tools/test_vocabulary_sources.py:1643-1754`

**Interfaces:**
- Consumes: existing `translations` entries and candidate lexical POS/definition terms.
- Produces: locally preferred CEDICT when aligned, otherwise aligned FreeDict; every selected translation keeps its original `reference` for attribution.

- [ ] **Step 1: Replace the global-CEDICT expectation with an aligned fallback test**

Rename `test_prepare_enrichment_requires_cedict_when_the_reviewed_source_exists` to `test_prepare_enrichment_falls_back_to_aligned_freedict` and change its final assertions to:

```python
            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads((root / "draft.jsonl").read_text())
            self.assertEqual(packet["translationDraft"], "優秀")
            self.assertIn(
                "freedict",
                {reference["sourceID"] for reference in packet["sourceRefs"]},
            )
```

Set the command's output path to `root / "draft.jsonl"`. Keep the unrelated CEDICT row in the fixture so the test distinguishes global availability from local alignment.

- [ ] **Step 2: Add a failing POS mismatch test**

Add:

```python
    def test_prepare_enrichment_rejects_freedict_part_of_speech_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            (input_dir / "cow.jsonl").unlink()
            record = json.loads((input_dir / "freedict.jsonl").read_text())
            record["partOfSpeech"] = "n"
            (input_dir / "freedict.jsonl").write_text(
                json.dumps(record, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            result = self.run_cli(
                root,
                "prepare-enrichment",
                "--input-dir",
                str(input_dir),
                "--existing-seed",
                str(existing_seed),
                "--basic",
                "1",
                "--intermediate",
                "0",
                "--advanced",
                "0",
                "--output",
                str(root / "draft.jsonl"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not enough basic candidates", result.stderr)
```

- [ ] **Step 3: Run both tests and confirm current behavior is wrong**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_prepare_enrichment_falls_back_to_aligned_freedict \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_prepare_enrichment_rejects_freedict_part_of_speech_mismatch
```

Expected: FreeDict fallback fails when any CEDICT row exists, and POS mismatch is currently accepted.

- [ ] **Step 4: Carry normalized POS in word translation entries**

Add this field where `translations` entries are created:

```python
                "partOfSpeech": part_of_speech_code(
                    record.get("partOfSpeech")
                ),
```

After computing lexical `pos`, extend the translation-option filter to require both semantic and POS compatibility:

```python
        translation_options = [
            item
            for item in translation_options
            if (item["definitionMatch"] or item["synonymMatch"])
            and (
                not item["partOfSpeech"]
                or not pos
                or item["partOfSpeech"] == pos
            )
        ]
```

- [ ] **Step 5: Prefer locally aligned CEDICT without globally excluding FreeDict**

Delete the `requires_cedict` calculation. Replace:

```python
        elif requires_cedict:
            translation_options = cedict_options
```

with:

```python
        elif cedict_options:
            translation_options = cedict_options
```

This preserves COW/ILI priority, then aligned CEDICT priority, then an aligned FreeDict fallback. Existing definition/synonym checks continue to reject mismatched senses.

- [ ] **Step 6: Run all source tests and verify the real FreeDict snapshot imports**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tools.test_vocabulary_sources
tmp=$(mktemp /tmp/vocaby-freedict.XXXXXX.jsonl)
python3 tools/vocabulary_sources.py import-source \
  freedict-eng-zho-2025.11.23 --output "$tmp"
test "$(wc -l < "$tmp" | tr -d ' ')" -eq 30362
rm -f "$tmp"
```

Expected: all tests pass and the pinned FreeDict adapter emits exactly 30,362 canonical records.

- [ ] **Step 7: Commit FreeDict alignment**

```sh
git add tools/vocabulary_sources.py tools/test_vocabulary_sources.py
git commit -m "fix: align FreeDict translation fallback"
```

---

### Task 4: Harden Shipping Gates and Rejection Accounting

**Files:**
- Modify: `tools/vocabulary_sources.py:1994-2132,2308-2387`
- Modify: `tools/review_vocabulary.py:43-123,351-463`
- Test: `tools/test_vocabulary_sources.py:1424-1487,2080-2140`
- Test: `tools/test_review_vocabulary.py:127-189`

**Interfaces:**
- Consumes: reviewed `sourceRefs`, `validationSourceIDs`, manifest `appUse`, and work-directory rejection rows.
- Produces: provenance version `2026.07.4`, 2026-07-15 reviewer metadata, fail-closed validation IDs, and a reconciled rejection report.

- [ ] **Step 1: Add failing metadata and blocked-validation assertions**

Extend `test_build_reviewed_promotes_only_rich_seed_fields`:

```python
            provenance_data = json.loads(provenance.read_text())
            self.assertEqual(provenance_data["bankVersion"], "2026.07.4")
            self.assertEqual(
                provenance_data["items"][0]["reviewedAt"], "2026-07-15"
            )
```

Add:

```python
    def test_build_reviewed_rejects_blocked_validation_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = self.make_source(root)
            manifest = json.loads(manifest_path.read_text())
            manifest["sources"][0]["appUse"] = "approved"
            manifest["sources"].append(
                {
                    **manifest["sources"][0],
                    "id": "blocked",
                    "appUse": "reference_only",
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            item = self.rich_review_record()
            item["sourceRefs"] = [
                {"sourceID": "demo", "sourceEntryRef": "lead-v-1"}
            ]
            item["validationSourceIDs"] = ["demo", "blocked"]
            reviewed = root / "reviewed.jsonl"
            reviewed.write_text(json.dumps(item) + "\n", encoding="utf-8")
            existing = root / "existing.json"
            existing.write_text("[]", encoding="utf-8")

            result = self.run_cli(
                root,
                "build-reviewed",
                "--input",
                str(reviewed),
                "--existing-seed",
                str(existing),
                "--seed-output",
                str(root / "seed.json"),
                "--provenance-output",
                str(root / "provenance.json"),
                "--notices-output",
                str(root / "notices.txt"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not approved for app use", result.stderr)
```

- [ ] **Step 2: Add failing rejection reconciliation assertions**

In `test_prepare_review_rejects_only_items_without_verified_pronunciation`, add:

```python
            self.assertEqual(
                rejection["sourceIDs"], ["oewn-2025"]
            )
```

Add this focused report test:

```python
    def test_build_reviewed_reconciles_rejection_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            (work / "enriched.jsonl").write_text("", encoding="utf-8")
            (work / "translation-output.jsonl").write_text("", encoding="utf-8")
            (work / "rejections.jsonl").write_text(
                json.dumps(
                    {
                        "id": "bank-basic-0001",
                        "level": "basic",
                        "target": "unpronounceable",
                        "reason": "no-verified-pronunciation",
                        "sourceIDs": ["oewn-2025"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            output = root / "reviewed.jsonl"
            report_path = root / "rejections.md"

            with mock.patch.object(
                review_vocabulary.sources, "traditionalize", return_value=[]
            ), mock.patch.object(
                review_vocabulary.sources,
                "audit_reviewed",
                return_value={"items": 0},
            ):
                result = review_vocabulary.build_reviewed(
                    work, output, report_path
                )

            self.assertEqual(result, {"items": 0})
            report = report_path.read_text()
            self.assertIn("Selected: 0", report)
            self.assertIn("Rejected: 1", report)
            self.assertIn("Total candidates: 1", report)
            self.assertIn("no-verified-pronunciation: 1", report)
            self.assertIn("oewn-2025: 1", report)
```

- [ ] **Step 3: Run the focused tests and confirm old metadata/gates fail**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_build_reviewed_promotes_only_rich_seed_fields \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_build_reviewed_rejects_blocked_validation_source \
  tools.test_review_vocabulary
```

Expected: failures identify bank version/date, blocked validation acceptance, and missing rejection source accounting.

- [ ] **Step 4: Reject blocked validation sources in both build and promotion gates**

In `build_reviewed`, replace validation-source checking with:

```python
        for source_id in validation_source_ids:
            if source_id == "vocaby-original":
                continue
            source = catalog.get(source_id)
            if source is None or source.get("appUse") != "approved":
                raise SourceError(
                    f"validation source {source_id} is not approved for app use"
                )
```

In `promote`, replace the current validation-source condition with:

```python
        if not isinstance(validation_source_ids, list) or any(
            source_id != "vocaby-original"
            and (
                source_id not in external
                or external[source_id].get("appUse") != "approved"
            )
            for source_id in validation_source_ids
        ):
            raise SourceError(
                f"provenance item {item_id} uses a validation source "
                "that is not approved for app use"
            )
```

`vocaby-original` remains exempt because it is project-owned and generated by the pipeline.

- [ ] **Step 5: Update literal bank and review metadata**

Use the approved release literals directly; do not add configuration for one release value:

```python
        "rightsReviewer": "codex-content-review-2026-07-15",
        "rightsVerifiedAt": "2026-07-15",
```

```python
                "reviewedAt": item.get("reviewedAt", "2026-07-15"),
```

```python
        "bankVersion": "2026.07.4",
```

In `tools/review_vocabulary.py`, stamp new reviewed rows with:

```python
                    "englishReviewer": "codex-content-review-2026-07-15",
                    "zhHantReviewer": "codex-content-review-2026-07-15",
                    "reviewedAt": "2026-07-15",
```

- [ ] **Step 6: Preserve source IDs and summarize rejection accounting**

Add the source IDs to each rejection in `prepare_review`:

```python
                    "sourceIDs": sorted(
                        {
                            ref["sourceID"]
                            for ref in packet.get("sourceRefs", [])
                            if ref.get("sourceID")
                        }
                    ),
```

Use the standard library in `build_reviewed`:

```python
from collections import Counter
```

Build the report summary before the item table:

```python
    reason_counts = Counter(item["reason"] for item in rejections)
    source_counts = Counter(
        source_id
        for item in rejections
        for source_id in item.get("sourceIDs", [])
    )
    report = [
        "# Vocabulary review rejections",
        "",
        f"Selected: {len(reviewed)}",
        f"Rejected: {len(rejections)}",
        f"Total candidates: {len(reviewed) + len(rejections)}",
        "",
        "## Rejections by reason",
        "",
        *(f"- {reason}: {count}" for reason, count in sorted(reason_counts.items())),
        "",
        "## Rejections by source",
        "",
        *(f"- {source_id}: {count}" for source_id, count in sorted(source_counts.items())),
        "",
        "## Rejected candidates",
        "",
        "| ID | Level | Expression | Reason |",
        "| --- | --- | --- | --- |",
        *(
            f"| {item['id']} | {item['level']} | {item['target']} | {item['reason']} |"
            for item in rejections
        ),
        "",
    ]
```

- [ ] **Step 7: Run both Python suites**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools.test_vocabulary_sources tools.test_review_vocabulary
```

Expected: all tests pass.

- [ ] **Step 8: Commit gates and accounting**

```sh
git add \
  tools/vocabulary_sources.py \
  tools/review_vocabulary.py \
  tools/test_vocabulary_sources.py \
  tools/test_review_vocabulary.py
git commit -m "fix: harden vocabulary promotion gates"
```

---

### Task 5: Generate and Audit the Complete Reviewed Bank with Two Workers

**Files:**
- Create: `Content/Reviews/vocabulary-rich-2026-07-15.jsonl`
- Create: `docs/vocabulary-rejections-2026-07-15.md`
- Generate in ignored work area: `Content/Sources/Reports/vocabulary-2026-07-15/**`

**Interfaces:**
- Consumes: the 15 pinned raw snapshots, approved append-all selector, current seed, CMUdict import, and Apple local language helper.
- Produces: a complete rich review JSONL, rejection report, two deterministic build directories, and audit evidence for final promotion.

- [ ] **Step 1: Create one fresh resumable work root and verify all snapshots**

Run:

```sh
RUN=Content/Sources/Reports/vocabulary-2026-07-15
test ! -e "$RUN"
mkdir -p "$RUN/import-a" "$RUN/import-b" "$RUN/work" "$RUN/build-a" "$RUN/build-b"
python3 tools/vocabulary_sources.py verify
```

Expected: `verified 15 source(s)`. If the work root exists, inspect it and resume only when its queue and helper inputs match; do not delete a potentially useful checkpoint blindly.

- [ ] **Step 2: Normalize twice and compare canonical imports**

Run:

```sh
python3 tools/vocabulary_sources.py import-all --output-dir "$RUN/import-a"
python3 tools/vocabulary_sources.py import-all --output-dir "$RUN/import-b"
diff -rq "$RUN/import-a" "$RUN/import-b"
```

Expected: `diff` prints nothing and exits zero. Both imports include `freedict-eng-zho-2025.11.23.jsonl` with 30,362 rows.

- [ ] **Step 3: Prepare every existing and newly eligible candidate**

Run:

```sh
python3 tools/vocabulary_sources.py prepare-enrichment \
  --input-dir "$RUN/import-a" \
  --existing-seed Vocaby/Resources/VocabularySeed.json \
  --current-seed Vocaby/Resources/VocabularySeed.json \
  --all-available \
  --output "$RUN/review-queue.jsonl"
```

Verify identity preservation and expansion before local language processing:

```sh
python3 - "$RUN/review-queue.jsonl" <<'PY'
import json
import sys

old = json.load(open("Vocaby/Resources/VocabularySeed.json", encoding="utf-8"))
queue = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
old_by_id = {item["id"]: item for item in old}
queue_by_id = {item["id"]: item for item in queue}
assert len(old_by_id) == 10_021
assert set(old_by_id) <= set(queue_by_id)
for item_id, item in old_by_id.items():
    packet = queue_by_id[item_id]
    assert packet["target"] == item["upgradedExpression"]
    assert packet["level"] == item["level"]
    assert packet["sortOrder"] == item["sortOrder"]
assert len(queue) > len(old), "append-all found no new eligible candidate"
print({"existing": len(old), "queue": len(queue), "new": len(queue) - len(old)})
PY
```

Expected: all assertions pass and `new` is greater than zero.

- [ ] **Step 4: Prepare the dated review work directory**

Run:

```sh
python3 tools/review_vocabulary.py prepare \
  --queue "$RUN/review-queue.jsonl" \
  --cmudict "$RUN/import-a/cmudict-7479086.jsonl" \
  --work-dir "$RUN/work" \
  --batch-size 20
```

Expected: JSON reports accepted, rejected, and sense counts; accepted plus rejected equals the review-queue row count.

- [ ] **Step 5: Run enrichment and translation through one two-worker process**

Run:

```sh
python3 tools/review_vocabulary.py run-local \
  --work-dir "$RUN/work" \
  --workers 2
```

Expected: enrichment checkpoint progress is followed by translation checkpoint progress, then JSON reports all batches, items, and translations. On interruption, rerun this exact command against the unchanged work directory; do not start a second simultaneous process.

- [ ] **Step 6: Build the tracked rich review and rejection artifacts**

Run:

```sh
python3 tools/review_vocabulary.py build-reviewed \
  --work-dir "$RUN/work" \
  --output Content/Reviews/vocabulary-rich-2026-07-15.jsonl \
  --rejection-report docs/vocabulary-rejections-2026-07-15.md
python3 tools/vocabulary_sources.py audit-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-15.jsonl
```

Expected: the audit reports one approved reviewed row for every selected candidate that was not rejected, with no structural error.

- [ ] **Step 7: Prove candidate accounting and source policy**

Run:

```sh
python3 - "$RUN" <<'PY'
import json
import sys
from pathlib import Path

run = Path(sys.argv[1])
queue = [json.loads(line) for line in (run / "review-queue.jsonl").read_text().splitlines() if line]
reviewed = [json.loads(line) for line in Path("Content/Reviews/vocabulary-rich-2026-07-15.jsonl").read_text().splitlines() if line]
rejected = [json.loads(line) for line in (run / "work/rejections.jsonl").read_text().splitlines() if line]
assert len(reviewed) + len(rejected) == len(queue)
approved = {
    "cefr-j-1.6",
    "cc-cedict-2026-07-11",
    "cmudict-7479086",
    "cow-0.9",
    "freedict-eng-zho-2025.11.23",
    "grundwortschatz-voc-en-004977a",
    "omw-ili-map-e3b5ac1",
    "oewn-2025",
    "tatoeba-eng-cmn-2026-07-04",
    "wiktextract-en-2026-07-09",
}
blocked = {"bsl-1.2", "gcide-0.54", "nawl-1.2", "ngsl-1.2", "tsl-1.2"}
source_refs = {
    ref["sourceID"]
    for item in reviewed
    for ref in item["sourceRefs"]
}
validation_ids = {
    source_id
    for item in reviewed
    for source_id in item["validationSourceIDs"]
}
assert approved <= source_refs
assert not blocked & source_refs
assert not blocked & validation_ids
assert sum(
    any(ref["sourceID"] == "freedict-eng-zho-2025.11.23" for ref in item["sourceRefs"])
    for item in reviewed
) > 0
print({"queue": len(queue), "selected": len(reviewed), "rejected": len(rejected)})
PY
```

Expected: all ten approved external source IDs are backed by at least one actual reference, FreeDict contributes at least once, all blocked sets are empty, and accounting reconciles.

- [ ] **Step 8: Build twice and require byte-identical outputs**

Run both builds:

```sh
for build in build-a build-b; do
  python3 tools/vocabulary_sources.py build-reviewed \
    --input Content/Reviews/vocabulary-rich-2026-07-15.jsonl \
    --existing-seed Vocaby/Resources/VocabularySeed.json \
    --seed-output "$RUN/$build/VocabularySeed.json" \
    --provenance-output "$RUN/$build/VocabularyProvenance.json" \
    --notices-output "$RUN/$build/ThirdPartyNotices.txt"
done
cmp "$RUN/build-a/VocabularySeed.json" "$RUN/build-b/VocabularySeed.json"
cmp "$RUN/build-a/VocabularyProvenance.json" "$RUN/build-b/VocabularyProvenance.json"
cmp "$RUN/build-a/ThirdPartyNotices.txt" "$RUN/build-b/ThirdPartyNotices.txt"
```

Expected: all three comparisons exit zero without output.

- [ ] **Step 9: Validate the candidate shipping set without touching app resources**

Run:

```sh
python3 tools/vocabulary_sources.py promote \
  --reviewed "$RUN/build-a/VocabularySeed.json" \
  --provenance "$RUN/build-a/VocabularyProvenance.json" \
  --notices "$RUN/build-a/ThirdPartyNotices.txt" \
  --output "$RUN/VocabularySeed.promoted.json"
cmp "$RUN/build-a/VocabularySeed.json" "$RUN/VocabularySeed.promoted.json"
```

Expected: promotion succeeds and the promoted seed is byte-identical to the deterministic build.

---

### Task 6: Promote Resources, Update Policy, and Verify the App Bundle

**Files:**
- Modify: `Vocaby/Resources/VocabularySeed.json`
- Modify: `Content/VocabularyProvenance.json`
- Modify: `Vocaby/Resources/ThirdPartyNotices.txt`
- Modify: `docs/question-bank-sources-and-levels.md`
- Modify: `VocabyTests/VocabularySeedValidationTests.swift`
- Include generated files from Task 5.

**Interfaces:**
- Consumes: Task 5's byte-identical `build-a` artifacts and reconciled counts.
- Produces: final repository/app resources and evidence that the Release bundle contains only the intended vocabulary files.

- [ ] **Step 1: Promote all three generated resources through the existing builder**

After the Task 5 promotion validation passes, run the reviewed builder once more with canonical destinations:

```sh
RUN=Content/Sources/Reports/vocabulary-2026-07-15
python3 tools/vocabulary_sources.py build-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-15.jsonl \
  --existing-seed Vocaby/Resources/VocabularySeed.json \
  --seed-output Vocaby/Resources/VocabularySeed.json \
  --provenance-output Content/VocabularyProvenance.json \
  --notices-output Vocaby/Resources/ThirdPartyNotices.txt
cmp Vocaby/Resources/VocabularySeed.json "$RUN/build-a/VocabularySeed.json"
cmp Content/VocabularyProvenance.json "$RUN/build-a/VocabularyProvenance.json"
cmp Vocaby/Resources/ThirdPartyNotices.txt "$RUN/build-a/ThirdPartyNotices.txt"
```

Expected: the builder validates the complete review before writing, then every canonical resource matches the audited build exactly.

- [ ] **Step 2: Verify existing identities survived promotion**

Use the pre-promotion seed saved in Git and the promoted file:

```sh
git show 786c3cd:Vocaby/Resources/VocabularySeed.json > "$RUN/previous-seed.json"
python3 - "$RUN/previous-seed.json" <<'PY'
import json
import sys

old = {item["id"]: item for item in json.load(open(sys.argv[1], encoding="utf-8"))}
new = {item["id"]: item for item in json.load(open("Vocaby/Resources/VocabularySeed.json", encoding="utf-8"))}
assert len(old) == 10_021
assert set(old) <= set(new)
for item_id, item in old.items():
    candidate = new[item_id]
    assert candidate["upgradedExpression"] == item["upgradedExpression"]
    assert candidate["level"] == item["level"]
    assert candidate["sortOrder"] == item["sortOrder"]
assert len(new) > len(old)
print({"old": len(old), "new": len(new), "added": len(new) - len(old)})
PY
```

Expected: all assertions pass and `added` is positive.

- [ ] **Step 3: Make the Swift bank test support a reviewed expansion**

Replace the four exact-count assertions in `testBundledSeedHasCompleteRichEntries` with stable expansion floors:

```swift
        XCTAssertGreaterThan(items.count, 10_021)
        XCTAssertGreaterThanOrEqual(items.filter { $0.level == .basic }.count, 1_588)
        XCTAssertGreaterThanOrEqual(items.filter { $0.level == .intermediate }.count, 2_983)
        XCTAssertGreaterThanOrEqual(items.filter { $0.level == .advanced }.count, 5_450)
```

The Python identity/source/accounting gates prove the exact generated set; XCTest continues to prove every bundled row decodes and satisfies the app contract.

- [ ] **Step 4: Update the source-and-level policy from the promoted data**

Obtain exact counts and catalog IDs:

```sh
python3 - <<'PY'
import json
from collections import Counter

seed = json.load(open("Vocaby/Resources/VocabularySeed.json", encoding="utf-8"))
provenance = json.load(open("Content/VocabularyProvenance.json", encoding="utf-8"))
counts = Counter(item["level"] for item in seed)
print("counts", {**dict(counts), "total": len(seed)})
print("sources", [source["id"] for source in provenance["sources"]])
print("bankVersion", provenance["bankVersion"])
PY
```

Use `apply_patch` to update `docs/question-bank-sources-and-levels.md` with the emitted exact level/total counts and these fixed policy changes:

- `Last reviewed: 2026-07-15`.
- 15 tracked external snapshots rather than fourteen.
- Add `grundwortschatz-voc-en-004977a` as approved English definition/example/CEFR evidence.
- Describe `freedict-eng-zho-2025.11.23` as aligned Chinese meaning fallback/corroboration used in this release.
- State that all 10 approved external sources contribute actual final evidence.
- Replace the maintainer workflow with `--all-available`, the dated ignored work root, and `run-local --workers 2` commands from Task 5.
- Replace stale 5,221-item acceptance text with the emitted final total and the preserved 10,021-item baseline.

- [ ] **Step 5: Run all Python release gates again**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tools -p 'test_*.py'
python3 tools/vocabulary_sources.py verify
python3 tools/vocabulary_sources.py audit-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-15.jsonl
git diff --check
```

Expected: all Python tests pass, 15 sources verify, the full review audits, and no whitespace error is reported.

- [ ] **Step 6: Run the full Swift test suite**

Run:

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath "$RUN/DerivedDataTests" \
  CODE_SIGNING_ALLOWED=NO
```

Expected: `** TEST SUCCEEDED **`, including complete rich-entry validation for the expanded bundled seed.

- [ ] **Step 7: Build Release and inspect the actual app bundle**

Run:

```sh
xcodebuild build \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -configuration Release \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath "$RUN/DerivedDataRelease" \
  CODE_SIGNING_ALLOWED=NO
APP="$RUN/DerivedDataRelease/Build/Products/Release-iphonesimulator/Vocaby.app"
test -f "$APP/VocabularySeed.json"
test -f "$APP/ThirdPartyNotices.txt"
test -z "$(find "$APP" -type f \( \
  -path '*/Content/Sources/*' -o \
  -path '*/Content/Reviews/*' -o \
  -name 'VocabularyProvenance.json' -o \
  -name 'source-manifest.json' \
\) -print -quit)"
```

Expected: `** BUILD SUCCEEDED **`; seed and notices exist; the forbidden-resource assertion prints nothing and exits zero.

- [ ] **Step 8: Review and commit only intentional final artifacts**

Run:

```sh
git status --short
git diff --check
git diff --stat
git diff -- \
  tools/vocabulary_sources.py \
  tools/review_vocabulary.py \
  tools/test_vocabulary_sources.py \
  tools/test_review_vocabulary.py \
  VocabyTests/VocabularySeedValidationTests.swift \
  docs/question-bank-sources-and-levels.md \
  docs/vocabulary-rejections-2026-07-15.md
```

Confirm ignored imports, work checkpoints, build products, and DerivedData are not staged. Then commit generated final artifacts:

```sh
git add \
  Content/Reviews/vocabulary-rich-2026-07-15.jsonl \
  Content/VocabularyProvenance.json \
  Vocaby/Resources/VocabularySeed.json \
  Vocaby/Resources/ThirdPartyNotices.txt \
  VocabyTests/VocabularySeedValidationTests.swift \
  docs/question-bank-sources-and-levels.md \
  docs/vocabulary-rejections-2026-07-15.md
git commit -m "content: expand approved vocabulary bank"
git status --short --branch
```

Expected: the branch is clean and ahead of `origin/main`; do not push unless the user asks.

---

## Final Verification Checklist

- [ ] Existing 10,021 IDs, levels, sort orders, and expressions are unchanged.
- [ ] At least one new eligible lesson is appended, and queue accounting covers every selected or rejected candidate.
- [ ] All ten approved external sources have actual final evidence; FreeDict has at least one legitimate final reference.
- [ ] No blocked ID occurs in final source references, validation IDs, catalog, or notices.
- [ ] Python tests, source verification, rich-review audit, deterministic double build, promotion validation, Swift tests, Release build, and bundle inspection all pass.
- [ ] Only seed and notices are bundled; raw/import/review/report/provenance content remains repository-only.
- [ ] The final worktree is clean after scoped commits and remains unpushed until explicitly requested.
