# 100,000-Lesson Content Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an indexed, source-traceable, fully reviewed 100,000-lesson bank from the current 15,336 deterministic baseline plus 84,664 new lessons, with one reviewed commit and push after every 20 ten-row batches.

**Architecture:** Extend the existing two Python pipeline modules at their shared boundaries. Approved raw sources still normalize through `tools/vocabulary_sources.py`; all draft generation, translation, resume, and review still route through `tools/review_vocabulary.py` and `tools/apple_language_services.swift`. Store the canonical reviewed result as one 15,336-row baseline shard plus 424 hash-indexed checkpoint shards instead of a single oversized JSONL file.

**Tech Stack:** Python 3 standard library and `unittest`, OpenCC, Apple NaturalLanguage, Apple Translation, Foundation Models, JSON/JSONL, SHA-256, existing Git/GitHub workflow.

## Global Constraints

- Preserve all original 14,064 IDs and complete the approved 15,336-row A/C/B quality baseline before adding new targets.
- Final reviewed count is exactly 100,000; draft, attempted, imported, or rejected rows do not count.
- Every approved row satisfies the rich lesson contract in the design spec.
- Only manifest sources with `appUse: approved` may contribute shipping fields.
- Exact CEFR wins; inferred CEFR requires method, evidence, confidence, reviewer, and A1-C2 mapping.
- Pronunciation must be verified; uncertain rows are replaced, never forced through.
- Batch size is 10. Review, commit, and push after every 20 completed batches and after the final partial boundary.
- Do not run two writers against the same review workspace.
- Do not add a per-source translator, example generator, reviewer, or promoter.
- Keep raw/import/report/review/provenance content out of the Xcode target.
- Run `git diff --check` before every commit.

---

## File Map

- `tools/vocabulary_sources.py`: Moby adapter, all-sense CEFR evidence, deterministic target selection, inferred-CEFR validation, reviewed-shard audit/index, and promotion input.
- `tools/test_vocabulary_sources.py`: source, target, CEFR, shard, rights, deterministic-selection, and cumulative-count tests.
- `tools/review_vocabulary.py`: all-sense requests, bounded 20-batch execution, validation, checkpoint shard construction, and resume fingerprints.
- `tools/test_review_vocabulary.py`: all-sense parity, bounded execution, checkpoint, retry, and final-partial tests.
- `tools/apple_language_services.swift`: existing local translation/enrichment helper; update the guided output only when the reviewed contract adds CEFR metadata.
- `Content/Sources/source-manifest.json`: Moby source and expanded Wiktextract target-snapshot identity.
- `Content/Sources/Raw/moby-pronunciator-ii/`: pinned pronunciation source and local public-domain evidence.
- `Content/Sources/Raw/wiktextract-en/`: expanded target-only snapshot of the pinned dump.
- `Content/Reviews/vocabulary-100k/index.json`: ordered reviewed-shard manifest.
- `Content/Reviews/vocabulary-100k/baseline-15336.jsonl`: repaired and promoted baseline.
- `Content/Reviews/vocabulary-100k/checkpoint-0001.jsonl` through `checkpoint-0424.jsonl`: reviewed expansion shards.
- `Content/VocabularyProvenance.json`: complete repository-only source and CEFR evidence.
- `Vocaby/Resources/ThirdPartyNotices.txt`: deterministic shipping notices.
- `docs/vocabulary-100k-progress.md`: generated boundary ledger and rejection accounting.
- `docs/question-bank-sources-and-levels.md`: final source policy and counts.

---

### Task 1: Freeze the Baseline and Add A/C/B Regression Tests

**Files:**
- Modify: `tools/test_review_vocabulary.py`
- Modify: `tools/test_vocabulary_sources.py`
- Create: `docs/vocabulary-100k-progress.md`

**Interfaces:**
- Consumes: current seed, provenance, notices, full deterministic queue, source manifest.
- Produces: frozen input hashes/counts and failing tests for all-sense enrichment, exact CEFR, and pronunciation completion.

- [ ] **Step 1: Record fresh baseline evidence**

Run:

```sh
python3 -B tools/vocabulary_sources.py verify
python3 -B tools/vocabulary_sources.py import-all
python3 -B tools/vocabulary_sources.py report
shasum -a 256 \
  Vocaby/Resources/VocabularySeed.json \
  Content/VocabularyProvenance.json \
  Vocaby/Resources/ThirdPartyNotices.txt \
  Content/Sources/source-manifest.json
```

