import bz2
import gzip
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import vocabulary_sources


SCRIPT = Path(__file__).with_name("vocabulary_sources.py")
SIMILARITY_SCRIPT = Path(__file__).with_name("definition_similarity.swift")
ROOT = Path(__file__).resolve().parents[1]


class VocabularySourcesTests(unittest.TestCase):
    def target_candidate(
        self,
        target: str,
        *,
        utility: str = "general",
        frequency_rank: int = 100,
        source_count: int = 2,
        cefr: str = "B2",
        cefr_method: str = "exact",
        tags: list[str] | None = None,
        proper_name: bool = False,
    ) -> dict:
        source_refs = [
            {"sourceID": f"source-{index}", "sourceEntryRef": f"{target}-{index}"}
            for index in range(source_count)
        ]
        evidence = {
            "method": "exact",
            "evidence": [f"source:{target}"],
            "confidence": 1.0,
            "reviewer": "source",
        }
        candidate = {
            "target": target,
            "candidateSenses": [
                {
                    "id": f"{target}-sense-1",
                    "partOfSpeech": "noun",
                    "glosses": [f"meaning of {target}"],
                    "tags": tags or [],
                    "sourceRef": source_refs[0],
                }
            ],
            "candidatePronunciations": [
                {
                    "notation": "ipa",
                    "value": "tɛst",
                    "speechLocale": "en-US",
                    "region": "General",
                    "sourceRef": source_refs[-1],
                }
            ],
            "validationSourceIDs": [ref["sourceID"] for ref in source_refs],
            "sourceRefs": source_refs,
            "learnerUtility": utility,
            "learnerUtilityEvidence": evidence,
            "approvedFrequencyRank": frequency_rank,
            "approvedCorpusOccurrences": max(0, 1_000 - frequency_rank),
            "isProperName": proper_name,
        }
        if cefr_method == "exact":
            candidate["exactCEFREvidence"] = [
                {"value": cefr, "sourceRef": source_refs[0]}
            ]
        else:
            candidate["inferredCEFR"] = {
                "value": cefr,
                "evidence": ["reviewed Taiwan learner rubric"],
                "confidence": 0.9,
                "reviewer": "codex-content-review-2026-07-17",
            }
        return candidate

    def test_select_target_candidates_preserves_retained_and_uses_utility(self):
        retained = [
            {
                "id": "stable-1",
                "upgradedExpression": "keep",
                "level": "basic",
                "sortOrder": 1,
                "cefr": "A1",
            }
        ]
        records = [
            self.target_candidate("specialist", utility="specialized", source_count=5),
            self.target_candidate("invoice", utility="business", source_count=2),
            self.target_candidate("breakfast", utility="everyday", source_count=2),
        ]

        selected = vocabulary_sources.select_target_candidates(
            records, retained, target_count=3
        )

        self.assertEqual(
            [item["target"] for item in selected],
            ["keep", "breakfast", "invoice"],
        )

    def test_select_target_candidates_orders_practical_domains_before_general(self):
        records = [
            self.target_candidate("general", utility="general", frequency_rank=1),
            self.target_candidate("daily", utility="everyday", frequency_rank=100),
            self.target_candidate("business", utility="business", frequency_rank=100),
            self.target_candidate("travel", utility="travel", frequency_rank=100),
            self.target_candidate("life", utility="practical-life", frequency_rank=100),
            self.target_candidate("technical", utility="specialized", frequency_rank=1),
        ]

        selected = vocabulary_sources.select_target_candidates(
            list(reversed(records)), [], target_count=len(records)
        )

        self.assertEqual(
            [item["target"] for item in selected],
            ["daily", "business", "travel", "life", "general", "technical"],
        )

    def test_select_target_candidates_is_deterministic_and_filters_invalid_rows(self):
        valid = self.target_candidate("alpha", utility="everyday")
        duplicate = self.target_candidate("ALPHA", utility="business")
        proper_name = self.target_candidate("London", proper_name=True)
        obsolete = self.target_candidate("forsooth", tags=["obsolete"])
        records = [proper_name, duplicate, obsolete, valid]

        first = vocabulary_sources.select_target_candidates(records, [], 1)
        second = vocabulary_sources.select_target_candidates(
            list(reversed(records)), [], 1
        )

        self.assertEqual(first, second)
        self.assertEqual([item["target"] for item in first], ["alpha"])

    def test_cefr_evidence_prefers_exact_and_requires_reviewed_inference(self):
        exact = self.target_candidate("exact", cefr="A2")
        inferred = self.target_candidate(
            "inferred", cefr="C1", cefr_method="inferred"
        )

        self.assertEqual(
            vocabulary_sources.cefr_evidence(exact)["method"], "exact"
        )
        self.assertEqual(
            vocabulary_sources.cefr_evidence(inferred),
            {
                "value": "C1",
                "method": "inferred",
                "evidence": ["reviewed Taiwan learner rubric"],
                "confidence": 0.9,
                "reviewer": "codex-content-review-2026-07-17",
            },
        )
        inferred["inferredCEFR"]["reviewer"] = ""
        with self.assertRaisesRegex(
            vocabulary_sources.SourceError, "reviewed inferred CEFR"
        ):
            vocabulary_sources.cefr_evidence(inferred)

    def test_prepare_100k_builds_target_and_reserve_queue_from_approved_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()
            retained = root / "retained.jsonl"
            retained.write_text(
                json.dumps(
                    {
                        "id": "stable-1",
                        "upgradedExpression": "keep",
                        "level": "basic",
                        "sortOrder": 1,
                        "cefr": "A1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            def canonical(
                target: str,
                source_id: str,
                *,
                definition: str = "",
                pronunciation: str = "",
                cefr: str | None = None,
            ) -> dict:
                return {
                    "headword": target,
                    "sourceID": source_id,
                    "sourceEntryRef": f"{source_id}:{target}",
                    "partOfSpeech": "noun",
                    "definitions": [definition] if definition else [],
                    "examples": [],
                    "senses": [],
                    "pronunciations": (
                        [
                            {
                                "notation": "ipa",
                                "value": pronunciation,
                                "speechLocale": "en-US",
                                "region": "General",
                                "tags": [],
                            }
                        ]
                        if pronunciation
                        else []
                    ),
                    "cefr": cefr,
                }

            rows = [
                canonical("technical", "lex", definition="specialized knowledge"),
                canonical("invoice", "lex", definition="a business payment request"),
                canonical("breakfast", "lex", definition="the first daily meal"),
                canonical("technical", "pron", pronunciation="ˈtɛknɪkəl"),
                canonical("invoice", "pron", pronunciation="ˈɪnvɔɪs"),
                canonical("breakfast", "pron", pronunciation="ˈbrɛkfəst"),
                canonical("technical", "cefr", cefr="C2"),
                canonical("invoice", "cefr", cefr="B1"),
                canonical("breakfast", "cefr", cefr="A1"),
            ]
            for source_id in ("lex", "pron", "cefr"):
                selected = [row for row in rows if row["sourceID"] == source_id]
                (input_dir / f"{source_id}.jsonl").write_text(
                    "".join(
                        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                        for row in reversed(selected)
                    ),
                    encoding="utf-8",
                )
            (input_dir / "corpus.jsonl").write_text(
                json.dumps(
                    canonical(
                        "I eat breakfast before work.",
                        "corpus",
                    ),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            output = root / "queue.jsonl"

            result = vocabulary_sources.prepare_100k(
                input_dir,
                retained,
                output,
                {"lex", "pron", "cefr", "corpus"},
                target_count=2,
                reserve_count=1,
                corpus_source_ids={"corpus"},
            )
            queue = vocabulary_sources.read_jsonl(output)

            self.assertEqual(result, {"retained": 1, "target": 1, "reserve": 1})
            self.assertEqual(
                [(item["target"], item["selectionStatus"]) for item in queue],
                [("breakfast", "target"), ("invoice", "reserve")],
            )
            self.assertEqual(queue[0]["learnerUtility"], "everyday")
            self.assertEqual(queue[1]["learnerUtility"], "business")
            self.assertEqual(queue[0]["level"], "basic")
            self.assertEqual(queue[1]["level"], "intermediate")
            self.assertEqual(queue[0]["approvedCorpusOccurrences"], 1)
            self.assertEqual(
                queue[1]["learnerUtilityEvidence"]["method"], "inferred"
            )

    def test_frozen_100k_baseline_inputs(self):
        expected_hashes = {
            "Vocaby/Resources/VocabularySeed.json": "0fad7a08386e7b9448448ce8dc2144dd6571d0614594a9c049d0e1147bb541d9",
            "Content/VocabularyProvenance.json": "eacf3d158eec48fab86f437e74975f3feff55145427201d8a3d8bfc7aa45188f",
            "Vocaby/Resources/ThirdPartyNotices.txt": "3f152459c424d7451fc08c3ea65f17e7d368d335bd78a93afda2307408e55d5c",
            "Content/Sources/source-manifest.json": "91302e0632d29d24f402bc67b7009cf180983a98f73c55e67191cd60616a3261",
        }

        for relative_path, expected_hash in expected_hashes.items():
            self.assertEqual(
                vocabulary_sources.sha256(ROOT / relative_path), expected_hash
            )
        self.assertEqual(
            len(json.loads((ROOT / "Vocaby/Resources/VocabularySeed.json").read_text())),
            14_064,
        )
        self.assertEqual(
            len(
                json.loads(
                    (ROOT / "Content/Sources/source-manifest.json").read_text()
                )["sources"]
            ),
            16,
        )

    def test_moby_pronunciator_emits_verified_ipa_and_pos(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mpron.txt"
            path.write_bytes(
                b"test t/E/st\r\n"
                b"word w/@/rd\r\n"
                b"close/v kl/oU/z\r\n"
                b"business_trip 'b/I/zn/@/s_tr/I/p\r\n"
            )

            records = list(
                vocabulary_sources.parse_moby_pronunciator(path, "moby-test")
            )

            self.assertEqual(
                [record["headword"] for record in records],
                ["test", "word", "close", "business trip"],
            )
            self.assertEqual(records[2]["partOfSpeech"], "verb")
            self.assertEqual(
                [record["pronunciations"][0]["value"] for record in records],
                ["tɛst", "wəɹd", "kloʊz", "ˈbɪznəs tɹɪp"],
            )
            self.assertTrue(
                all(
                    record["pronunciations"][0]["notation"] == "ipa"
                    for record in records
                )
            )

    def test_moby_pronunciator_rejects_unknown_notation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mpron.txt"
            path.write_bytes(b"test t/?/st\r\n")

            with self.assertRaisesRegex(
                vocabulary_sources.SourceError, "unknown Moby"
            ):
                list(
                    vocabulary_sources.parse_moby_pronunciator(
                        path, "moby-test"
                    )
                )

    def test_moby_pronunciator_skips_only_documented_source_anomalies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mpron.txt"
            path.write_bytes(
                b"antivivisectionist ,/&/nt/I/,v/I/v/@/'s/E/ksh(/@/)n/@/st\r\n"
                b"test t/E/st\r\n"
            )

            records = list(
                vocabulary_sources.parse_moby_pronunciator(
                    path, "moby-pronunciator-ii-3205"
                )
            )

            self.assertEqual([record["headword"] for record in records], ["test"])

    def test_validate_seed_record_rejects_pronunciation_region_id_mismatch(self):
        record = {
            "id": "basic-0001",
            "level": "basic",
            "sortOrder": 1,
            "cefr": "A1",
            "contentLanguageCode": "en",
            "supportLanguageCodes": ["zh-Hant"],
            "plainExpression": "ask for",
            "upgradedExpression": "request",
            "primarySenseID": "basic-0001-sense-1",
            "pronunciations": [{
                "id": "request-us-1",
                "ipa": "ɹɪˈkwɛst",
                "speechLocale": "en-US",
                "region": "General",
            }],
            "senses": [{
                "id": "basic-0001-sense-1",
                "partOfSpeech": "verb",
                "pronunciationIDs": ["request-us-1"],
                "meaning": {"en": "Ask for something.", "zh-Hant": "要求某事物。"},
                "example": {
                    "text": "I request a receipt.",
                    "translation": {"zh-Hant": "我要求一張收據。"},
                },
            }],
            "quiz": {
                "prompt": {"en": "Choose request.", "zh-Hant": "選出 request。"},
                "options": ["ask", "request", "say", "tell"],
                "correctOptionIndex": 1,
            },
            "reviewStatus": "approved",
            "englishReviewer": "test",
            "zhHantReviewer": "test",
            "sourceRefs": [{"sourceID": "test-source", "sourceEntryRef": "request"}],
        }

        with self.assertRaisesRegex(vocabulary_sources.SourceError, "inconsistent pronunciation"):
            vocabulary_sources.validate_seed_item(record)

    def test_grundwortschatz_sqlite_gzip_adapter_keeps_cefr_and_grade_six_advanced_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "words.db"
            connection = sqlite3.connect(database)
            connection.execute(
                "CREATE TABLE words (original_id TEXT, word TEXT, lemma TEXT, word_type TEXT, grade_level INTEGER, enrichment_json TEXT, metadata_json TEXT)"
            )
            connection.executemany(
                "INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        "word_en_00001",
                        "add",
                        "add",
                        "verb",
                        2,
                        json.dumps({"definitions": ["To join or combine."], "examples": ["Add the numbers."]}),
                        json.dumps({
                            "cefr_level": "A1",
                            "pronunciation": {"ipa": "æd"},
                            "gutenberg_examples": ["We add the numbers."],
                        }),
                    ),
                    (
                        "word_en_00002",
                        "moraine",
                        "moraine",
                        "noun",
                        6,
                        json.dumps({"definitions": ["A glacial deposit."]}),
                        json.dumps({"gradeLevelEstimate": 6}),
                    ),
                ],
            )
            connection.commit()
            connection.close()
            source = Path(directory) / "words.db.gz"
            with database.open("rb") as input_stream, gzip.open(source, "wb") as output_stream:
                output_stream.write(input_stream.read())

            records = list(vocabulary_sources.parse_grundwortschatz_sqlite_gzip(source, "grundwortschatz-voc-en"))

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["headword"], "add")
        self.assertEqual(records[0]["cefr"], "A1")
        self.assertEqual(records[0]["definitions"], ["To join or combine."])
        self.assertEqual(records[0]["examples"], ["Add the numbers.", "We add the numbers."])
        self.assertEqual(records[0]["pronunciations"][0]["value"], "æd")
        self.assertEqual(records[1]["headword"], "moraine")
        self.assertEqual(records[1]["cefr"], "C1")

    def test_bare_ipa_selects_one_reading_from_wiktextract_variants(self):
        cases = {
            "/t͡ʃæns/[t͡ʃʰæns]": "t͡ʃæns",
            "ˈæk.tʰɚ]~[ˈæk.tʰɹ̩": "ˈæk.tʰɚ",
            "[ˈʍɪi̯l]~/ˈw̥iːl/": "ˈʍɪi̯l",
            "/fjʉw]": "fjʉw",
            "dɛəns~deəns": "dɛəns",
            "liːd": "liːd",
        }

        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(vocabulary_sources.bare_ipa(source), expected)

    def test_definition_similarity_prefers_the_matching_sense(self):
        payload = "\n".join(
            json.dumps(item)
            for item in (
                {
                    "id": "language",
                    "left": "use foul or abusive language towards abuse shout",
                    "right": "abuse insult revile vituperation",
                },
                {
                    "id": "mistreat",
                    "left": "use foul or abusive language towards abuse shout",
                    "right": "abuse maltreat mistreatment",
                },
            )
        )
        result = subprocess.run(
            ["xcrun", "swift", str(SIMILARITY_SCRIPT)],
            input=payload + "\n",
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        scores = {item["id"]: item["distance"] for item in map(json.loads, result.stdout.splitlines())}
        self.assertLess(scores["language"], scores["mistreat"])

    def run_cli(
        self,
        root: Path,
        *arguments: str,
        hash_seed: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, **({"PYTHONHASHSEED": hash_seed} if hash_seed else {})},
        )

    def make_source(self, root: Path, *, checksum: str | None = None, encoding: str = "utf-8") -> Path:
        raw = root / "Content/Sources/Raw/demo/words.csv"
        raw.parent.mkdir(parents=True)
        raw.write_text("beta,betas\nAlpha,Alphas\nalpha,alpha\n", encoding=encoding)
        digest = checksum or hashlib.sha256(raw.read_bytes()).hexdigest()
        manifest = {
            "schemaVersion": 1,
            "sources": [
                {
                    "id": "demo",
                    "name": "Demo",
                    "version": "1",
                    "retrievedAt": "2026-07-11",
                    "canonicalURL": "https://example.invalid/demo",
                    "adapter": "lemma_csv",
                    "encoding": encoding,
                    "rawFile": {
                        "path": "Content/Sources/Raw/demo/words.csv",
                        "sha256": digest,
                        "bytes": raw.stat().st_size,
                    },
                    "licenseEvidence": [],
                    "repositoryRedistribution": "allowed",
                    "appUse": "reference_only",
                }
            ],
        }
        path = root / "Content/Sources/source-manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def make_promotable_bank(self, root: Path) -> tuple[Path, Path, Path]:
        manifest_path = self.make_source(root)
        manifest = json.loads(manifest_path.read_text())
        manifest["sources"][0].update(
            {"appUse": "approved", "requiredNotice": "Demo attribution"}
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        reviewed = root / "reviewed.json"
        rich_item = self.rich_review_record()
        rich_item["id"] = "basic-001"
        rich_item["sortOrder"] = 1
        reviewed.write_text(
            json.dumps(
                [
                    {
                        key: rich_item[key]
                        for key in vocabulary_sources.SEED_KEYS
                    }
                ]
            ),
            encoding="utf-8",
        )
        provenance = root / "provenance.json"
        provenance.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "id": "demo",
                            "licenses": [{"requiredNotice": "Demo attribution"}],
                            "rights": {
                                key: "approved"
                                for key in (
                                    "commercialUse",
                                    "reproduction",
                                    "redistribution",
                                    "modification",
                                    "translatedDerivatives",
                                )
                            },
                        }
                    ],
                    "items": [
                        {
                            "itemID": "basic-001",
                            "conceptKey": "expression:excellent",
                            "sourceIDs": ["demo"],
                            "validationSourceIDs": ["demo"],
                            "cefr": "A2",
                            "appLevel": "basic",
                            "englishReviewer": "en",
                            "zhHantReviewer": "zh",
                            "levelReviewer": "level",
                            "rightsReviewer": "rights",
                            "reviewedAt": "2026-07-11",
                            "status": "approved",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        notices = root / "notices.txt"
        notices.write_text("Demo attribution\n", encoding="utf-8")
        return reviewed, provenance, notices

    def rich_review_record(self) -> dict:
        return {
            "id": "bank-basic-0001",
            "level": "basic",
            "sortOrder": 1,
            "contentLanguageCode": "en",
            "supportLanguageCodes": ["zh-Hant"],
            "plainExpression": "guide",
            "upgradedExpression": "lead",
            "primarySenseID": "lead-verb-guide",
            "pronunciations": [
                {
                    "id": "lead-us-1",
                    "ipa": "liːd",
                    "speechLocale": "en-US",
                    "region": "US",
                }
            ],
            "senses": [
                {
                    "id": "lead-verb-guide",
                    "partOfSpeech": "verb",
                    "meaning": {
                        "en": "To guide or conduct.",
                        "zh-Hant": "引導或帶領。",
                    },
                    "example": {
                        "text": "She will lead the meeting.",
                        "translation": {"zh-Hant": "她將主持這場會議。"},
                    },
                    "pronunciationIDs": ["lead-us-1"],
                }
            ],
            "quiz": {
                "prompt": {
                    "en": "Which expression means guide?",
                    "zh-Hant": "哪個詞表示引導？",
                },
                "options": ["lead", "leave", "lend", "lean"],
                "correctOptionIndex": 0,
            },
            "sourceRefs": [
                {"sourceID": "oewn-2025", "sourceEntryRef": "lead-v-1"}
            ],
            "validationSourceIDs": [
                "wiktextract-en-2026-07-09",
                "cmudict-7479086",
            ],
            "cefr": "A2",
            "reviewStatus": "approved",
            "englishReviewer": "codex-content-review-2026-07-11",
            "zhHantReviewer": "codex-content-review-2026-07-11",
        }

    def indexed_review_items(self, count: int, *, start: int = 0) -> list[dict]:
        items = []
        for index in range(start, start + count):
            item = json.loads(json.dumps(self.rich_review_record()))
            target = f"reviewed-{index:06d}"
            item["id"] = f"bank-{index:06d}"
            item["sortOrder"] = index + 1
            item["upgradedExpression"] = target
            item["quiz"]["options"] = [
                target,
                f"option-a-{index:06d}",
                f"option-b-{index:06d}",
                f"option-c-{index:06d}",
            ]
            items.append(item)
        return items

    def write_review_index_shard(
        self,
        review_dir: Path,
        number: int,
        items: list[dict],
        cumulative: int,
        *,
        final: bool = False,
    ) -> dict:
        path = review_dir / f"checkpoint-{number:04d}.jsonl"
        path.write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in items),
            encoding="utf-8",
        )
        return {
            "path": path.name,
            "items": len(items),
            "sha256": vocabulary_sources.sha256(path),
            "firstID": items[0]["id"],
            "lastID": items[-1]["id"],
            "cumulativeItems": cumulative,
            "status": "approved",
            "final": final,
        }

    def test_rich_review_accepts_complete_record(self):
        vocabulary_sources.validate_reviewed_item(self.rich_review_record())

    def test_load_review_index_accepts_complete_and_final_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            review_dir = Path(directory)
            first = self.indexed_review_items(200)
            final = self.indexed_review_items(64, start=200)
            shards = [
                self.write_review_index_shard(review_dir, 1, first, 200),
                self.write_review_index_shard(
                    review_dir, 2, final, 264, final=True
                ),
            ]
            index = review_dir / "index.json"
            index.write_text(
                json.dumps({"schemaVersion": 1, "shards": shards}),
                encoding="utf-8",
            )

            loaded = vocabulary_sources.load_review_index(index, 264)

            self.assertEqual(len(loaded), 264)
            self.assertEqual(loaded[0]["id"], "bank-000000")
            self.assertEqual(loaded[-1]["id"], "bank-000263")

    def test_load_review_index_rejects_a_tampered_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            review_dir = Path(directory)
            items = self.indexed_review_items(1)
            shard = self.write_review_index_shard(
                review_dir, 1, items, 1, final=True
            )
            index = review_dir / "index.json"
            index.write_text(
                json.dumps({"schemaVersion": 1, "shards": [shard]}),
                encoding="utf-8",
            )
            (review_dir / shard["path"]).write_text("tampered\n", encoding="utf-8")

            with self.assertRaisesRegex(vocabulary_sources.SourceError, "hash"):
                vocabulary_sources.load_review_index(index, 1)

    def test_load_review_index_rejects_reordered_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            review_dir = Path(directory)
            first = self.indexed_review_items(200)
            final = self.indexed_review_items(1, start=200)
            shards = [
                self.write_review_index_shard(review_dir, 1, first, 200),
                self.write_review_index_shard(
                    review_dir, 2, final, 201, final=True
                ),
            ]
            index = review_dir / "index.json"
            index.write_text(
                json.dumps({"schemaVersion": 1, "shards": list(reversed(shards))}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(vocabulary_sources.SourceError, "order"):
                vocabulary_sources.load_review_index(index, 201)

    def test_load_review_index_rejects_duplicate_id_across_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            review_dir = Path(directory)
            first = self.indexed_review_items(200)
            duplicate = [json.loads(json.dumps(first[0]))]
            shards = [
                self.write_review_index_shard(review_dir, 1, first, 200),
                self.write_review_index_shard(
                    review_dir, 2, duplicate, 201, final=True
                ),
            ]
            index = review_dir / "index.json"
            index.write_text(
                json.dumps({"schemaVersion": 1, "shards": shards}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(vocabulary_sources.SourceError, "duplicate"):
                vocabulary_sources.load_review_index(index, 201)

    def test_load_review_index_rejects_incomplete_non_final_shard(self):
        with tempfile.TemporaryDirectory() as directory:
            review_dir = Path(directory)
            items = self.indexed_review_items(64)
            shard = self.write_review_index_shard(review_dir, 1, items, 64)
            index = review_dir / "index.json"
            index.write_text(
                json.dumps({"schemaVersion": 1, "shards": [shard]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(vocabulary_sources.SourceError, "200"):
                vocabulary_sources.load_review_index(index, 64)

    def test_rich_review_rejects_dangling_pronunciation_reference(self):
        item = self.rich_review_record()
        item["senses"][0]["pronunciationIDs"] = ["missing"]

        with self.assertRaisesRegex(
            vocabulary_sources.SourceError, "unknown pronunciation"
        ):
            vocabulary_sources.validate_reviewed_item(item)

    def test_rich_review_rejects_usage_note_instead_of_sentence_translation(self):
        item = self.rich_review_record()
        item["senses"][0]["example"]["translation"]["zh-Hant"] = (
            "例句中的 lead 表示引導。"
        )

        with self.assertRaisesRegex(
            vocabulary_sources.SourceError, "full-sentence translation"
        ):
            vocabulary_sources.validate_reviewed_item(item)

    def test_rich_review_rejects_more_than_three_senses(self):
        item = self.rich_review_record()
        item["senses"] = item["senses"] * 4

        with self.assertRaisesRegex(
            vocabulary_sources.SourceError, "one to three senses"
        ):
            vocabulary_sources.validate_reviewed_item(item)

    def test_arpabet_to_ipa_places_stress_at_the_syllable_onset(self):
        self.assertEqual(
            vocabulary_sources.arpabet_to_ipa("AH0 B AW1 T"),
            "əˈbaʊt",
        )
        self.assertEqual(vocabulary_sources.arpabet_to_ipa("G EH1 T"), "gɛt")

    def test_review_pronunciations_compose_a_phrase_from_cmudict(self):
        pronunciations, references = vocabulary_sources.review_pronunciations(
            "get together",
            [],
            {
                "get": [
                    {
                        "value": "G EH1 T",
                        "sourceRef": {
                            "sourceID": "cmudict-7479086",
                            "sourceEntryRef": "get",
                        },
                    }
                ],
                "together": [
                    {
                        "value": "T AH0 G EH1 DH ER0",
                        "sourceRef": {
                            "sourceID": "cmudict-7479086",
                            "sourceEntryRef": "together",
                        },
                    }
                ],
            },
        )

        self.assertEqual(
            pronunciations,
            [
                {
                    "id": "get-together-us-1",
                    "ipa": "gɛt təˈgɛðɚ",
                    "speechLocale": "en-US",
                    "region": "US",
                }
            ],
        )
        self.assertEqual(
            references,
            [
                {"sourceID": "cmudict-7479086", "sourceEntryRef": "get"},
                {
                    "sourceID": "cmudict-7479086",
                    "sourceEntryRef": "together",
                },
            ],
        )

    def test_review_pronunciations_reject_fragments_and_nonstandard_dialects(self):
        pronunciations, _ = vocabulary_sources.review_pronunciations(
            "exacerbate",
            [
                {"notation": "ipa", "value": "ɪkˈsæs-", "region": "UK"},
                {"notation": "ipa", "value": "ɪɡ ˈzæsəˌbeɪt", "region": "UK"},
                {"notation": "ipa", "value": "egˈzæ.sə.beɪt", "region": "Australian"},
            ],
            {},
        )

        self.assertEqual(
            pronunciations,
            [
                {
                    "id": "exacerbate-gb-1",
                    "ipa": "ɪɡˈzæsəˌbeɪt",
                    "speechLocale": "en-GB",
                    "region": "UK",
                }
            ],
        )

    def test_review_pronunciations_uses_region_tags_and_labels_unmarked_ipa_general(self):
        pronunciations, _ = vocabulary_sources.review_pronunciations(
            "ambiguous",
            [
                {
                    "notation": "ipa",
                    "value": "æmˈbɪɡ.ju.əs",
                    "region": "Canada",
                    "tags": ["Canada", "General-American"],
                },
                {
                    "notation": "ipa",
                    "value": "ɛəmˈbɪɡ.ju.əs",
                    "region": None,
                    "tags": [],
                },
            ],
            {},
        )

        self.assertEqual(
            pronunciations,
            [
                {
                    "id": "ambiguous-us-1",
                    "ipa": "æmˈbɪɡ.ju.əs",
                    "speechLocale": "en-US",
                    "region": "US",
                },
                {
                    "id": "ambiguous-general-2",
                    "ipa": "ɛəmˈbɪɡ.ju.əs",
                    "speechLocale": "en-US",
                    "region": "General",
                },
            ],
        )

    def test_review_pronunciations_keeps_matching_ipa_for_distinct_regions(self):
        pronunciations, _ = vocabulary_sources.review_pronunciations(
            "ambiguous",
            [
                {
                    "notation": "ipa",
                    "value": "æmˈbɪɡ.ju.əs",
                    "region": "Received-Pronunciation",
                    "tags": ["Received-Pronunciation"],
                },
                {
                    "notation": "ipa",
                    "value": "æmˈbɪɡ.ju.əs",
                    "region": "Canada",
                    "tags": ["Canada", "General-American"],
                },
            ],
            {},
        )

        self.assertEqual(
            [(item["region"], item["ipa"]) for item in pronunciations],
            [("US", "æmˈbɪɡ.ju.əs"), ("UK", "æmˈbɪɡ.ju.əs")],
        )

    def test_review_pronunciations_accepts_explicit_general_region(self):
        source_ref = {
            "sourceID": "moby-pronunciator-ii-3205",
            "sourceEntryRef": "impermanent",
        }

        pronunciations, references = vocabulary_sources.review_pronunciations(
            "impermanent",
            [
                {
                    "notation": "ipa",
                    "value": "ɪmˈpɝɹmənənt",
                    "speechLocale": "en-US",
                    "region": "General",
                    "tags": [],
                    "sourceRef": source_ref,
                }
            ],
            {},
        )

        self.assertEqual(
            pronunciations,
            [
                {
                    "id": "impermanent-general-1",
                    "ipa": "ɪmˈpɝɹmənənt",
                    "speechLocale": "en-US",
                    "region": "General",
                }
            ],
        )
        self.assertEqual(references, [source_ref])

    def test_review_pronunciations_adds_cmudict_us_when_other_ipa_is_unmarked(self):
        pronunciations, references = vocabulary_sources.review_pronunciations(
            "leverage",
            [
                {"notation": "ipa", "value": "ˈliːv.ə.ɹɪd͡ʒ", "region": None},
                {"notation": "ipa", "value": "ˈlɛv.ə.ɹɪd͡ʒ", "region": None},
            ],
            {
                "leverage": [
                    {
                        "value": "L EH1 V ER0 IH0 JH",
                        "sourceRef": {
                            "sourceID": "cmudict-7479086",
                            "sourceEntryRef": "leverage",
                        },
                    }
                ]
            },
        )

        self.assertEqual([item["region"] for item in pronunciations], ["US", "General", "General"])
        self.assertEqual(pronunciations[0]["id"], "leverage-us-1")
        self.assertEqual(pronunciations[1]["id"], "leverage-general-2")
        self.assertIn(
            {"sourceID": "cmudict-7479086", "sourceEntryRef": "leverage"},
            references,
        )

    def test_review_senses_keep_primary_and_common_additional_meanings(self):
        packet = {
            "id": "bank-basic-0001",
            "target": "lead",
            "definition": "to guide a group",
            "example": "She will lead the meeting.",
            "partOfSpeech": "v",
            "sourceRefs": [
                {"sourceID": "oewn-2025", "sourceEntryRef": "lead#v#1"}
            ],
            "candidateSenses": [
                {
                    "id": "lead-verb-guide",
                    "partOfSpeech": "verb",
                    "glosses": ["to guide a group"],
                    "examples": ["She will lead the meeting."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "lead#verb#1",
                    },
                },
                {
                    "id": "lead-noun-clue",
                    "partOfSpeech": "noun",
                    "glosses": ["information that may help solve a problem"],
                    "examples": ["The detective followed a new lead."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "lead#noun#1",
                    },
                },
                {
                    "id": "lead-rare",
                    "partOfSpeech": "verb",
                    "glosses": ["an obsolete meaning"],
                    "examples": [],
                    "tags": ["obsolete"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "lead#verb#2",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual([sense["id"] for sense in senses], ["lead-verb-guide", "lead-noun-clue"])
        self.assertEqual(senses[0]["partOfSpeech"], "verb")

    def test_review_senses_infer_legacy_primary_part_of_speech(self):
        senses = vocabulary_sources.review_senses(
            {
                "id": "advanced-001",
                "target": "exacerbate",
                "definition": "A precise verb for making a bad situation worse.",
                "example": "Poor communication can exacerbate the delay.",
                "partOfSpeech": "",
                "sourceRefs": [
                    {"sourceID": "vocaby-original", "sourceEntryRef": "advanced-001"}
                ],
                "candidateSenses": [
                    {
                        "id": "exacerbate#v#1",
                        "partOfSpeech": "v",
                        "glosses": ["make worse"],
                        "examples": ["Poor communication can exacerbate the delay."],
                        "tags": [],
                        "sourceRef": {
                            "sourceID": "oewn-2025",
                            "sourceEntryRef": "exacerbate#v#1",
                        },
                    }
                ],
            }
        )

        self.assertEqual(senses[0]["partOfSpeech"], "verb")

    def test_audit_reviewed_reports_complete_bank_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root)
            reviewed = root / "reviewed.jsonl"
            items = []
            for index in range(5_000):
                item = json.loads(json.dumps(self.rich_review_record()))
                target = f"reviewed-expression-{index:04d}"
                item["id"] = f"bank-basic-{index:04d}"
                item["sortOrder"] = index + 1
                item["upgradedExpression"] = target
                item["quiz"]["options"][0] = target
                items.append(item)
            reviewed.write_text(
                "".join(json.dumps(item) + "\n" for item in items),
                encoding="utf-8",
            )

            result = self.run_cli(
                root, "audit-reviewed", "--input", str(reviewed)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout),
                {
                    "approved": 5_000,
                    "items": 5_000,
                    "levels": {"advanced": 0, "basic": 5_000, "intermediate": 0},
                },
            )

    def test_audit_reviewed_rejects_bank_below_minimum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root)
            reviewed = root / "reviewed.jsonl"
            reviewed.write_text(
                json.dumps(self.rich_review_record()) + "\n", encoding="utf-8"
            )

            result = self.run_cli(
                root, "audit-reviewed", "--input", str(reviewed)
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("at least 5000", result.stderr)

    def test_audit_reviewed_accepts_a_checkpoint_minimum(self):
        with tempfile.TemporaryDirectory() as directory:
            reviewed = Path(directory) / "checkpoint.jsonl"
            reviewed.write_text(
                json.dumps(self.rich_review_record()) + "\n",
                encoding="utf-8",
            )

            result = vocabulary_sources.audit_reviewed(
                reviewed, minimum_items=1
            )

            self.assertEqual(result["items"], 1)
            self.assertEqual(result["approved"], 1)

    def make_enrichment_sources(self, root: Path) -> tuple[Path, Path]:
        input_dir = root / "Content/Sources/Imported"
        input_dir.mkdir(parents=True)
        records = {
            "oewn-2025.jsonl": {
                "sourceID": "oewn-2025",
                "sourceEntryRef": "excellent#a",
                "headword": "excellent",
                "partOfSpeech": "a",
                "cefr": None,
                "definitions": ["of very high quality"],
                "examples": ["She shared an excellent idea."],
                "relatedTerms": ["excellent", "very good"],
                "translations": {},
                "pronunciations": [],
                "forms": [],
                "senseRefs": ["0001-a"],
            },
            "freedict.jsonl": {
                "sourceID": "freedict",
                "sourceEntryRef": "entry-1",
                "headword": "excellent",
                "partOfSpeech": "adj",
                "cefr": None,
                "definitions": ["of very high quality"],
                "examples": [],
                "relatedTerms": [],
                "translations": {"zh": ["优秀"]},
                "pronunciations": [],
                "forms": [],
                "senseRefs": [],
            },
            "cefr.jsonl": {
                "sourceID": "cefr",
                "sourceEntryRef": "excellent#adjective#A2",
                "headword": "excellent",
                "partOfSpeech": "adjective",
                "cefr": "A2",
                "definitions": [],
                "examples": [],
                "relatedTerms": [],
                "translations": {},
                "pronunciations": [],
                "forms": [],
                "senseRefs": [],
            },
            "cow.jsonl": {
                "sourceID": "cow",
                "sourceEntryRef": "0001-a",
                "headword": "卓越",
                "partOfSpeech": None,
                "cefr": None,
                "definitions": [],
                "examples": [],
                "relatedTerms": [],
                "translations": {"language": "cmn"},
                "pronunciations": [],
                "forms": [],
                "senseRefs": ["0001-a"],
            },
            "tatoeba.jsonl": {
                "sourceID": "tatoeba-eng-cmn-2026-07-04",
                "sourceEntryRef": "eng-42:cmn-84",
                "headword": "Her excellent quality impressed us.",
                "partOfSpeech": None,
                "cefr": None,
                "definitions": [],
                "examples": ["Her excellent quality impressed us."],
                "relatedTerms": [],
                "translations": {"zh-Hant": ["她的優秀品質令我們印象深刻。"]},
                "pronunciations": [],
                "forms": [],
                "senseRefs": [],
            },
        }
        for name, record in records.items():
            (input_dir / name).write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
        with (input_dir / "cefr.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        **records["cefr.jsonl"],
                        "sourceEntryRef": "very good#adjective#A1",
                        "headword": "very good",
                        "cefr": "A1",
                    }
                )
                + "\n"
            )
        manifest = {
            "schemaVersion": 1,
            "sources": [
                {
                    "id": source_id,
                    "name": source_id,
                    "version": "1",
                    "canonicalURL": f"https://example.invalid/{source_id}",
                    "license": "Demo license",
                    "licenseURL": "https://example.invalid/license",
                    "appUse": "approved",
                }
                for source_id in (
                    "oewn-2025",
                    "freedict",
                    "cefr",
                    "cc-cedict-2026-07-11",
                    "cow",
                    "omw-ili-map",
                    "tatoeba-eng-cmn-2026-07-04",
                )
            ],
        }
        manifest_path = root / "Content/Sources/source-manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        existing_seed = root / "existing.json"
        existing_seed.write_text("[]", encoding="utf-8")
        return input_dir, existing_seed

    def test_import_honors_the_manifest_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = self.make_source(root, encoding="iso-8859-1")
            raw = root / "Content/Sources/Raw/demo/words.csv"
            raw.write_text("café,cafés\n", encoding="iso-8859-1")
            manifest = json.loads(manifest_path.read_text())
            manifest["sources"][0]["rawFile"]["sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
            manifest["sources"][0]["rawFile"]["bytes"] = raw.stat().st_size
            manifest_path.write_text(json.dumps(manifest))

            output = root / "output.jsonl"
            result = self.run_cli(root, "import-source", "demo", "--output", str(output))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["headword"], "café")

    def test_wiktextract_snapshot_keeps_only_seed_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root)
            source = root / "all.jsonl.gz"
            rows = [
                {
                    "word": "lead",
                    "lang_code": "en",
                    "pos": "noun",
                    "senses": [{"glosses": ["A metal."]}],
                },
                {
                    "word": "lead",
                    "lang_code": "en",
                    "pos": "verb",
                    "senses": [{"glosses": ["To guide."]}],
                },
                {
                    "word": "other",
                    "lang_code": "en",
                    "pos": "noun",
                    "senses": [{"glosses": ["Another."]}],
                },
                {
                    "word": "lead",
                    "lang_code": "fr",
                    "pos": "noun",
                    "senses": [{"glosses": ["French row."]}],
                },
            ]
            with gzip.open(source, "wt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row) + "\n")
            seed = root / "seed.json"
            seed.write_text(
                json.dumps([{"upgradedExpression": "lead"}]), encoding="utf-8"
            )
            output = root / "targets.jsonl.gz"

            result = self.run_cli(
                root,
                "snapshot-wiktextract",
                "--source-url",
                source.as_uri(),
                "--seed",
                str(seed),
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            with gzip.open(output, "rt", encoding="utf-8") as stream:
                kept = [json.loads(line) for line in stream]
            self.assertEqual(
                [(row["word"], row["pos"]) for row in kept],
                [("lead", "noun"), ("lead", "verb")],
            )
            metadata = json.loads(result.stdout)
            self.assertEqual(metadata["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(metadata["bytes"], output.stat().st_size)
            self.assertEqual(metadata["records"], 2)

    def test_wiktextract_adapter_preserves_pos_senses_and_ipa(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "Content/Sources/Raw/wiktextract/targets.jsonl.gz"
            raw.parent.mkdir(parents=True)
            row = {
                "word": "lead",
                "lang_code": "en",
                "pos": "verb",
                "sounds": [
                    {"ipa": "/liːd/", "tags": ["General-American"]},
                    {"ipa": "[lɛd]", "tags": ["UK"]},
                ],
                "translations": [{"code": "zh", "word": "帶領"}],
                "senses": [
                    {
                        "senseid": ["lead-verb-guide"],
                        "glosses": ["To guide or conduct."],
                        "tags": ["transitive"],
                        "examples": [
                            {
                                "text": "She will lead the meeting.",
                                "type": "example",
                            },
                            {
                                "text": "A quoted example.",
                                "type": "quotation",
                            },
                        ],
                        "translations": [{"code": "zh", "word": "引導"}],
                    }
                ],
            }
            with gzip.open(raw, "wt", encoding="utf-8") as stream:
                stream.write(json.dumps(row) + "\n")
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "wiktextract-test",
                        "adapter": "wiktextract_jsonl_gz",
                        "rawFile": {
                            "path": str(raw.relative_to(root)),
                            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                            "bytes": raw.stat().st_size,
                        },
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "output.jsonl"

            result = self.run_cli(
                root,
                "import-source",
                "wiktextract-test",
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(output.read_text())
            self.assertEqual(record["partOfSpeech"], "verb")
            self.assertEqual(
                [item["value"] for item in record["pronunciations"]],
                ["liːd", "lɛd"],
            )
            self.assertEqual(record["senses"][0]["id"], "lead-verb-guide")
            self.assertEqual(
                record["senses"][0]["examples"],
                ["She will lead the meeting."],
            )
            self.assertEqual(
                record["senses"][0]["translations"], {"zh": ["引導"]}
            )
            self.assertEqual(record["translations"]["zh"], ["帶領", "引導"])

    def test_cmudict_adapter_strips_inline_comments_and_preserves_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "Content/Sources/Raw/cmudict/cmudict.dict"
            raw.parent.mkdir(parents=True)
            raw.write_text(
                "word W ER1 D # common noun\nword(2) W AO1 R D\n",
                encoding="utf-8",
            )
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "cmudict-test",
                        "adapter": "cmudict",
                        "rawFile": {
                            "path": str(raw.relative_to(root)),
                            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                            "bytes": raw.stat().st_size,
                        },
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "output.jsonl"

            result = self.run_cli(
                root, "import-source", "cmudict-test", "--output", str(output)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(output.read_text())
            self.assertEqual(
                record["pronunciations"],
                [
                    {
                        "notation": "arpabet",
                        "region": "US",
                        "speechLocale": "en-US",
                        "tags": [],
                        "value": "W AO1 R D",
                    },
                    {
                        "notation": "arpabet",
                        "region": "US",
                        "speechLocale": "en-US",
                        "tags": [],
                        "value": "W ER1 D",
                    },
                ],
            )

    def test_cedict_adapter_inverts_traditional_chinese_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "Content/Sources/Raw/cedict/cedict.txt.gz"
            raw.parent.mkdir(parents=True)
            with gzip.open(raw, "wt", encoding="utf-8") as stream:
                stream.write("# CC-CEDICT test\n")
                stream.write("有能力 有能力 [you3 neng2 li4] /able/capable/\n")
                stream.write("舊 旧 [jiu4] /variant of 舊|旧[jiu4]/old/\n")
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "cc-cedict",
                        "name": "CC-CEDICT",
                        "version": "test",
                        "adapter": "cedict_gzip",
                        "rawFile": {
                            "path": str(raw.relative_to(root)),
                            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                            "bytes": raw.stat().st_size,
                        },
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                        "appUse": "approved",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "cedict.jsonl"

            result = self.run_cli(
                root, "import-source", "cc-cedict", "--output", str(output)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            records = [json.loads(line) for line in output.read_text().splitlines()]
            able = next(item for item in records if item["headword"] == "able")
            self.assertEqual(able["translations"]["zh-Hant"], ["有能力"])
            self.assertEqual(able["definitions"], ["able", "capable"])
            self.assertNotIn("variant of", " ".join(item["headword"] for item in records))

    def test_tatoeba_adapter_imports_verified_parallel_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_dir = root / "Content/Sources/Raw/tatoeba"
            raw_dir.mkdir(parents=True)
            files = {
                "eng_sentences.tsv.bz2": "42\teng\tHer excellent quality impressed us.\n",
                "cmn_sentences.tsv.bz2": "84\tcmn\t她的優秀品質令我們印象深刻。\n",
                "cmn-eng_links.tsv.bz2": "84\t42\n",
            }
            raw_files = []
            for name, content in files.items():
                path = raw_dir / name
                with bz2.open(path, "wt", encoding="utf-8") as stream:
                    stream.write(content)
                raw_files.append(
                    {
                        "path": str(path.relative_to(root)),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "bytes": path.stat().st_size,
                    }
                )
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "tatoeba",
                        "name": "Tatoeba",
                        "version": "test",
                        "adapter": "tatoeba_parallel_bz2",
                        "rawFiles": raw_files,
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                        "appUse": "approved",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "tatoeba.jsonl"

            result = self.run_cli(
                root, "import-source", "tatoeba", "--output", str(output)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(output.read_text())
            self.assertEqual(record["sourceEntryRef"], "eng-42:cmn-84")
            self.assertEqual(record["examples"], ["Her excellent quality impressed us."])
            self.assertEqual(record["translations"]["zh-Hant"], ["她的優秀品質令我們印象深刻。"])

    def test_ili_map_adapter_preserves_pwn_and_ili_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "Content/Sources/Raw/omw/ili-map.tab"
            raw.parent.mkdir(parents=True)
            raw.write_text("i1\t00001740-a\ni2\t00002098-a\n", encoding="utf-8")
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "omw-ili",
                        "adapter": "ili_map_tab",
                        "rawFile": {
                            "path": str(raw.relative_to(root)),
                            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                            "bytes": raw.stat().st_size,
                        },
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "ili.jsonl"

            result = self.run_cli(
                root, "import-source", "omw-ili", "--output", str(output)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(output.read_text().splitlines()[0])
            self.assertEqual(record["senseRefs"], ["00001740-a"])
            self.assertEqual(record["iliRefs"], ["i1"])

    def test_cow_adapter_keeps_the_same_lemma_in_separate_senses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "Content/Sources/Raw/cow/wn-data.tab"
            raw.parent.mkdir(parents=True)
            raw.write_text(
                "0001-n\tcmn:lemma\t吸菸\n0002-v\tcmn:lemma\t吸菸\n",
                encoding="utf-8",
            )
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "cow",
                        "adapter": "cow_tsv",
                        "rawFile": {
                            "path": str(raw.relative_to(root)),
                            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                            "bytes": raw.stat().st_size,
                        },
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "cow.jsonl"

            result = self.run_cli(
                root, "import-source", "cow", "--output", str(output)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            records = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(
                [record["senseRefs"] for record in records],
                [["0001-n"], ["0002-v"]],
            )

    def test_oewn_candidate_contains_shared_enrichment_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "Content/Sources/Raw/demo/oewn.zip"
            raw.parent.mkdir(parents=True)
            with zipfile.ZipFile(raw, "w") as archive:
                archive.writestr(
                    "entries-e.json",
                    json.dumps({"excellent": {"a": {"sense": [{"synset": "0001-a"}]}}}),
                )
                archive.writestr(
                    "adj.all.json",
                    json.dumps(
                        {
                            "0001-a": {
                                "definition": ["of very high quality"],
                                "example": [
                                    {
                                        "text": "She shared an excellent idea.",
                                        "source": "Demo corpus",
                                    }
                                ],
                                "members": ["excellent", "first-class"],
                                "ili": "i1",
                                "partOfSpeech": "a",
                            }
                        }
                    ),
                )
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "demo-oewn",
                        "name": "Demo OEWN",
                        "version": "1",
                        "retrievedAt": "2026-07-11",
                        "canonicalURL": "https://example.invalid/oewn",
                        "adapter": "oewn_json_zip",
                        "rawFile": {
                            "path": "Content/Sources/Raw/demo/oewn.zip",
                            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                            "bytes": raw.stat().st_size,
                        },
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                        "appUse": "reference_only",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "output.jsonl"

            result = self.run_cli(root, "import-source", "demo-oewn", "--output", str(output))

            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(output.read_text())
            self.assertEqual(record["definitions"], ["of very high quality"])
            self.assertEqual(record["examples"], ["She shared an excellent idea."])
            self.assertEqual(record["relatedTerms"], ["excellent", "first-class"])
            self.assertEqual(record["iliRefs"], ["i1"])

    def test_oewn_candidates_keep_definition_example_and_terms_in_the_same_sense(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "Content/Sources/Raw/demo/oewn.zip"
            raw.parent.mkdir(parents=True)
            with zipfile.ZipFile(raw, "w") as archive:
                archive.writestr(
                    "entries-b.json",
                    json.dumps(
                        {
                            "bank": {
                                "n": {
                                    "sense": [
                                        {"synset": "0001-n"},
                                        {"synset": "0002-n"},
                                    ]
                                }
                            }
                        }
                    ),
                )
                archive.writestr(
                    "noun.group.json",
                    json.dumps(
                        {
                            "0001-n": {
                                "definition": ["a financial institution"],
                                "example": ["The bank approved the loan."],
                                "members": ["bank", "depository financial institution"],
                            },
                            "0002-n": {
                                "definition": ["the edge of a river"],
                                "example": ["They sat on the river bank."],
                                "members": ["bank", "riverbank"],
                            },
                        }
                    ),
                )
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "demo-oewn",
                        "adapter": "oewn_json_zip",
                        "rawFile": {
                            "path": "Content/Sources/Raw/demo/oewn.zip",
                            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                            "bytes": raw.stat().st_size,
                        },
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest))
            output = root / "output.jsonl"

            result = self.run_cli(root, "import-source", "demo-oewn", "--output", str(output))

            self.assertEqual(result.returncode, 0, result.stderr)
            records = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(
                [(item["definitions"][0], item["examples"][0], item["relatedTerms"][1]) for item in records],
                [
                    ("a financial institution", "The bank approved the loan.", "depository financial institution"),
                    ("the edge of a river", "They sat on the river bank.", "riverbank"),
                ],
            )

    def test_freedict_candidates_keep_each_translation_with_its_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "Content/Sources/Raw/demo/freedict.tar.xz"
            raw.parent.mkdir(parents=True)
            tei = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
            <entry><form><orth>abandon</orth><pron>/test/</pron></form><gramGrp><pos>v</pos></gramGrp>
              <sense><cit type="trans" xml:lang="zh"><quote>放棄</quote></cit><sense><def>To give up control of something.</def></sense></sense>
              <sense><cit type="trans" xml:lang="zh"><quote>遺棄</quote></cit><sense><def>To leave a place or person behind.</def></sense></sense>
            </entry></body></text></TEI>'''.encode()
            with tarfile.open(raw, "w:xz") as archive:
                info = tarfile.TarInfo("eng-zho/eng-zho.tei")
                info.size = len(tei)
                archive.addfile(info, io.BytesIO(tei))
            manifest = {
                "schemaVersion": 1,
                "sources": [
                    {
                        "id": "demo-freedict",
                        "adapter": "freedict_tei_tar",
                        "rawFile": {
                            "path": "Content/Sources/Raw/demo/freedict.tar.xz",
                            "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                            "bytes": raw.stat().st_size,
                        },
                        "licenseEvidence": [],
                        "repositoryRedistribution": "allowed",
                    }
                ],
            }
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest))
            output = root / "output.jsonl"

            result = self.run_cli(root, "import-source", "demo-freedict", "--output", str(output))

            self.assertEqual(result.returncode, 0, result.stderr)
            records = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(
                [(item["translations"]["zh"], item["definitions"]) for item in records],
                [
                    (["放棄"], ["To give up control of something."]),
                    (["遺棄"], ["To leave a place or person behind."]),
                ],
            )

    def test_shared_enrichment_builds_source_aligned_review_packet(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            draft = root / "draft.jsonl"

            prepare = self.run_cli(
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
                str(draft),
            )

            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            item = json.loads(draft.read_text())
            self.assertEqual(item["plain"], "very good")
            self.assertEqual(item["target"], "excellent")
            self.assertEqual(item["translationDraft"], "優秀")
            self.assertEqual(item["example"], "Her excellent quality impressed us.")
            self.assertEqual(
                item["exampleTranslationDraft"],
                "她的優秀品質令我們印象深刻。",
            )
            self.assertEqual(
                sorted({reference["sourceID"] for reference in item["sourceRefs"]}),
                ["cefr", "freedict", "oewn-2025", "tatoeba-eng-cmn-2026-07-04"],
            )

    def test_shared_enrichment_uses_taiwan_vocabulary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            freedict = input_dir / "freedict.jsonl"
            record = json.loads(freedict.read_text())
            record["translations"] = {"zh": ["土著上边略称"]}
            freedict.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            draft = root / "draft.jsonl"
            self.assertEqual(
                self.run_cli(
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
                    str(draft),
                ).returncode,
                0,
            )
            self.assertEqual(
                json.loads(draft.read_text())["translationDraft"],
                "原住民上方縮寫",
            )

    def test_rich_review_rejects_non_unique_quiz_options(self):
        item = self.rich_review_record()
        item["quiz"]["options"] = ["lead", "lead", "lend", "lean"]

        with self.assertRaisesRegex(vocabulary_sources.SourceError, "invalid quiz"):
            vocabulary_sources.validate_reviewed_item(item)

    def test_build_reviewed_promotes_only_rich_seed_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = self.make_source(root)
            manifest = json.loads(manifest_path.read_text())
            manifest["sources"][0].update(
                {
                    "appUse": "approved",
                    "requiredNotice": "Demo attribution",
                    "license": "Demo license",
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            item = self.rich_review_record()
            item["sourceRefs"] = [
                {"sourceID": "demo", "sourceEntryRef": "lead-v-1"}
            ]
            item["validationSourceIDs"] = ["demo"]
            reviewed = root / "reviewed.jsonl"
            reviewed.write_text(json.dumps(item) + "\n", encoding="utf-8")
            existing = root / "existing.json"
            existing.write_text("[]", encoding="utf-8")
            seed = root / "seed.json"
            provenance = root / "provenance.json"
            notices = root / "notices.txt"

            result = self.run_cli(
                root,
                "build-reviewed",
                "--input",
                str(reviewed),
                "--existing-seed",
                str(existing),
                "--seed-output",
                str(seed),
                "--provenance-output",
                str(provenance),
                "--notices-output",
                str(notices),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            seed_item = json.loads(seed.read_text())[0]
            self.assertEqual(
                set(seed_item),
                {
                    "id",
                    "level",
                    "sortOrder",
                    "contentLanguageCode",
                    "supportLanguageCodes",
                    "plainExpression",
                    "upgradedExpression",
                    "primarySenseID",
                    "pronunciations",
                    "senses",
                    "quiz",
                },
            )
            provenance_data = json.loads(provenance.read_text())
            self.assertEqual(provenance_data["bankVersion"], "2026.07.5")
            self.assertEqual(
                provenance_data["items"][0]["reviewedAt"], "2026-07-15"
            )
            provenance_item = provenance_data["items"][0]
            self.assertEqual(provenance_item["sourceIDs"], ["demo"])
            self.assertEqual(provenance_item["validationSourceIDs"], ["demo"])
            self.assertEqual(provenance_item["status"], "approved")
            self.assertIn("Demo attribution", notices.read_text())

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

    def test_prepare_enrichment_preserves_current_seed_identity_and_rich_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            oewn_path = input_dir / "oewn-2025.jsonl"
            oewn = json.loads(oewn_path.read_text())
            oewn["senses"] = [
                {
                    "id": "excellent-adjective-1",
                    "partOfSpeech": "adjective",
                    "glosses": ["of very high quality"],
                    "tags": [],
                    "examples": ["She shared an excellent idea."],
                    "translations": {},
                }
            ]
            oewn["pronunciations"] = [
                {
                    "notation": "ipa",
                    "value": "ˈɛksələnt",
                    "speechLocale": "en-US",
                    "region": "US",
                    "tags": [],
                }
            ]
            oewn_path.write_text(json.dumps(oewn) + "\n", encoding="utf-8")
            current_seed = root / "current-seed.json"
            current_seed.write_text(
                json.dumps(
                    [
                        {
                            "id": "stable-basic-0042",
                            "level": "intermediate",
                            "sortOrder": 42,
                            "plainExpression": "very good",
                            "upgradedExpression": "excellent",
                            "meaning": {
                                "en": "Of very high quality.",
                                "zh-Hant": "非常出色。",
                            },
                            "example": {
                                "text": "She shared an excellent idea.",
                                "translation": {"zh-Hant": "她分享了一個很棒的想法。"},
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "review-queue.jsonl"

            result = self.run_cli(
                root,
                "prepare-enrichment",
                "--input-dir",
                str(input_dir),
                "--existing-seed",
                str(existing_seed),
                "--current-seed",
                str(current_seed),
                "--basic",
                "1",
                "--intermediate",
                "0",
                "--advanced",
                "0",
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(output.read_text())
            self.assertEqual(packet["id"], "stable-basic-0042")
            self.assertEqual(packet["level"], "intermediate")
            self.assertEqual(packet["sortOrder"], 42)
            self.assertEqual(packet["candidateSenses"][0]["id"], "excellent-adjective-1")
            self.assertEqual(packet["candidatePlainExpressions"], ["very good"])
            self.assertEqual(
                packet["candidatePronunciations"][0]["value"], "ˈɛksələnt"
            )
            self.assertEqual(packet["validationSourceIDs"], ["oewn-2025"])
            self.assertIn("level-evidence-mismatch", packet["issues"])

    def test_prepare_enrichment_preserves_current_seed_expression_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            current_seed = root / "current-seed.json"
            current_seed.write_text(
                json.dumps(
                    [
                        {
                            "id": "bank-basic-0001",
                            "level": "basic",
                            "sortOrder": 1,
                            "plainExpression": "very good",
                            "upgradedExpression": "Excellent",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "review-queue.jsonl"

            result = self.run_cli(
                root,
                "prepare-enrichment",
                "--input-dir",
                str(input_dir),
                "--existing-seed",
                str(existing_seed),
                "--current-seed",
                str(current_seed),
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["target"], "Excellent")

    def test_prepare_enrichment_conflicting_cefr_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            cefr_path = input_dir / "cefr.jsonl"
            cefr = json.loads(cefr_path.read_text().splitlines()[0])
            cefr_path.write_text(
                cefr_path.read_text()
                + json.dumps(
                    {
                        **cefr,
                        "sourceEntryRef": "Excellent#adjective#B1",
                        "headword": "Excellent",
                        "cefr": "B1",
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
                            "id": "bank-basic-0001",
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

            packet = json.loads(first.read_text())
            self.assertEqual(packet["cefr"], "A2")
            self.assertIn(
                "excellent#adjective#A2",
                {ref["sourceEntryRef"] for ref in packet["sourceRefs"]},
            )

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

    def test_prepare_enrichment_uses_a_lower_cefr_plain_term(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            with (input_dir / "oewn-2025.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "sourceID": "oewn-2025",
                            "sourceEntryRef": "abstemious#a#0002-a",
                            "headword": "abstemious",
                            "partOfSpeech": "a",
                            "cefr": None,
                            "definitions": ["sparing in consumption"],
                            "examples": ["She remained abstemious at dinner."],
                            "relatedTerms": ["abstemious", "spartan", "moderate"],
                            "translations": {},
                            "pronunciations": [],
                            "forms": [],
                            "senseRefs": ["0002-a"],
                        }
                    )
                    + "\n"
                )
            with (input_dir / "freedict.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            **json.loads((input_dir / "freedict.jsonl").read_text().splitlines()[0]),
                            "sourceEntryRef": "entry-2",
                            "headword": "abstemious",
                            "definitions": ["sparing in consumption"],
                            "translations": {"zh": ["节制"]},
                        }
                    )
                    + "\n"
                )
            with (input_dir / "cefr.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            **json.loads((input_dir / "cefr.jsonl").read_text().splitlines()[0]),
                            "sourceEntryRef": "moderate#adjective#B1",
                            "headword": "moderate",
                            "cefr": "B1",
                        }
                    )
                    + "\n"
                )
            output = root / "draft.jsonl"

            result = self.run_cli(
                root,
                "prepare-enrichment",
                "--input-dir",
                str(input_dir),
                "--existing-seed",
                str(existing_seed),
                "--basic",
                "0",
                "--intermediate",
                "0",
                "--advanced",
                "1",
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["plain"], "moderate")

    def test_prepare_enrichment_matches_translation_to_the_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            (input_dir / "cow.jsonl").unlink()
            template = json.loads((input_dir / "freedict.jsonl").read_text().splitlines()[0])
            wrong = {
                **template,
                "sourceEntryRef": "entry-1-sense-1",
                "definitions": ["ordinary or average in quality"],
                "translations": {"zh": ["一般"]},
            }
            right = {
                **template,
                "sourceEntryRef": "entry-1-sense-2",
                "definitions": ["of very high quality"],
                "translations": {"zh": ["卓越"]},
            }
            (input_dir / "freedict.jsonl").write_text(
                json.dumps(wrong, ensure_ascii=False) + "\n" + json.dumps(right, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            output = root / "draft.jsonl"

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
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["translationDraft"], "卓越")

    def test_prepare_enrichment_orders_parallel_translations_from_one_source_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            freedict = json.loads((input_dir / "freedict.jsonl").read_text())
            freedict["translations"] = {"zh": ["優秀品質", "優秀"]}
            (input_dir / "freedict.jsonl").write_text(
                json.dumps(freedict, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            output = root / "draft.jsonl"

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
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(output.read_text())["translationDraft"], "優秀品質"
            )

    def test_prepare_enrichment_rejects_an_unmatched_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            (input_dir / "cow.jsonl").unlink()
            record = json.loads((input_dir / "freedict.jsonl").read_text().splitlines()[0])
            record["definitions"] = ["a device for cooking food"]
            record["translations"] = {"zh": ["烤箱"]}
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

    def test_prepare_enrichment_falls_back_to_aligned_freedict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            cedict = {
                **json.loads((input_dir / "freedict.jsonl").read_text()),
                "sourceID": "cc-cedict-2026-07-11",
                "sourceEntryRef": "line-1:unrelated",
                "headword": "unrelated",
                "definitions": ["not connected"],
                "translations": {"zh-Hant": ["無關"]},
            }
            (input_dir / "cedict.jsonl").write_text(
                json.dumps(cedict, ensure_ascii=False) + "\n", encoding="utf-8"
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

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads((root / "draft.jsonl").read_text())
            self.assertEqual(packet["translationDraft"], "優秀")
            self.assertIn(
                "freedict",
                {reference["sourceID"] for reference in packet["sourceRefs"]},
            )

    def test_prepare_enrichment_prefers_aligned_cedict_over_aligned_freedict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            (input_dir / "cow.jsonl").unlink()
            cedict = {
                **json.loads((input_dir / "freedict.jsonl").read_text()),
                "sourceID": "cc-cedict-2026-07-11",
                "sourceEntryRef": "line-1:excellent",
                "translations": {"zh-Hant": ["出色"]},
            }
            (input_dir / "cedict.jsonl").write_text(
                json.dumps(cedict, ensure_ascii=False) + "\n", encoding="utf-8"
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

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads((root / "draft.jsonl").read_text())
            self.assertEqual(packet["translationDraft"], "出色")
            source_ids = {
                reference["sourceID"] for reference in packet["sourceRefs"]
            }
            self.assertIn("cc-cedict-2026-07-11", source_ids)
            self.assertNotIn("freedict", source_ids)

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

    def test_prepare_enrichment_prefers_exact_ili_sense_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            lexical_path = input_dir / "oewn-2025.jsonl"
            lexical = json.loads(lexical_path.read_text())
            lexical["iliRefs"] = ["i1"]
            lexical_path.write_text(json.dumps(lexical) + "\n", encoding="utf-8")
            cow = {
                **json.loads((input_dir / "cow.jsonl").read_text()),
                "headword": "卓越+\u7684",
                "senseRefs": ["0001-a"],
            }
            (input_dir / "cow.jsonl").write_text(
                json.dumps(cow, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            mapping = {
                **cow,
                "sourceID": "omw-ili-map",
                "sourceEntryRef": "0001-a",
                "headword": "0001-a",
                "translations": {},
                "iliRefs": ["i1"],
            }
            (input_dir / "omw.jsonl").write_text(
                json.dumps(mapping, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            output = root / "draft.jsonl"

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
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            candidate = json.loads(output.read_text())
            self.assertEqual(candidate["translationDraft"], "卓越")
            self.assertEqual(
                {item["sourceID"] for item in candidate["sourceRefs"]},
                {"cefr", "cow", "oewn-2025", "omw-ili-map"},
            )

    def test_prepare_enrichment_applies_reviewed_sense_translation_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            lexical_path = input_dir / "oewn-2025.jsonl"
            lexical = json.loads(lexical_path.read_text())
            lexical["iliRefs"] = ["i15746"]
            lexical_path.write_text(json.dumps(lexical) + "\n", encoding="utf-8")
            cow = {
                **json.loads((input_dir / "cow.jsonl").read_text()),
                "headword": "观念+的",
                "senseRefs": ["02784317-a"],
            }
            (input_dir / "cow.jsonl").write_text(
                json.dumps(cow, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            mapping = {
                **cow,
                "sourceID": "omw-ili-map",
                "sourceEntryRef": "02784317-a",
                "headword": "02784317-a",
                "translations": {},
                "iliRefs": ["i15746"],
            }
            (input_dir / "omw.jsonl").write_text(
                json.dumps(mapping, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            output = root / "draft.jsonl"

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
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["translationDraft"], "呈現的")

    def test_prepare_enrichment_uses_a_matched_synonym_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            (input_dir / "cow.jsonl").unlink()
            lexical = json.loads((input_dir / "oewn-2025.jsonl").read_text().splitlines()[0])
            lexical["relatedTerms"] = ["excellent", "superb"]
            (input_dir / "oewn-2025.jsonl").write_text(
                json.dumps(lexical, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            direct = json.loads((input_dir / "freedict.jsonl").read_text().splitlines()[0])
            direct["definitions"] = ["a device for cooking food"]
            direct["translations"] = {"zh": ["烤箱"]}
            synonym = {
                **direct,
                "sourceEntryRef": "entry-superb",
                "headword": "superb",
                "definitions": ["of very high quality"],
                "translations": {"zh": ["卓越"]},
            }
            (input_dir / "freedict.jsonl").write_text(
                json.dumps(direct, ensure_ascii=False)
                + "\n"
                + json.dumps(synonym, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            output = root / "draft.jsonl"

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
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["translationDraft"], "卓越")

    def test_prepare_enrichment_requires_the_target_in_the_source_example(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            lexical_path = input_dir / "oewn-2025.jsonl"
            lexical = json.loads(lexical_path.read_text())
            lexical["examples"] = ["She shared a superb idea."]
            lexical_path.write_text(json.dumps(lexical) + "\n", encoding="utf-8")
            (input_dir / "tatoeba.jsonl").unlink()

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

    def test_prepare_enrichment_fails_when_a_level_quota_is_unavailable(self):
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
                "--basic",
                "2",
                "--intermediate",
                "0",
                "--advanced",
                "0",
                "--output",
                str(root / "draft.jsonl"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("basic", result.stderr)

    def test_verify_rejects_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root, checksum="0" * 64)

            result = self.run_cli(root, "verify", "--source", "demo")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checksum", result.stderr.lower())

    def test_import_is_deterministic_and_deduplicates_normalized_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root)
            first = root / "first.jsonl"
            second = root / "second.jsonl"

            first_run = self.run_cli(root, "import-source", "demo", "--output", str(first))
            second_run = self.run_cli(root, "import-source", "demo", "--output", str(second))

            self.assertEqual(first_run.returncode, 0, first_run.stderr)
            self.assertEqual(second_run.returncode, 0, second_run.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            records = [json.loads(line) for line in first.read_text().splitlines()]
            self.assertEqual([record["headword"] for record in records], ["Alpha", "beta"])
            self.assertTrue(all(record["sourceID"] == "demo" for record in records))

            report = self.run_cli(root, "report", "--input-dir", str(first.parent))
            self.assertEqual(report.returncode, 0, report.stderr)
            summary = json.loads(report.stdout)["summary"]
            self.assertEqual(summary["records"], 4)
            self.assertEqual(summary["uniqueHeadwords"], 2)

    def test_import_is_deterministic_when_merged_values_normalize_equally(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = self.make_source(root)
            raw = root / "Content/Sources/Raw/demo/words.csv"
            raw.write_text("Alpha,rock'n'roll\nalpha,rock’n’roll\n", encoding="utf-8")
            manifest = json.loads(manifest_path.read_text())
            manifest["sources"][0]["rawFile"] = {
                "path": "Content/Sources/Raw/demo/words.csv",
                "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                "bytes": raw.stat().st_size,
            }
            manifest_path.write_text(json.dumps(manifest))
            outputs = []

            for hash_seed in map(str, range(1, 17)):
                output = root / f"seed-{hash_seed}.jsonl"
                result = self.run_cli(
                    root,
                    "import-source",
                    "demo",
                    "--output",
                    str(output),
                    hash_seed=hash_seed,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(output.read_bytes())

            self.assertEqual(len(set(outputs)), 1)

    def test_promote_fails_closed_when_source_rights_are_not_approved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root)
            reviewed = root / "reviewed.json"
            reviewed.write_text("[]", encoding="utf-8")
            provenance = root / "provenance.json"
            provenance.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "demo",
                                "rights": {
                                    "commercialUse": "unknown",
                                    "reproduction": "approved",
                                    "redistribution": "approved",
                                    "modification": "approved",
                                    "translatedDerivatives": "approved",
                                },
                            }
                        ],
                        "items": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "notices.txt").write_text("", encoding="utf-8")

            result = self.run_cli(
                root,
                "promote",
                "--reviewed",
                str(reviewed),
                "--provenance",
                str(provenance),
                "--notices",
                str(root / "notices.txt"),
                "--output",
                str(root / "seed.json"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rights", result.stderr.lower())

    def test_promote_checks_every_source_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed, provenance, notices = self.make_promotable_bank(root)
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["sources"].append(
                {**manifest["sources"][0], "id": "blocked", "appUse": "blocked"}
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            data = json.loads(provenance.read_text())
            data["sources"].append({**data["sources"][0], "id": "blocked"})
            data["items"][0]["sourceIDs"] = ["demo", "blocked"]
            provenance.write_text(json.dumps(data), encoding="utf-8")

            result = self.run_cli(
                root,
                "promote",
                "--reviewed",
                str(reviewed),
                "--provenance",
                str(provenance),
                "--notices",
                str(notices),
                "--output",
                str(root / "seed.json"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("blocked", result.stderr)

    def test_promote_rejects_unknown_validation_source_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed, provenance, notices = self.make_promotable_bank(root)
            data = json.loads(provenance.read_text())
            data["items"][0]["validationSourceIDs"] = ["missing-source"]
            provenance.write_text(json.dumps(data), encoding="utf-8")

            result = self.run_cli(
                root,
                "promote",
                "--reviewed",
                str(reviewed),
                "--provenance",
                str(provenance),
                "--notices",
                str(notices),
                "--output",
                str(root / "seed.json"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("validation source", result.stderr.lower())

    def test_promote_rejects_blocked_validation_source_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed, provenance, notices = self.make_promotable_bank(root)
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["sources"].append(
                {
                    **manifest["sources"][0],
                    "id": "blocked",
                    "appUse": "reference_only",
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            data = json.loads(provenance.read_text())
            data["items"][0]["validationSourceIDs"] = ["demo", "blocked"]
            provenance.write_text(json.dumps(data), encoding="utf-8")

            result = self.run_cli(
                root,
                "promote",
                "--reviewed",
                str(reviewed),
                "--provenance",
                str(provenance),
                "--notices",
                str(notices),
                "--output",
                str(root / "seed.json"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not approved for app use", result.stderr)

    def test_promote_requires_every_source_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed, provenance, notices = self.make_promotable_bank(root)
            notices.write_text("", encoding="utf-8")

            result = self.run_cli(
                root,
                "promote",
                "--reviewed",
                str(reviewed),
                "--provenance",
                str(provenance),
                "--notices",
                str(notices),
                "--output",
                str(root / "seed.json"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("notice", result.stderr.lower())

    def test_promote_requires_cefr_to_match_the_app_level(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed, provenance, notices = self.make_promotable_bank(root)
            data = json.loads(provenance.read_text())
            data["items"][0]["cefr"] = "C1"
            provenance.write_text(json.dumps(data), encoding="utf-8")

            result = self.run_cli(
                root,
                "promote",
                "--reviewed",
                str(reviewed),
                "--provenance",
                str(provenance),
                "--notices",
                str(notices),
                "--output",
                str(root / "seed.json"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CEFR", result.stderr)

    def test_promote_rejects_missing_localized_content(self):
        for field in ("example", "prompt"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                reviewed, provenance, notices = self.make_promotable_bank(root)
                items = json.loads(reviewed.read_text())
                if field == "example":
                    items[0]["senses"][0]["example"]["translation"][
                        "zh-Hant"
                    ] = ""
                else:
                    items[0]["quiz"]["prompt"]["zh-Hant"] = ""
                reviewed.write_text(json.dumps(items), encoding="utf-8")

                result = self.run_cli(
                    root,
                    "promote",
                    "--reviewed",
                    str(reviewed),
                    "--provenance",
                    str(provenance),
                    "--notices",
                    str(notices),
                    "--output",
                    str(root / "seed.json"),
                )

                self.assertNotEqual(result.returncode, 0)
                expected = {
                    "example": "bilingual sense",
                    "prompt": "invalid quiz",
                }[field]
                self.assertIn(expected, result.stderr.lower())

    def test_promote_rejects_duplicate_upgraded_expressions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed, provenance, notices = self.make_promotable_bank(root)
            items = json.loads(reviewed.read_text())
            items.append({**items[0], "id": "basic-002", "sortOrder": 2})
            reviewed.write_text(json.dumps(items), encoding="utf-8")
            data = json.loads(provenance.read_text())
            data["items"].append(
                {
                    **data["items"][0],
                    "itemID": "basic-002",
                    "conceptKey": "expression:excellent-copy",
                }
            )
            provenance.write_text(json.dumps(data), encoding="utf-8")

            result = self.run_cli(
                root,
                "promote",
                "--reviewed",
                str(reviewed),
                "--provenance",
                str(provenance),
                "--notices",
                str(notices),
                "--output",
                str(root / "seed.json"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate upgraded expression", result.stderr)

    def test_promote_writes_a_fully_reviewed_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed, provenance, notices = self.make_promotable_bank(root)
            output = root / "seed.json"

            result = self.run_cli(
                root,
                "promote",
                "--reviewed",
                str(reviewed),
                "--provenance",
                str(provenance),
                "--notices",
                str(notices),
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())[0]["id"], "basic-001")


if __name__ == "__main__":
    unittest.main()
