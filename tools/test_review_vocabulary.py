import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from tools import review_vocabulary


class ReviewVocabularyTests(unittest.TestCase):
    def _reviewed_items(self, count: int) -> list[dict]:
        items = []
        for index in range(count):
            target = f"checkpoint-target-{index:04d}"
            items.append(
                {
                    "id": f"checkpoint-{index:04d}",
                    "level": "basic",
                    "sortOrder": index + 1,
                    "contentLanguageCode": "en",
                    "supportLanguageCodes": ["zh-Hant"],
                    "plainExpression": f"plain-{index:04d}",
                    "upgradedExpression": target,
                    "primarySenseID": f"sense-{index:04d}",
                    "pronunciations": [
                        {
                            "id": f"pronunciation-us-{index:04d}",
                            "ipa": "tɛst",
                            "speechLocale": "en-US",
                            "region": "US",
                        }
                    ],
                    "senses": [
                        {
                            "id": f"sense-{index:04d}",
                            "partOfSpeech": "noun",
                            "meaning": {
                                "en": f"Meaning {index}.",
                                "zh-Hant": f"意思 {index}。",
                            },
                            "example": {
                                "text": f"This {target} works.",
                                "translation": {"zh-Hant": f"這個詞 {index} 可以使用。"},
                            },
                            "pronunciationIDs": [f"pronunciation-us-{index:04d}"],
                        }
                    ],
                    "quiz": {
                        "prompt": {
                            "en": "Which expression is correct?",
                            "zh-Hant": "哪個詞正確？",
                        },
                        "options": [
                            target,
                            f"wrong-a-{index:04d}",
                            f"wrong-b-{index:04d}",
                            f"wrong-c-{index:04d}",
                        ],
                        "correctOptionIndex": 0,
                    },
                    "sourceRefs": [
                        {"sourceID": "source", "sourceEntryRef": target}
                    ],
                    "validationSourceIDs": ["source"],
                    "cefr": "A2",
                    "reviewStatus": "approved",
                    "englishReviewer": "reviewer",
                    "zhHantReviewer": "reviewer",
                }
            )
        return items

    def _write_enrichment_fixture(self, work: Path) -> tuple[dict, dict]:
        item = {
            "id": "bank-basic-0001::sense-1",
            "target": "excellent",
            "partOfSpeech": "adjective",
            "meaning": "extremely good",
            "plainCandidates": ["very good"],
            "exampleCandidate": "",
        }
        batch = {"batchID": "0000", "items": [item]}
        (work / "enrichment-input.jsonl").write_text(
            json.dumps(batch) + "\n", encoding="utf-8"
        )
        draft = {
            "packet": {
                "id": "bank-basic-0001",
                "target": "excellent",
                "plain": "very good",
                "candidatePlainExpressions": ["very good"],
            },
            "senses": [
                {
                    "id": "sense-1",
                    "partOfSpeech": "adjective",
                    "exampleCandidate": "She made an excellent choice",
                }
            ],
        }
        (work / "draft.jsonl").write_text(
            json.dumps(draft) + "\n", encoding="utf-8"
        )
        return batch, draft

    def _write_translation_checkpoint(
        self, work: Path, swift_source: Path, text: str = "text"
    ) -> tuple[Path, Path]:
        swift_source.write_text("// helper v1\n", encoding="utf-8")
        input_path = work / "translation-input.jsonl"
        input_path.write_text(
            json.dumps({"id": "segment-001", "text": text}) + "\n",
            encoding="utf-8",
        )
        (work / "translation-output.jsonl").write_text(
            json.dumps({"id": "segment-001", "text": "stale"}) + "\n",
            encoding="utf-8",
        )
        fingerprint_path = work / "translation-output.fingerprint.json"
        fingerprint_path.write_text(
            json.dumps(
                {
                    "inputSHA256": review_vocabulary.sources.sha256(input_path),
                    "swiftSourceSHA256": review_vocabulary.sources.sha256(swift_source),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return input_path, fingerprint_path

    def test_run_helper_reports_a_timeout(self):
        with mock.patch.object(
            review_vocabulary.subprocess,
            "run",
            side_effect=review_vocabulary.subprocess.TimeoutExpired(["helper", "enrich"], 180),
        ):
            with self.assertRaisesRegex(
                review_vocabulary.sources.SourceError, "timed out"
            ):
                review_vocabulary.run_helper(Path("/tmp/helper"), "enrich", "{}\n")

    def test_run_local_enrichment_uses_input_fallback_after_three_invalid_singleton_outputs(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch, _draft = self._write_enrichment_fixture(work)
            calls = []

            def helper(_executable, _mode, payload):
                request = json.loads(payload)
                calls.append(request)
                return json.dumps(
                    {
                        "batchID": request["batchID"],
                        "items": [
                            {
                                "id": "wrong-id",
                                "plainExpression": "very good",
                                "example": "She made an excellent choice.",
                            }
                        ],
                    }
                ) + "\n"

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ):
                result = review_vocabulary.run_local_enrichment(
                    work, root / "helper.swift", 1
                )

            self.assertEqual(result, {"batches": 1, "completed": 1, "processed": 1})
            self.assertEqual(len(calls), 3)
            output = review_vocabulary.sources.read_jsonl(
                work / "enrichment-output.jsonl"
            )
            self.assertEqual(
                [item["id"] for item in output[0]["items"]],
                [batch["items"][0]["id"]],
            )
            review_vocabulary.validate_enrichment(
                output[0]["items"][0], batch["items"][0]["target"]
            )

    def test_run_local_enrichment_fails_closed_when_invalid_singleton_fallback_is_invalid(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch = {
                "batchID": "0000",
                "items": [
                    {
                        "id": "bank-basic-0001::sense-1",
                        "target": "excellent",
                        "partOfSpeech": "",
                        "meaning": "extremely good",
                        "plainCandidates": ["very good"],
                        "exampleCandidate": "",
                    }
                ],
            }
            (work / "enrichment-input.jsonl").write_text(
                json.dumps(batch) + "\n", encoding="utf-8"
            )
            calls = []

            def helper(_executable, _mode, payload):
                request = json.loads(payload)
                calls.append(request)
                return json.dumps(
                    {
                        "batchID": request["batchID"],
                        "items": [
                            {
                                "id": "wrong-id",
                                "plainExpression": "very good",
                                "example": "She made an excellent choice.",
                            }
                        ],
                    }
                ) + "\n"

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ):
                with self.assertRaisesRegex(
                    review_vocabulary.sources.SourceError,
                    "invalid deterministic safety fallback",
                ):
                    review_vocabulary.run_local_enrichment(
                        work, root / "helper.swift", 1
                    )

            self.assertEqual(len(calls), 3)
            output = work / "enrichment-output.jsonl"
            self.assertFalse(
                output.exists() and review_vocabulary.sources.read_jsonl(output)
            )

    def test_run_local_enrichment_propagates_unrelated_generation_error_without_retry(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            self._write_enrichment_fixture(work)
            calls = []

            def helper(_executable, _mode, payload):
                calls.append(json.loads(payload))
                raise review_vocabulary.sources.SourceError(
                    "Apple enrich failed: "
                    "FoundationModels.LanguageModelSession.GenerationError error -1"
                )

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ):
                with self.assertRaisesRegex(
                    review_vocabulary.sources.SourceError,
                    "GenerationError error -1",
                ):
                    review_vocabulary.run_local_enrichment(
                        work, root / "helper.swift", 1
                    )

            self.assertEqual(len(calls), 1)
            output = work / "enrichment-output.jsonl"
            self.assertFalse(
                output.exists() and review_vocabulary.sources.read_jsonl(output)
            )

    def test_run_local_enrichment_uses_input_fallback_after_safety_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch = {
                "batchID": "0000",
                "items": [
                    {
                        "id": "bank-basic-0001::sense-1",
                        "target": "excellent",
                        "partOfSpeech": "adjective",
                        "meaning": "extremely good",
                        "plainCandidates": ["very good"],
                        "exampleCandidate": "She made an excellent choice",
                    },
                    {
                        "id": "bank-basic-0002::sense-1",
                        "target": "murder",
                        "partOfSpeech": "noun",
                        "meaning": "unlawful killing",
                        "plainCandidates": [],
                        "exampleCandidate": "The detective investigated the murder",
                    },
                ],
            }
            (work / "enrichment-input.jsonl").write_text(
                json.dumps(batch) + "\n", encoding="utf-8"
            )
            calls = []

            def helper(_executable, _mode, payload):
                calls.append(json.loads(payload))
                raise review_vocabulary.sources.SourceError(
                    "Apple enrich failed: error: Detected content likely to be unsafe"
                )

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ):
                result = review_vocabulary.run_local_enrichment(
                    work, root / "helper.swift", 1
                )

            self.assertEqual(result, {"batches": 1, "completed": 1, "processed": 1})
            self.assertEqual(len(calls), 1)
            output = review_vocabulary.sources.read_jsonl(
                work / "enrichment-output.jsonl"
            )
            self.assertEqual(
                output,
                [
                    {
                        "batchID": "0000",
                        "items": [
                            {
                                "id": "bank-basic-0001::sense-1",
                                "plainExpression": "very good",
                                "example": "She made an excellent choice.",
                            },
                            {
                                "id": "bank-basic-0002::sense-1",
                                "plainExpression": "unlawful killing",
                                "example": "The detective investigated the murder.",
                            },
                        ],
                    }
                ],
            )
            for item, input_item in zip(
                output[0]["items"], batch["items"], strict=True
            ):
                review_vocabulary.validate_enrichment(item, input_item["target"])

    def test_run_local_enrichment_fails_closed_when_safety_fallback_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch = {
                "batchID": "0000",
                "items": [
                    {
                        "id": "bank-basic-0001::sense-1",
                        "target": "murder",
                        "partOfSpeech": "",
                        "meaning": "unlawful killing",
                        "plainCandidates": [],
                        "exampleCandidate": "",
                    }
                ],
            }
            (work / "enrichment-input.jsonl").write_text(
                json.dumps(batch) + "\n", encoding="utf-8"
            )
            calls = []

            def helper(_executable, _mode, payload):
                calls.append(json.loads(payload))
                raise review_vocabulary.sources.SourceError(
                    "Apple enrich failed: error: Detected content likely to be unsafe"
                )

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ):
                with self.assertRaisesRegex(
                    review_vocabulary.sources.SourceError,
                    "invalid deterministic safety fallback",
                ):
                    review_vocabulary.run_local_enrichment(
                        work, root / "helper.swift", 1
                    )

            self.assertEqual(len(calls), 1)
            output = work / "enrichment-output.jsonl"
            self.assertFalse(output.exists() and review_vocabulary.sources.read_jsonl(output))

    def test_run_local_enrichment_retries_a_transient_invalid_singleton_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch, _draft = self._write_enrichment_fixture(work)
            calls = []

            def helper(_executable, _mode, payload):
                request = json.loads(payload)
                calls.append(request)
                item_id = (
                    "wrong-id"
                    if len(calls) == 1
                    else request["items"][0]["id"]
                )
                return json.dumps(
                    {
                        "batchID": request["batchID"],
                        "items": [
                            {
                                "id": item_id,
                                "plainExpression": "very good",
                                "example": "She made an excellent choice.",
                            }
                        ],
                    }
                ) + "\n"

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ):
                result = review_vocabulary.run_local_enrichment(
                    work, root / "helper.swift", 1
                )

            self.assertEqual(result, {"batches": 1, "completed": 1, "processed": 1})
            self.assertEqual(len(calls), 2)
            self.assertEqual(
                review_vocabulary.sources.read_jsonl(
                    work / "enrichment-output.jsonl"
                )[0]["items"][0]["id"],
                batch["items"][0]["id"],
            )

    def test_run_local_enrichment_repairs_invalid_plain_and_example(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch, _draft = self._write_enrichment_fixture(work)
            invalid = {
                "batchID": batch["batchID"],
                "items": [
                    {
                        "id": batch["items"][0]["id"],
                        "plainExpression": "excellent",
                        "example": "Not a sentence",
                    }
                ],
            }

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary,
                "run_helper",
                return_value=json.dumps(invalid) + "\n",
            ):
                result = review_vocabulary.run_local_enrichment(
                    work, root / "helper.swift", 1
                )

            self.assertEqual(result, {"batches": 1, "completed": 1, "processed": 1})
            output = review_vocabulary.sources.read_jsonl(
                work / "enrichment-output.jsonl"
            )
            self.assertEqual(output[0]["items"][0]["plainExpression"], "very good")
            self.assertEqual(
                output[0]["items"][0]["example"],
                "She made an excellent choice.",
            )

    def test_run_local_enrichment_rejects_invalid_saved_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch, _draft = self._write_enrichment_fixture(work)
            (work / "enrichment-output.jsonl").write_text(
                json.dumps(
                    {
                        "batchID": batch["batchID"],
                        "items": [
                            {
                                "id": batch["items"][0]["id"],
                                "plainExpression": "excellent",
                                "example": "broken",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ) as compile_helper:
                with self.assertRaisesRegex(
                    review_vocabulary.sources.SourceError,
                    "invalid saved enrichment batch",
                ):
                    review_vocabulary.run_local_enrichment(
                        work, root / "helper.swift", 1
                    )

            compile_helper.assert_not_called()

    def test_enrich_local_processes_exactly_twenty_batches_without_finishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batches = [
                {"batchID": f"{index:04d}", "items": []}
                for index in range(25)
            ]
            (work / "enrichment-input.jsonl").write_text(
                "".join(json.dumps(batch) + "\n" for batch in batches),
                encoding="utf-8",
            )

            def helper(_executable, mode, payload):
                self.assertEqual(mode, "enrich")
                return payload

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ), mock.patch.object(
                review_vocabulary,
                "finish_enrichment",
                side_effect=AssertionError("must not finish enrichment"),
            ), mock.patch.object(
                review_vocabulary,
                "run_local_translation",
                side_effect=AssertionError("must not translate"),
            ):
                exit_code = review_vocabulary.main(
                    [
                        "enrich-local",
                        "--work-dir",
                        str(work),
                        "--swift-source",
                        str(root / "helper.swift"),
                        "--workers",
                        "2",
                        "--max-batches",
                        "20",
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                [
                    batch["batchID"]
                    for batch in review_vocabulary.sources.read_jsonl(
                        work / "enrichment-output.jsonl"
                    )
                ],
                [f"{index:04d}" for index in range(20)],
            )

    def test_run_local_services_resumes_completed_enrichment_batches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batches = [
                {"batchID": "batch-1", "items": []},
                {"batchID": "batch-2", "items": []},
            ]
            (work / "enrichment-input.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in batches), encoding="utf-8"
            )
            completed = {"batchID": "batch-1", "items": []}
            (work / "enrichment-output.jsonl").write_text(
                json.dumps(completed) + "\n", encoding="utf-8"
            )
            calls = []

            def helper(_executable, mode, payload):
                calls.append((mode, payload))
                if mode == "enrich":
                    batch = json.loads(payload)
                    return json.dumps({"batchID": batch["batchID"], "items": []}) + "\n"
                return ""

            def finish(output_work):
                self.assertEqual(
                    [item["batchID"] for item in review_vocabulary.sources.read_jsonl(output_work / "enrichment-output.jsonl")],
                    ["batch-1", "batch-2"],
                )
                (output_work / "translation-input.jsonl").write_text("", encoding="utf-8")
                return {"items": 2, "translations": 0}

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
            self.assertEqual(
                [json.loads(payload)["batchID"] for mode, payload in calls if mode == "enrich"],
                ["batch-2"],
            )

    def test_run_local_services_stops_after_twenty_pending_batches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batches = [
                {"batchID": f"{index:04d}", "items": []}
                for index in range(25)
            ]
            (work / "enrichment-input.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in batches),
                encoding="utf-8",
            )

            def helper(_executable, _mode, payload):
                batch = json.loads(payload)
                return json.dumps({"batchID": batch["batchID"], "items": []}) + "\n"

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ), mock.patch.object(
                review_vocabulary,
                "finish_enrichment",
                return_value={"items": 200, "translations": 400},
            ) as finish, mock.patch.object(
                review_vocabulary, "run_local_translation", return_value=400
            ) as translate:
                result = review_vocabulary.run_local_services(
                    work,
                    root / "helper.swift",
                    workers=2,
                    batch_limit=20,
                )

            self.assertEqual(result["completedBatches"], 20)
            self.assertEqual(result["remainingBatches"], 5)
            self.assertEqual(result["items"], 200)
            finish.assert_called_once_with(work, allow_partial=True)
            translate.assert_called_once_with(work, root / "helper.swift", 2)

    def test_write_review_checkpoint_writes_hashed_200_and_final_64_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            review_dir = root / "reviews"
            work.mkdir()
            items = self._reviewed_items(264)
            reviewed_path = work / "reviewed.jsonl"

            def build_first(_work, output, _report, **_kwargs):
                output.write_text(
                    "".join(json.dumps(item) + "\n" for item in items[:200]),
                    encoding="utf-8",
                )
                return {"items": 200}

            with mock.patch.object(
                review_vocabulary, "build_reviewed", side_effect=build_first
            ):
                first = review_vocabulary.write_review_checkpoint(
                    work, review_dir, checkpoint=1
                )

            self.assertEqual(first["items"], 200)
            self.assertEqual(first["cumulativeItems"], 200)
            self.assertEqual(
                first["sha256"],
                review_vocabulary.sources.sha256(review_dir / first["path"]),
            )

            def build_all(_work, output, _report, **_kwargs):
                output.write_text(
                    "".join(json.dumps(item) + "\n" for item in items),
                    encoding="utf-8",
                )
                return {"items": 264}

            with mock.patch.object(
                review_vocabulary, "build_reviewed", side_effect=build_all
            ):
                final = review_vocabulary.write_review_checkpoint(
                    work, review_dir, checkpoint=2, final=True
                )

            self.assertEqual(final["items"], 64)
            self.assertEqual(final["cumulativeItems"], 264)
            self.assertEqual(
                len(
                    review_vocabulary.sources.load_review_index(
                        review_dir / "index.json", 264
                    )
                ),
                264,
            )

    def test_run_local_services_chunks_enrichment_helper_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch = {
                "batchID": "batch-1",
                "items": [
                    {"id": f"item-{index:02d}", "target": "excellent"}
                    for index in range(20)
                ],
            }
            enriched_batch = {
                "batchID": "batch-1",
                "items": [
                    {
                        "id": item["id"],
                        "plainExpression": "very good",
                        "example": "This excellent choice works well.",
                    }
                    for item in batch["items"]
                ],
            }
            (work / "enrichment-input.jsonl").write_text(
                json.dumps(batch) + "\n", encoding="utf-8"
            )
            calls = []

            def helper(_executable, mode, payload):
                self.assertEqual(mode, "enrich")
                chunk = json.loads(payload)
                calls.append(chunk)
                return json.dumps(
                    {
                        "batchID": chunk["batchID"],
                        "items": [
                            {
                                "id": item["id"],
                                "plainExpression": "very good",
                                "example": "This excellent choice works well.",
                            }
                            for item in chunk["items"]
                        ],
                    }
                ) + "\n"

            def finish(output_work):
                output = review_vocabulary.sources.read_jsonl(
                    output_work / "enrichment-output.jsonl"
                )
                self.assertEqual(output, [enriched_batch])
                return {"items": 20, "translations": 0}

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ), mock.patch.object(
                review_vocabulary, "finish_enrichment", side_effect=finish
            ), mock.patch.object(
                review_vocabulary, "run_local_translation", return_value=0
            ):
                result = review_vocabulary.run_local_services(
                    work, root / "helper.swift", 2
                )

            self.assertEqual(result["items"], 20)
            self.assertEqual([len(chunk["items"]) for chunk in calls], [10, 10])

    def test_run_local_services_splits_failed_or_incomplete_enrichment_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batch = {
                "batchID": "batch-1",
                "items": [
                    {"id": f"item-{index:02d}", "target": "excellent"}
                    for index in range(20)
                ],
            }
            enriched_batch = {
                "batchID": "batch-1",
                "items": [
                    {
                        "id": item["id"],
                        "plainExpression": "very good",
                        "example": "This excellent choice works well.",
                    }
                    for item in batch["items"]
                ],
            }
            (work / "enrichment-input.jsonl").write_text(
                json.dumps(batch) + "\n", encoding="utf-8"
            )
            calls = []

            def helper(_executable, _mode, payload):
                chunk = json.loads(payload)
                calls.append(json.loads(payload))
                if len(chunk["items"]) == 10 and chunk["items"][0]["id"] == "item-00":
                    raise review_vocabulary.sources.SourceError(
                        "Exceeded model context window size"
                    )
                if len(chunk["items"]) == 5 and chunk["items"][0]["id"] == "item-00":
                    chunk["items"] = chunk["items"][:-1]
                return json.dumps(
                    {
                        "batchID": chunk["batchID"],
                        "items": [
                            {
                                "id": item["id"],
                                "plainExpression": "very good",
                                "example": "This excellent choice works well.",
                            }
                            for item in chunk["items"]
                        ],
                    }
                ) + "\n"

            def finish(output_work):
                self.assertEqual(
                    review_vocabulary.sources.read_jsonl(
                        output_work / "enrichment-output.jsonl"
                    ),
                    [enriched_batch],
                )
                return {"items": 20, "translations": 0}

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ), mock.patch.object(
                review_vocabulary, "finish_enrichment", side_effect=finish
            ), mock.patch.object(
                review_vocabulary, "run_local_translation", return_value=0
            ):
                review_vocabulary.run_local_services(
                    work, root / "helper.swift", 2
                )

            self.assertEqual(
                [len(chunk["items"]) for chunk in calls], [10, 5, 2, 3, 5, 10]
            )

    def test_run_local_services_cancels_queued_batches_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            batches = [
                {"batchID": f"batch-{index:03d}", "items": []}
                for index in range(50)
            ]
            (work / "enrichment-input.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in batches),
                encoding="utf-8",
            )
            calls = []

            def helper(_executable, _mode, payload):
                batch = json.loads(payload)
                calls.append(batch["batchID"])
                if batch["batchID"] == "batch-000":
                    raise review_vocabulary.sources.SourceError("failed")
                time.sleep(0.02)
                return json.dumps({"batchID": batch["batchID"], "items": []}) + "\n"

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ):
                with self.assertRaisesRegex(
                    review_vocabulary.sources.SourceError,
                    "Apple enrich failed for batch batch-000",
                ):
                    review_vocabulary.run_local_services(
                        work, root / "helper.swift", 1
                    )

            self.assertLess(len(calls), len(batches))

    def test_run_local_translation_resumes_parallel_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            swift_source = root / "helper.swift"
            swift_source.write_text("// helper v1\n", encoding="utf-8")
            requests = [
                {"id": f"segment-{index:03d}", "text": "text"}
                for index in range(401)
            ]
            input_path = work / "translation-input.jsonl"
            input_path.write_text(
                "".join(json.dumps(item) + "\n" for item in requests),
                encoding="utf-8",
            )
            (work / "translation-output.jsonl").write_text(
                json.dumps({"id": "segment-000", "text": "done"}) + "\n",
                encoding="utf-8",
            )
            (work / "translation-output.fingerprint.json").write_text(
                json.dumps(
                    {
                        "inputSHA256": review_vocabulary.sources.sha256(input_path),
                        "swiftSourceSHA256": review_vocabulary.sources.sha256(
                            swift_source
                        ),
                    }
                )
                + "\n",
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
                    work, swift_source, 2
                )

            self.assertEqual(count, 401)
            self.assertEqual(len(calls), 4)
            self.assertTrue(all(len(chunk) <= 100 for chunk in calls))
            self.assertNotIn("segment-000", set().union(*calls))
            completed = review_vocabulary.sources.read_jsonl(
                work / "translation-output.jsonl"
            )
            self.assertEqual(
                {item["id"] for item in completed},
                {item["id"] for item in requests},
            )

    def test_run_local_translation_limits_parallel_chunks_to_100_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            swift_source = root / "helper.swift"
            swift_source.write_text("// helper v1\n", encoding="utf-8")
            requests = [
                {"id": f"segment-{index:03d}", "text": "text"}
                for index in range(205)
            ]
            (work / "translation-input.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in requests),
                encoding="utf-8",
            )
            chunk_sizes = []

            def helper(_executable, mode, payload):
                self.assertEqual(mode, "translate")
                chunk = [json.loads(line) for line in payload.splitlines()]
                chunk_sizes.append(len(chunk))
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
                    work, swift_source, 2
                )

            self.assertEqual(count, len(requests))
            self.assertEqual(sorted(chunk_sizes), [5, 100, 100])

    def test_run_local_translation_cancels_queued_chunks_after_helper_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            swift_source = root / "helper.swift"
            swift_source.write_text("// helper v1\n", encoding="utf-8")
            requests = [
                {"id": f"segment-{index:04d}", "text": "text"}
                for index in range(1001)
            ]
            input_path = work / "translation-input.jsonl"
            input_path.write_text(
                "".join(json.dumps(item) + "\n" for item in requests),
                encoding="utf-8",
            )
            saved = {"id": "segment-0000", "text": "checkpointed"}
            (work / "translation-output.jsonl").write_text(
                json.dumps(saved) + "\n", encoding="utf-8"
            )
            (work / "translation-output.fingerprint.json").write_text(
                json.dumps(
                    {
                        "inputSHA256": review_vocabulary.sources.sha256(input_path),
                        "swiftSourceSHA256": review_vocabulary.sources.sha256(
                            swift_source
                        ),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            calls = []
            calls_lock = threading.Lock()
            second_started = threading.Event()
            release_helpers = threading.Event()
            release_timer = threading.Timer(0.6, release_helpers.set)
            release_timer.daemon = True

            def helper(_executable, mode, payload):
                self.assertEqual(mode, "translate")
                chunk = [json.loads(line) for line in payload.splitlines()]
                with calls_lock:
                    calls.append(chunk[0]["id"])
                    ordinal = len(calls)
                if ordinal == 1:
                    self.assertTrue(second_started.wait(timeout=0.2))
                    raise review_vocabulary.sources.SourceError("failed helper")
                second_started.set()
                self.assertTrue(release_helpers.wait(timeout=1.0))
                return "".join(
                    json.dumps({"id": item["id"], "text": "translated"}) + "\n"
                    for item in chunk
                )

            release_timer.start()
            started = time.monotonic()
            try:
                with mock.patch.object(
                    review_vocabulary, "compile_apple_helper"
                ), mock.patch.object(
                    review_vocabulary, "run_helper", side_effect=helper
                ):
                    with self.assertRaisesRegex(
                        review_vocabulary.sources.SourceError, "failed helper"
                    ):
                        review_vocabulary.run_local_translation(
                            work, swift_source, 2
                        )
            finally:
                elapsed = time.monotonic() - started
                release_helpers.set()
                release_timer.cancel()

            time.sleep(0.05)
            self.assertLess(elapsed, 0.3)
            self.assertLess(len(calls), 5)
            self.assertEqual(
                review_vocabulary.sources.read_jsonl(
                    work / "translation-output.jsonl"
                ),
                [saved],
            )

    def test_run_local_translation_recomputes_when_queue_content_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            swift_source = root / "helper.swift"
            input_path, fingerprint_path = self._write_translation_checkpoint(
                work, swift_source, "old"
            )
            input_path.write_text(
                json.dumps({"id": "segment-001", "text": "changed"}) + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary,
                "run_helper",
                return_value=json.dumps(
                    {"id": "segment-001", "text": "fresh"}
                )
                + "\n",
            ) as helper:
                review_vocabulary.run_local_translation(work, swift_source, 2)

            helper.assert_called_once()
            self.assertEqual(
                review_vocabulary.sources.read_jsonl(
                    work / "translation-output.jsonl"
                ),
                [{"id": "segment-001", "text": "fresh"}],
            )
            self.assertEqual(
                json.loads(fingerprint_path.read_text(encoding="utf-8")),
                {
                    "inputSHA256": review_vocabulary.sources.sha256(input_path),
                    "swiftSourceSHA256": review_vocabulary.sources.sha256(
                        swift_source
                    ),
                },
            )

    def test_run_local_translation_reuses_unchanged_rows_when_queue_grows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            swift_source = root / "helper.swift"
            swift_source.write_text("// helper v1\n", encoding="utf-8")
            input_path = work / "translation-input.jsonl"
            input_path.write_text(
                json.dumps({"id": "segment-001", "text": "first"}) + "\n",
                encoding="utf-8",
            )

            def helper(_executable, _mode, payload):
                requests = [json.loads(line) for line in payload.splitlines()]
                return "".join(
                    json.dumps({"id": item["id"], "text": f"zh:{item['text']}"})
                    + "\n"
                    for item in requests
                )

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ) as first_helper:
                review_vocabulary.run_local_translation(work, swift_source, 2)
            self.assertEqual(first_helper.call_count, 1)

            input_path.write_text(
                "".join(
                    json.dumps(item) + "\n"
                    for item in (
                        {"id": "segment-001", "text": "first"},
                        {"id": "segment-002", "text": "second"},
                    )
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary, "run_helper", side_effect=helper
            ) as second_helper:
                review_vocabulary.run_local_translation(work, swift_source, 2)

            payload = second_helper.call_args.args[2]
            self.assertIn("segment-002", payload)
            self.assertNotIn("segment-001", payload)

    def test_run_local_translation_recomputes_when_swift_helper_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            swift_source = root / "helper.swift"
            input_path, fingerprint_path = self._write_translation_checkpoint(
                work, swift_source
            )
            swift_source.write_text("// helper v2\n", encoding="utf-8")

            with mock.patch.object(
                review_vocabulary, "compile_apple_helper"
            ), mock.patch.object(
                review_vocabulary,
                "run_helper",
                return_value=json.dumps(
                    {"id": "segment-001", "text": "fresh"}
                )
                + "\n",
            ) as helper:
                review_vocabulary.run_local_translation(work, swift_source, 2)

            helper.assert_called_once()
            self.assertEqual(
                review_vocabulary.sources.read_jsonl(
                    work / "translation-output.jsonl"
                ),
                [{"id": "segment-001", "text": "fresh"}],
            )
            self.assertEqual(
                json.loads(fingerprint_path.read_text(encoding="utf-8")),
                {
                    "inputSHA256": review_vocabulary.sources.sha256(input_path),
                    "swiftSourceSHA256": review_vocabulary.sources.sha256(
                        swift_source
                    ),
                },
            )

    def test_run_local_translation_recomputes_without_a_valid_fingerprint(self):
        for saved_fingerprint in (None, "not json\n"):
            with self.subTest(saved_fingerprint=saved_fingerprint):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    work = root / "work"
                    work.mkdir()
                    swift_source = root / "helper.swift"
                    _, fingerprint_path = self._write_translation_checkpoint(
                        work, swift_source
                    )
                    if saved_fingerprint is None:
                        fingerprint_path.unlink()
                    else:
                        fingerprint_path.write_text(
                            saved_fingerprint, encoding="utf-8"
                        )

                    with mock.patch.object(
                        review_vocabulary, "compile_apple_helper"
                    ), mock.patch.object(
                        review_vocabulary,
                        "run_helper",
                        return_value=json.dumps(
                            {"id": "segment-001", "text": "fresh"}
                        )
                        + "\n",
                    ) as helper:
                        review_vocabulary.run_local_translation(
                            work, swift_source, 2
                        )

                    helper.assert_called_once()
                    self.assertEqual(
                        review_vocabulary.sources.read_jsonl(
                            work / "translation-output.jsonl"
                        ),
                        [{"id": "segment-001", "text": "fresh"}],
                    )

    def test_run_local_translation_rejects_a_missing_swift_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            swift_source = root / "helper.swift"
            self._write_translation_checkpoint(work, swift_source)
            swift_source.unlink()

            with self.assertRaisesRegex(
                review_vocabulary.sources.SourceError, "missing Swift helper"
            ):
                review_vocabulary.run_local_translation(work, swift_source, 2)

    def test_run_local_translation_rejects_incomplete_parallel_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            swift_source = root / "helper.swift"
            swift_source.write_text("// helper v1\n", encoding="utf-8")
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
                        work, swift_source, 2
                    )

            self.assertFalse((work / "translation-output.jsonl").exists())

    def test_validate_enrichment_requires_the_target_in_a_full_sentence(self):
        item = {
            "id": "bank-basic-0001::sense-1",
            "plainExpression": "very good",
            "example": "The idea was very good.",
        }

        with self.assertRaisesRegex(
            review_vocabulary.sources.SourceError, "must use target"
        ):
            review_vocabulary.validate_enrichment(item, "excellent")

    def test_validate_enrichment_rejects_generic_examples(self):
        with self.assertRaisesRegex(
            review_vocabulary.sources.SourceError, "generic example"
        ):
            review_vocabulary.validate_enrichment(
                {
                    "plainExpression": "very good",
                    "example": "This example uses excellent in context.",
                },
                "excellent",
            )

    def test_fallback_plain_expression_is_concise_and_not_the_target(self):
        packet = {
            "target": "about",
            "plain": "(of quantities) imprecise but fairly close to correct",
            "definition": "(of quantities) imprecise but fairly close to correct",
            "candidatePlainExpressions": ["roughly", "almost"],
        }

        self.assertEqual(
            review_vocabulary.fallback_plain(packet),
            "imprecise but fairly close to correct",
        )

    def test_source_example_wraps_a_fragment_as_a_complete_teaching_sentence(self):
        self.assertEqual(
            review_vocabulary.source_example(
                "Italian",
                {
                    "partOfSpeech": "adjective",
                    "exampleCandidate": "Italian cooking",
                },
            ),
            "The phrase “Italian cooking” shows how Italian is used in context.",
        )
        self.assertEqual(
            review_vocabulary.source_example(
                "zip",
                {
                    "partOfSpeech": "noun",
                    "exampleCandidate": "He's full of zip.",
                },
            ),
            "He's full of zip.",
        )

    def test_wrapped_example_translation_preserves_the_learning_phrase(self):
        self.assertEqual(
            review_vocabulary.wrapped_example_translation(
                "The phrase “Italian cooking” shows how Italian is used in context."
            ),
            "「Italian cooking」這個片語顯示 Italian 在語境中的用法。",
        )

    def test_example_translation_fallback_is_a_clear_usage_hint(self):
        self.assertEqual(
            review_vocabulary.example_translation_fallback("Italian"),
            "這個例句示範「Italian」的用法。",
        )

    def test_prepare_review_rejects_only_items_without_verified_pronunciation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = root / "queue.jsonl"
            cmu = root / "cmu.jsonl"
            work = root / "work"
            base = {
                "level": "basic",
                "sortOrder": 1,
                "plain": "very good",
                "definition": "of very high quality",
                "example": "She shared an excellent idea.",
                "translationDraft": "非常好",
                "exampleTranslationDraft": "她分享了一個很棒的想法。",
                "partOfSpeech": "a",
                "cefr": "A2",
                "sourceRefs": [
                    {"sourceID": "oewn-2025", "sourceEntryRef": "excellent#a#1"}
                ],
                "validationSourceIDs": ["oewn-2025"],
                "candidatePlainExpressions": ["very good"],
                "candidateSenses": [],
                "issues": [],
            }
            accepted = {
                **base,
                "id": "bank-basic-0001",
                "target": "excellent",
                "candidatePronunciations": [
                    {
                        "notation": "ipa",
                        "value": "ˈɛksələnt",
                        "speechLocale": "en-US",
                        "region": "US",
                        "sourceRef": {
                            "sourceID": "oewn-2025",
                            "sourceEntryRef": "excellent#a#1",
                        },
                    }
                ],
            }
            rejected = {
                **base,
                "id": "bank-basic-0002",
                "sortOrder": 2,
                "target": "unpronounceable",
                "candidatePronunciations": [],
            }
            queue.write_text(
                "".join(json.dumps(item) + "\n" for item in (accepted, rejected)),
                encoding="utf-8",
            )
            cmu.write_text("", encoding="utf-8")

            result = review_vocabulary.prepare_review(queue, cmu, work, batch_size=10)

            self.assertEqual(result, {"accepted": 1, "rejected": 1, "senses": 1})
            draft = json.loads((work / "draft.jsonl").read_text())
            self.assertEqual(draft["pronunciations"][0]["ipa"], "ˈɛksələnt")
            rejection = json.loads((work / "rejections.jsonl").read_text())
            self.assertEqual(rejection["reason"], "no-verified-pronunciation")
            self.assertEqual(rejection["sourceIDs"], ["oewn-2025"])
            batch = json.loads((work / "enrichment-input.jsonl").read_text())
            self.assertEqual(batch["items"][0]["id"], "bank-basic-0001::bank-basic-0001-sense-1")

    def test_prepare_review_emits_every_selected_sense(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = root / "queue.jsonl"
            cmu = root / "cmu.jsonl"
            work = root / "work"
            source_ref = {
                "sourceID": "oewn-2025",
                "sourceEntryRef": "excellent#a#1",
            }
            packet = {
                "id": "bank-basic-0001",
                "level": "basic",
                "sortOrder": 1,
                "target": "excellent",
                "plain": "very good",
                "definition": "of very high quality",
                "example": "She shared an excellent idea.",
                "partOfSpeech": "adjective",
                "cefr": "A2",
                "sourceRefs": [source_ref],
                "validationSourceIDs": ["oewn-2025"],
                "candidatePlainExpressions": ["very good"],
                "candidatePronunciations": [
                    {
                        "notation": "ipa",
                        "value": "ˈɛksələnt",
                        "speechLocale": "en-US",
                        "region": "US",
                        "sourceRef": source_ref,
                    }
                ],
                "candidateSenses": [
                    {
                        "id": "sense-1",
                        "partOfSpeech": "adjective",
                        "glosses": ["of very high quality"],
                        "examples": ["She shared an excellent idea."],
                        "tags": [],
                        "sourceRef": source_ref,
                    },
                    {
                        "id": "sense-2",
                        "partOfSpeech": "noun",
                        "glosses": ["a person or thing of outstanding quality"],
                        "examples": ["The award recognizes excellence."],
                        "tags": [],
                        "sourceRef": {
                            "sourceID": "oewn-2025",
                            "sourceEntryRef": "excellent#n#2",
                        },
                    },
                ],
                "issues": [],
            }
            queue.write_text(json.dumps(packet) + "\n", encoding="utf-8")
            cmu.write_text("", encoding="utf-8")

            review_vocabulary.prepare_review(queue, cmu, work)

            requests = json.loads((work / "enrichment-input.jsonl").read_text())[
                "items"
            ]
            self.assertEqual(
                [item["id"] for item in requests],
                ["bank-basic-0001::sense-1", "bank-basic-0001::sense-2"],
            )

    def test_prepare_review_batches_ten_lessons_even_with_multiple_senses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = root / "queue.jsonl"
            cmu = root / "cmu.jsonl"
            work = root / "work"
            packets = []
            for index in range(11):
                target = f"target-{index}"
                source_ref = {
                    "sourceID": "oewn-test",
                    "sourceEntryRef": target,
                }
                packets.append(
                    {
                        "id": f"item-{index}",
                        "level": "basic",
                        "sortOrder": index + 1,
                        "target": target,
                        "plain": f"plain {index}",
                        "definition": f"meaning {index}",
                        "example": f"The {target} works.",
                        "partOfSpeech": "noun",
                        "cefr": "A2",
                        "sourceRefs": [source_ref],
                        "validationSourceIDs": ["oewn-test"],
                        "candidatePlainExpressions": [f"plain {index}"],
                        "candidatePronunciations": [
                            {
                                "notation": "ipa",
                                "value": "tɛst",
                                "speechLocale": "en-US",
                                "region": "US",
                                "sourceRef": source_ref,
                            }
                        ],
                        "candidateSenses": [
                            {
                                "id": f"sense-{sense}",
                                "partOfSpeech": "noun" if sense == 0 else "verb",
                                "glosses": [f"meaning {index} sense {sense}"],
                                "examples": [f"The {target} works."],
                                "tags": [],
                                "sourceRef": source_ref,
                            }
                            for sense in range(2)
                        ],
                    }
                )
            queue.write_text(
                "".join(json.dumps(item) + "\n" for item in packets),
                encoding="utf-8",
            )
            cmu.write_text("", encoding="utf-8")

            review_vocabulary.prepare_review(queue, cmu, work, batch_size=10)

            batches = review_vocabulary.sources.read_jsonl(
                work / "enrichment-input.jsonl"
            )
            self.assertEqual([len(batch["items"]) for batch in batches], [20, 2])

    def test_build_reviewed_preserves_packet_cefr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            source_ref = {
                "sourceID": "oewn-2025",
                "sourceEntryRef": "excellent#a#1",
            }
            draft = {
                "packet": {
                    "id": "bank-basic-0001",
                    "level": "advanced",
                    "sortOrder": 1,
                    "target": "excellent",
                    "cefr": "A1",
                    "sourceRefs": [source_ref],
                    "validationSourceIDs": ["oewn-2025"],
                },
                "pronunciations": [
                    {
                        "id": "bank-basic-0001-pronunciation-us",
                        "ipa": "ˈɛksələnt",
                        "speechLocale": "en-US",
                        "region": "US",
                    }
                ],
                "pronunciationSourceRefs": [source_ref],
                "senses": [
                    {
                        "id": "sense-1",
                        "partOfSpeech": "adjective",
                        "meaning": "of very high quality",
                        "sourceRef": source_ref,
                    }
                ],
                "enrichment": {
                    "sense-1": {
                        "plainExpression": "very good",
                        "example": "She shared an excellent idea.",
                    }
                },
            }
            (work / "enriched.jsonl").write_text(
                json.dumps(draft) + "\n", encoding="utf-8"
            )
            (work / "translation-output.jsonl").write_text(
                "".join(
                    json.dumps(item) + "\n"
                    for item in (
                        {
                            "id": "bank-basic-0001::sense-1::meaning",
                            "text": "品質非常好。",
                        },
                        {
                            "id": "bank-basic-0001::sense-1::example",
                            "text": "她分享了一個很棒的想法。",
                        },
                    )
                ),
                encoding="utf-8",
            )
            (work / "rejections.jsonl").write_text("", encoding="utf-8")
            output = root / "reviewed.jsonl"

            with mock.patch.object(
                review_vocabulary.sources,
                "traditionalize",
                side_effect=lambda values: values,
            ), mock.patch.object(
                review_vocabulary.sources,
                "audit_reviewed",
                return_value={"items": 1},
            ):
                review_vocabulary.build_reviewed(
                    work, output, root / "rejections.md"
                )

            reviewed = json.loads(output.read_text())
            self.assertEqual(reviewed["cefr"], "A1")
            self.assertEqual(reviewed["level"], "basic")

    def test_finish_enrichment_reconciles_every_sense_id(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            draft = {
                "packet": {"id": "bank-basic-0001", "target": "excellent"},
                "senses": [
                    {
                        "id": "sense-1",
                        "meaning": "of very high quality",
                        "partOfSpeech": "adjective",
                        "exampleCandidate": "She shared an excellent idea.",
                    },
                    {
                        "id": "sense-2",
                        "meaning": "a person or thing of outstanding quality",
                        "partOfSpeech": "noun",
                        "exampleCandidate": "The excellent result surprised us.",
                    },
                ],
            }
            (work / "draft.jsonl").write_text(
                json.dumps(draft) + "\n", encoding="utf-8"
            )
            (work / "enrichment-output.jsonl").write_text(
                json.dumps(
                    {
                        "batchID": "0000",
                        "items": [
                            {
                                "id": "bank-basic-0001::sense-1",
                                "plainExpression": "very good",
                                "example": "She shared an excellent idea.",
                            },
                            {
                                "id": "bank-basic-0001::sense-2",
                                "plainExpression": "outstanding example",
                                "example": "The excellent result surprised us.",
                            },
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = review_vocabulary.finish_enrichment(work)

            self.assertEqual(result, {"items": 1, "translations": 4})
            enriched = json.loads((work / "enriched.jsonl").read_text())
            self.assertEqual(
                sorted(enriched["enrichment"]), ["sense-1", "sense-2"]
            )

    def test_finish_enrichment_accepts_only_complete_partial_lessons(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            drafts = [
                {
                    "packet": {"id": f"item-{index}", "target": f"target-{index}"},
                    "senses": [
                        {
                            "id": "sense-1",
                            "meaning": f"meaning {index}",
                            "partOfSpeech": "noun",
                            "exampleCandidate": f"The target-{index} works.",
                        }
                    ],
                }
                for index in range(2)
            ]
            (work / "draft.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in drafts),
                encoding="utf-8",
            )
            (work / "enrichment-output.jsonl").write_text(
                json.dumps(
                    {
                        "batchID": "0000",
                        "items": [
                            {
                                "id": "item-0::sense-1",
                                "plainExpression": "plain zero",
                                "example": "The target-0 works.",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = review_vocabulary.finish_enrichment(
                work, allow_partial=True
            )

            self.assertEqual(result, {"items": 1, "translations": 2})
            enriched = review_vocabulary.sources.read_jsonl(
                work / "enriched.jsonl"
            )
            self.assertEqual(enriched[0]["packet"]["id"], "item-0")

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


if __name__ == "__main__":
    unittest.main()