Expected: all 15 existing source entries verify; report totals are 904,681 records and 583,652 unique headwords; the shipping seed contains 14,064 rows.

- [ ] **Step 2: Add the failing all-sense test**

Add to `tools/test_review_vocabulary.py`:

```python
def test_prepare_review_emits_every_selected_sense(self):
    packet = self.queue_packet()
    packet["candidateSenses"] = [
        {**packet["candidateSenses"][0], "id": "sense-1"},
        {**packet["candidateSenses"][0], "id": "sense-2"},
    ]

    requests = review_vocabulary.enrichment_requests(packet)

    self.assertEqual(
        [item["id"] for item in requests],
        [f'{packet["id"]}:sense-1', f'{packet["id"]}:sense-2'],
    )
```

- [ ] **Step 3: Add the failing exact-CEFR test**

Add to `tools/test_review_vocabulary.py`:

```python
def test_build_reviewed_preserves_packet_cefr(self):
    packet = self.complete_review_packet()
    packet["cefr"] = "A1"
    packet["level"] = "basic"

    reviewed = review_vocabulary.reviewed_item(packet, sort_order=1)

    self.assertEqual(reviewed["cefr"], "A1")
    self.assertEqual(reviewed["level"], "basic")
```

- [ ] **Step 4: Verify RED**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools.test_review_vocabulary.ReviewVocabularyTests.test_prepare_review_emits_every_selected_sense \
  tools.test_review_vocabulary.ReviewVocabularyTests.test_build_reviewed_preserves_packet_cefr
```

Expected: both tests fail because the current pipeline prepares only the first sense and hardcodes CEFR from App level.

- [ ] **Step 5: Commit the frozen baseline and tests**

```sh
git add tools/test_review_vocabulary.py tools/test_vocabulary_sources.py docs/vocabulary-100k-progress.md
git diff --cached --check
git commit -m "test: freeze 100k vocabulary baseline"
git push origin HEAD
```

---

### Task 2: Fix All-Sense Review and Exact CEFR Once

**Files:**
- Modify: `tools/review_vocabulary.py`
- Modify: `tools/vocabulary_sources.py`
- Modify: `tools/test_review_vocabulary.py`
- Modify: `tools/test_vocabulary_sources.py`

**Interfaces:**
- Produces: `enrichment_requests(packet: dict) -> list[dict]`, exact result-ID parity, and `reviewed_item(packet: dict, sort_order: int) -> dict` that preserves packet CEFR.

- [ ] **Step 1: Extract one request per sense**

Add:

```python
def enrichment_requests(packet: dict) -> list[dict]:
    return [
        {
            "id": f'{packet["id"]}:{sense["id"]}',
            "lessonID": packet["id"],
            "senseID": sense["id"],
            "target": packet["target"],
            "definition": sense["glosses"][0],
            "example": next(iter(sense.get("examples", [])), ""),
            "partOfSpeech": sense["partOfSpeech"],
        }
        for sense in packet["candidateSenses"][:3]
    ]
```

Use this helper from `prepare_review`; delete the primary-sense-only request construction.

- [ ] **Step 2: Reject incomplete or unexpected result IDs**

Before merging results:

```python
expected_ids = {
    request["id"]
    for packet in batches
    for request in enrichment_requests(packet)
}
actual_ids = {item["id"] for item in completed}
if actual_ids != expected_ids:
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    raise sources.SourceError(
        f"enrichment ID mismatch: missing={missing[:10]} extra={extra[:10]}"
    )
```

- [ ] **Step 3: Preserve exact CEFR and derive App level**

Replace level-wide CEFR constants with:

```python
cefr = packet["cefr"]
level = sources.CEFR_LEVEL.get(cefr)
if level is None:
    raise sources.SourceError(f'invalid CEFR for {packet["id"]}: {cefr}')
```

Reassign contiguous `sortOrder` per derived level using previous global order and ID as the final tie-breaker.

- [ ] **Step 4: Reject known generic templates**

Add:

```python
GENERIC_EXAMPLE_PATTERNS = (
    re.compile(r"^This example uses .+ in context\.$", re.IGNORECASE),
    re.compile(r"^Here is an example of .+\.$", re.IGNORECASE),
)


def validate_natural_example(value: str, target: str) -> None:
    if any(pattern.fullmatch(value.strip()) for pattern in GENERIC_EXAMPLE_PATTERNS):
        raise sources.SourceError(f"generic example for {target}")
    validate_enrichment({"example": value, "plainExpression": target}, target)
```

- [ ] **Step 5: Run the focused and complete review suites**

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools.test_review_vocabulary \
  tools.test_vocabulary_sources
```

Expected: all vocabulary pipeline tests pass.

- [ ] **Step 6: Commit and push**

```sh
git add tools/review_vocabulary.py tools/vocabulary_sources.py \
  tools/test_review_vocabulary.py tools/test_vocabulary_sources.py
git diff --cached --check
git commit -m "fix: review every vocabulary sense and exact CEFR"
git push origin HEAD
```

---

### Task 3: Add and Verify Moby Pronunciator II

**Files:**
- Modify: `tools/vocabulary_sources.py`
- Modify: `tools/test_vocabulary_sources.py`
- Modify: `Content/Sources/source-manifest.json`
- Create: `Content/Sources/Raw/moby-pronunciator-ii/mpron.txt`
- Create: `Content/Sources/Raw/moby-pronunciator-ii/source-page.html`
- Create: `Content/Sources/Raw/moby-pronunciator-ii/README.txt`

**Interfaces:**
- Produces: adapter `moby_pronunciator` and `parse_moby_pronunciator(path: Path, source_id: str) -> Iterable[dict]`.

- [ ] **Step 1: Write parser and unknown-symbol tests**

Add tests using a local two-line fixture:

```python
def test_moby_pronunciator_emits_verified_ipa(self):
    path = self.root / "mpron.txt"
    path.write_bytes(b"test tEst\nword w3rd\n")

    records = list(
        vocabulary_sources.parse_moby_pronunciator(path, "moby-test")
    )

    self.assertEqual(records[0]["headword"], "test")
    self.assertEqual(records[0]["pronunciations"][0]["notation"], "ipa")
    self.assertTrue(records[0]["pronunciations"][0]["value"])


def test_moby_pronunciator_rejects_unknown_notation(self):
    path = self.root / "mpron.txt"
    path.write_bytes(b"test t?st\n")

    with self.assertRaisesRegex(vocabulary_sources.SourceError, "unknown Moby"):
        list(vocabulary_sources.parse_moby_pronunciator(path, "moby-test"))
```

- [ ] **Step 2: Verify RED**

```sh
python3 -B -m unittest \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_moby_pronunciator_emits_verified_ipa \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_moby_pronunciator_rejects_unknown_notation
```

Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Implement the smallest documented converter**

Add `MOBY_PHONE_IPA`, a strict line splitter, optional POS-suffix parsing, underscore-to-space conversion, and a converter that raises on every unknown byte instead of guessing. Emit:

```python
{
    "notation": "ipa",
    "value": ipa,
    "speechLocale": "en-US",
    "region": "General",
    "tags": [],
}
```

Register `PARSERS["moby_pronunciator"] = parse_moby_pronunciator`.

- [ ] **Step 4: Download, hash, declare, and verify the pinned artifact**

```sh
mkdir -p Content/Sources/Raw/moby-pronunciator-ii
curl --fail --location \
  https://www.gutenberg.org/files/3205/files/mpron.txt \
  --output Content/Sources/Raw/moby-pronunciator-ii/mpron.txt
wc -c Content/Sources/Raw/moby-pronunciator-ii/mpron.txt
shasum -a 256 Content/Sources/Raw/moby-pronunciator-ii/mpron.txt
python3 -B tools/vocabulary_sources.py verify --source moby-pronunciator-ii-3205
python3 -B tools/vocabulary_sources.py import-source \
  moby-pronunciator-ii-3205 \
  --output Content/Sources/Imported/moby-pronunciator-ii-3205.jsonl
```

Expected bytes: 5,493,251. Expected SHA-256:
`55580c3b258873723fed33497fe3a438b26167370bbe016431b3fc65fea67f2d`.

- [ ] **Step 5: Run all source tests and commit**

```sh
python3 -B -m unittest tools.test_vocabulary_sources
git add tools/vocabulary_sources.py tools/test_vocabulary_sources.py \
  Content/Sources/source-manifest.json \
  Content/Sources/Raw/moby-pronunciator-ii
git diff --cached --check
git commit -m "feat: add Moby pronunciation source"
git push origin HEAD
```

---

### Task 4: Add Deterministic 100,000-Target Selection and CEFR Inference

**Files:**
- Modify: `tools/vocabulary_sources.py`
- Modify: `tools/test_vocabulary_sources.py`

**Interfaces:**
- Produces: `select_target_candidates(records: list[dict], retained: list[dict], target_count: int) -> list[dict]`.
- Produces: `cefr_evidence(candidate: dict) -> dict` with `value`, `method`, `evidence`, and `confidence`.
- Produces CLI: `prepare-100k --input-dir PATH --retained PATH --output PATH --reserve-count 10000`.

- [ ] **Step 1: Add deterministic selection tests**

```python
def test_select_target_candidates_preserves_retained_and_replaces_rejections(self):
    retained = [{"id": "stable-1", "upgradedExpression": "keep"}]
    records = [
        self.candidate("alpha", source_count=3, pronunciation=True),
        self.candidate("beta", source_count=2, pronunciation=False),
        self.candidate("gamma", source_count=2, pronunciation=True),
    ]

    selected = vocabulary_sources.select_target_candidates(
        records, retained, target_count=3
    )

    self.assertEqual(
        [item["upgradedExpression"] for item in selected],
        ["keep", "alpha", "gamma"],
    )
```

Add shuffled-input equality, proper-name/obsolete/duplicate rejection, exact-CEFR precedence, inferred-metadata completeness, and reserve-candidate tests.

- [ ] **Step 2: Verify RED**

```sh
python3 -B -m unittest \
  tools.test_vocabulary_sources.VocabularySourcesTests.test_select_target_candidates_preserves_retained_and_replaces_rejections
```

Expected: FAIL because `select_target_candidates` does not exist.

- [ ] **Step 3: Implement strict eligibility and stable scoring**

Use one tuple and no ranking framework:

```python
def candidate_score(candidate: dict) -> tuple:
    evidence = candidate["cefrEvidence"]
    return (
        CEFR_ORDER[evidence["value"]],
        0 if evidence["method"] == "exact" else 1,
        -len(candidate["validationSourceIDs"]),
        -candidate.get("approvedCorpusOccurrences", 0),
        normalized(candidate["target"]),
        candidate["sourceRefs"][0]["sourceEntryRef"],
    )
```

Filter unsupported tags, missing sense/POS/pronunciation, expressions longer than eight tokens, and retained duplicates before sorting.

- [ ] **Step 4: Implement reviewed inferred CEFR metadata**

Exact evidence returns `method: exact`. Otherwise require a review packet:

```python
{
    "value": proposed_cefr,
    "method": "inferred",
    "evidence": sorted(evidence_strings),
    "confidence": confidence,
    "reviewer": reviewer,
}
```

Reject missing reviewer/evidence, confidence below the accepted threshold, or CEFR/App-level mismatch.

- [ ] **Step 5: Run the complete source suite and commit**

```sh
python3 -B -m unittest tools.test_vocabulary_sources
git add tools/vocabulary_sources.py tools/test_vocabulary_sources.py
git diff --cached --check
git commit -m "feat: select traceable 100k vocabulary targets"
git push origin HEAD
```

---

### Task 5: Add Hash-Indexed Review Checkpoint Shards

**Files:**
- Modify: `tools/review_vocabulary.py`
- Modify: `tools/test_review_vocabulary.py`
- Modify: `tools/vocabulary_sources.py`
- Modify: `tools/test_vocabulary_sources.py`

**Interfaces:**
- Adds CLI flag `run-local --batch-limit 20`.
- Produces `write_review_checkpoint(work_dir: Path, review_dir: Path, checkpoint: int, final: bool = False) -> dict`.
- Produces `load_review_index(index_path: Path, expected_count: int) -> list[dict]`.

- [ ] **Step 1: Add bounded-run and checkpoint tests**

```python
def test_run_local_services_stops_after_twenty_pending_batches(self):
    self.write_batches(count=25)

    result = review_vocabulary.run_local_services(
        self.work, self.helper, workers=2, batch_limit=20
    )

    self.assertEqual(result["completedBatches"], 20)
    self.assertEqual(result["remainingBatches"], 5)
```

Add tests for a 200-row shard, the final 64-row shard, tampered hash, reordered index, duplicate ID across shards, and incomplete non-final shard.

- [ ] **Step 2: Verify RED**

```sh
python3 -B -m unittest \
  tools.test_review_vocabulary.ReviewVocabularyTests.test_run_local_services_stops_after_twenty_pending_batches
```

Expected: FAIL because `batch_limit` is not accepted.

- [ ] **Step 3: Bound only pending work**

After resume filtering:

```python
pending = pending[:batch_limit] if batch_limit is not None else pending
```

Do not truncate already completed output or renumber batch IDs.

- [ ] **Step 4: Write shard and index atomically**

The checkpoint writer validates exactly 200 rows unless `final=True`, writes
`checkpoint-NNNN.jsonl` through `sources.atomic_write`, computes SHA-256, then atomically rewrites `index.json` with:

```python
{
    "path": shard_path.name,
    "items": len(items),
    "sha256": sources.sha256(shard_path),
    "firstID": items[0]["id"],
    "lastID": items[-1]["id"],
    "cumulativeItems": previous_count + len(items),
    "status": "approved",
}
```

- [ ] **Step 5: Audit every indexed shard**

`load_review_index` must reject an unknown key, absolute/traversal path, missing file, hash/count/order mismatch, duplicate ID/expression, unapproved row, or cumulative-count mismatch.

- [ ] **Step 6: Run suites and commit**

```sh
python3 -B -m unittest tools.test_review_vocabulary tools.test_vocabulary_sources
git add tools/review_vocabulary.py tools/test_review_vocabulary.py \
  tools/vocabulary_sources.py tools/test_vocabulary_sources.py
git diff --cached --check
git commit -m "feat: checkpoint reviewed vocabulary shards"
git push origin HEAD
```

---

### Task 6: Complete and Commit the 15,336 Baseline

**Files:**
- Create: `Content/Reviews/vocabulary-100k/baseline-15336.jsonl`
- Create: `Content/Reviews/vocabulary-100k/index.json`
- Modify: `Content/VocabularyProvenance.json`
- Modify: `Vocaby/Resources/ThirdPartyNotices.txt`
- Modify: `docs/vocabulary-100k-progress.md`

**Interfaces:**
- Consumes: repaired all-sense queue and Moby-enhanced pronunciation imports.
- Produces: exact 15,336-row approved baseline shard with preserved IDs.

- [ ] **Step 1: Prepare the full baseline queue**

```sh
python3 -B tools/vocabulary_sources.py prepare-enrichment \
  --input-dir Content/Sources/Imported \
  --existing-seed Content/Baselines/legacy-90.json \
  --current-seed Vocaby/Resources/VocabularySeed.json \
  --output /tmp/vocabulary-baseline-15336.jsonl
python3 -B tools/review_vocabulary.py prepare \
  --queue /tmp/vocabulary-baseline-15336.jsonl \
  --cmudict Content/Sources/Imported/cmudict-7479086.jsonl \
  --work-dir /tmp/vocaby-baseline-15336 \
  --batch-size 10
```

- [ ] **Step 2: Process at most 20 new batches per boundary**

For each boundary:

```sh
python3 -B tools/review_vocabulary.py run-local \
  --work-dir /tmp/vocaby-baseline-15336 \
  --workers 2 \
  --batch-limit 20
python3 -B tools/review_vocabulary.py audit-boundary \
  --work-dir /tmp/vocaby-baseline-15336
git diff --check
```

Review the generated sample and zero-error report, update the progress ledger, commit, and push before the next boundary.

- [ ] **Step 3: Build and audit the baseline shard**

```sh
python3 -B tools/review_vocabulary.py build-reviewed \
  --work-dir /tmp/vocaby-baseline-15336 \
  --output Content/Reviews/vocabulary-100k/baseline-15336.jsonl \
  --rejection-report docs/vocabulary-rejections-2026-07-17.md
python3 -B tools/vocabulary_sources.py audit-reviewed \
  --input Content/Reviews/vocabulary-100k/baseline-15336.jsonl
```

Expected: 15,336 approved rows, original 14,064 IDs retained, no known generic example, and no missing pronunciation.

- [ ] **Step 4: Commit and push the baseline**

```sh
git add Content/Reviews/vocabulary-100k Content/VocabularyProvenance.json \
  Vocaby/Resources/ThirdPartyNotices.txt docs/vocabulary-100k-progress.md \
  docs/vocabulary-rejections-2026-07-17.md
git diff --cached --check
git commit -m "content: establish reviewed 15336 lesson baseline"
git push origin HEAD
```

---

### Task 7: Expand the Pinned Wiktextract Target Snapshot

**Files:**
- Modify: `Content/Sources/Raw/wiktextract-en/english-targets-2026-07-09.jsonl.gz`
- Modify: `Content/Sources/source-manifest.json`
- Modify: `tools/test_vocabulary_sources.py`

**Interfaces:**
- Consumes: retained 15,336 targets plus selected/reserve target queue.
- Produces: deterministic superset snapshot from the same pinned upstream extraction.

- [ ] **Step 1: Add retained-superset test**

The snapshot test must assert every old normalized target remains in the new target set and output rows are byte-deterministic regardless of target input order.

- [ ] **Step 2: Generate a seed-shaped temporary target file**

```sh
python3 -B tools/vocabulary_sources.py prepare-100k \
  --input-dir Content/Sources/Imported \
  --retained Content/Reviews/vocabulary-100k/baseline-15336.jsonl \
  --output /tmp/vocabulary-100k-targets.jsonl \
  --reserve-count 10000
python3 -B tools/vocabulary_sources.py targets-to-seed \
  --input /tmp/vocabulary-100k-targets.jsonl \
  --output /tmp/vocabulary-100k-target-seed.json
```

- [ ] **Step 3: Stream and verify the expanded snapshot**

```sh
python3 -B tools/vocabulary_sources.py snapshot-wiktextract \
  --source-url https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz \
  --seed /tmp/vocabulary-100k-target-seed.json \
  --output /tmp/english-targets-2026-07-09-expanded.jsonl.gz
python3 -B tools/vocabulary_sources.py verify --source wiktextract-en-2026-07-09
```

Before replacing the tracked file, record the official URL shown above, exact
bytes, SHA-256, row count, and retained-target reconciliation.

- [ ] **Step 4: Re-import twice and compare**

```sh
python3 -B tools/vocabulary_sources.py import-source \
  wiktextract-en-2026-07-09 --output /tmp/wiktextract-a.jsonl
python3 -B tools/vocabulary_sources.py import-source \
  wiktextract-en-2026-07-09 --output /tmp/wiktextract-b.jsonl
cmp /tmp/wiktextract-a.jsonl /tmp/wiktextract-b.jsonl
```

- [ ] **Step 5: Commit and push**

```sh
git add Content/Sources/Raw/wiktextract-en/english-targets-2026-07-09.jsonl.gz \
  Content/Sources/source-manifest.json tools/test_vocabulary_sources.py
git diff --cached --check
git commit -m "content: expand pinned Wiktextract targets"
git push origin HEAD
```

---

### Task 8: Run the 424 Expansion Checkpoints

**Files:**
- Create: `Content/Reviews/vocabulary-100k/checkpoint-0001.jsonl` through `checkpoint-0424.jsonl`
- Modify: `Content/Reviews/vocabulary-100k/index.json`
- Modify: `docs/vocabulary-100k-progress.md`

**Interfaces:**
- Consumes: deterministic target queue, approved imports, checkpointed Apple local services.
- Produces: 84,664 approved rows and exact cumulative total 100,000.

- [ ] **Step 1: Prepare one resumable expansion workspace**

```sh
python3 -B tools/vocabulary_sources.py prepare-100k \
  --input-dir Content/Sources/Imported \
  --retained Content/Reviews/vocabulary-100k/baseline-15336.jsonl \
  --output /tmp/vocabulary-100k-queue.jsonl \
  --reserve-count 10000
python3 -B tools/review_vocabulary.py prepare \
  --queue /tmp/vocabulary-100k-queue.jsonl \
  --cmudict Content/Sources/Imported/cmudict-7479086.jsonl \
  --work-dir /tmp/vocaby-100k-review \
  --batch-size 10
```

- [ ] **Step 2: Execute each complete boundary**

For checkpoint numbers 0001 through 0423, run this block once per boundary:

```sh
checkpoint="$(python3 -c 'import json; from pathlib import Path; data=json.loads(Path("Content/Reviews/vocabulary-100k/index.json").read_text()); print(1 + sum(item["path"].startswith("checkpoint-") for item in data["shards"]))')"
checkpoint_number="$(printf '%04d' "$checkpoint")"
expected_count="$((15336 + checkpoint * 200))"
python3 -B tools/review_vocabulary.py run-local \
  --work-dir /tmp/vocaby-100k-review \
  --workers 2 \
  --batch-limit 20
python3 -B tools/review_vocabulary.py write-checkpoint \
  --work-dir /tmp/vocaby-100k-review \
  --review-dir Content/Reviews/vocabulary-100k \
  --checkpoint "$checkpoint_number"
python3 -B tools/vocabulary_sources.py audit-review-index \
  --index Content/Reviews/vocabulary-100k/index.json \
  --expected-count "$expected_count"
python3 -B -m unittest tools.test_review_vocabulary tools.test_vocabulary_sources
git diff --check
```

Review the deterministic sample and rejection report, then:

```sh
git add Content/Reviews/vocabulary-100k docs/vocabulary-100k-progress.md
git diff --cached --check
git commit -m "content: review vocabulary checkpoint $checkpoint_number"
git push origin HEAD
```

Do not start the next 20 batches until the push succeeds.

- [ ] **Step 3: Execute the final partial boundary**

```sh
python3 -B tools/review_vocabulary.py run-local \
  --work-dir /tmp/vocaby-100k-review \
  --workers 2 \
  --batch-limit 7
python3 -B tools/review_vocabulary.py write-checkpoint \
  --work-dir /tmp/vocaby-100k-review \
  --review-dir Content/Reviews/vocabulary-100k \
  --checkpoint 0424 \
  --final
python3 -B tools/vocabulary_sources.py audit-review-index \
  --index Content/Reviews/vocabulary-100k/index.json \
  --expected-count 100000
```

Expected final shard count: 64. Expected cumulative count: 100,000.

- [ ] **Step 4: Review, commit, and push the final boundary**

```sh
python3 -B -m unittest tools.test_review_vocabulary tools.test_vocabulary_sources
git diff --check
git add Content/Reviews/vocabulary-100k docs/vocabulary-100k-progress.md
git diff --cached --check
git commit -m "content: complete 100000 reviewed vocabulary lessons"
git push origin HEAD
```

---

### Task 9: Build Final Provenance, Notices, and Policy Evidence

**Files:**
- Modify: `Content/VocabularyProvenance.json`
- Modify: `Vocaby/Resources/ThirdPartyNotices.txt`
- Modify: `docs/question-bank-sources-and-levels.md`
- Modify: `docs/content-review.md`
- Modify: `docs/vocabulary-100k-progress.md`

**Interfaces:**
- Consumes: complete reviewed index.
- Produces: one-to-one 100,000-row provenance and final source/notices documentation for the SQLite compiler.

- [ ] **Step 1: Build twice**

```sh
mkdir -p /tmp/vocaby-100k-a /tmp/vocaby-100k-b
python3 -B tools/vocabulary_sources.py build-review-index \
  --index Content/Reviews/vocabulary-100k/index.json \
  --provenance-output /tmp/vocaby-100k-a/VocabularyProvenance.json \
  --notices-output /tmp/vocaby-100k-a/ThirdPartyNotices.txt
python3 -B tools/vocabulary_sources.py build-review-index \
  --index Content/Reviews/vocabulary-100k/index.json \
  --provenance-output /tmp/vocaby-100k-b/VocabularyProvenance.json \
  --notices-output /tmp/vocaby-100k-b/ThirdPartyNotices.txt
cmp /tmp/vocaby-100k-a/VocabularyProvenance.json \
  /tmp/vocaby-100k-b/VocabularyProvenance.json
cmp /tmp/vocaby-100k-a/ThirdPartyNotices.txt \
  /tmp/vocaby-100k-b/ThirdPartyNotices.txt
```

- [ ] **Step 2: Promote repository-only evidence atomically**

Replace provenance and notices together only after deterministic comparison and exact 100,000 ID parity pass.

- [ ] **Step 3: Run final content gates**

```sh
python3 -B tools/vocabulary_sources.py verify
python3 -B tools/vocabulary_sources.py audit-review-index \
  --index Content/Reviews/vocabulary-100k/index.json \
  --expected-count 100000
python3 -B -m unittest discover -s tools -p 'test_*.py'
git diff --check
```

- [ ] **Step 4: Commit and push**

```sh
git add Content/VocabularyProvenance.json \
  Vocaby/Resources/ThirdPartyNotices.txt \
  docs/question-bank-sources-and-levels.md docs/content-review.md \
  docs/vocabulary-100k-progress.md
git diff --cached --check
git commit -m "content: finalize 100000 lesson evidence"
git push origin HEAD
```

Expected: content pipeline complete with exact 100,000 reviewed IDs, valid rights/notices, and no unresolved rejection counted as approved.
