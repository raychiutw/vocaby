import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("vocabulary_sources.py")


class VocabularySourcesTests(unittest.TestCase):
    def run_cli(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), *arguments],
            text=True,
            capture_output=True,
            check=False,
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
        reviewed.write_text(
            json.dumps(
                [
                    {
                        "id": "basic-001",
                        "level": "basic",
                        "sortOrder": 1,
                        "contentLanguageCode": "en",
                        "supportLanguageCodes": ["zh-Hant"],
                        "plainExpression": "very good",
                        "upgradedExpression": "excellent",
                        "meaning": {"en": "Very good.", "zh-Hant": "非常好。"},
                        "example": {
                            "text": "Excellent work.",
                            "translation": {"zh-Hant": "做得很好。"},
                        },
                        "pronunciationText": "excellent",
                        "quiz": {
                            "prompt": {"en": "Choose.", "zh-Hant": "請選擇。"},
                            "options": ["excellent", "poor"],
                            "correctOptionIndex": 0,
                        },
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
                    "appUse": "reference_only",
                }
                for source_id in ("oewn-2025", "freedict", "cefr", "cow")
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

    def test_shared_enrichment_builds_complete_app_fields_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            license_file = root / "Content/Sources/Raw/oewn/LICENSE.txt"
            license_file.parent.mkdir(parents=True)
            license_file.write_text("FULL DEMO LICENSE\n", encoding="utf-8")
            manifest_path = root / "Content/Sources/source-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["sources"][0]["noticeFiles"] = [
                "Content/Sources/Raw/oewn/LICENSE.txt"
            ]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
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
            seed = root / "seed.json"
            provenance = root / "provenance.json"
            notices = root / "notices.txt"
            build = self.run_cli(
                root,
                "build-reviewed",
                "--input",
                str(draft),
                "--existing-seed",
                str(existing_seed),
                "--seed-output",
                str(seed),
                "--provenance-output",
                str(provenance),
                "--notices-output",
                str(notices),
            )

            self.assertEqual(build.returncode, 0, build.stderr)
            item = json.loads(seed.read_text())[0]
            self.assertEqual(item["plainExpression"], "very good")
            self.assertEqual(item["upgradedExpression"], "excellent")
            self.assertEqual(item["meaning"]["zh-Hant"], "優秀")
            self.assertEqual(item["example"]["text"], "She shared an excellent idea.")
            self.assertIn("優秀", item["example"]["translation"]["zh-Hant"])
            self.assertEqual(item["quiz"]["correctOptionIndex"], 0)
            provenance_item = json.loads(provenance.read_text())["items"][0]
            self.assertEqual(provenance_item["sourceIDs"], ["cefr", "freedict", "oewn-2025"])
            self.assertEqual(provenance_item["status"], "approved")
            self.assertIn("FULL DEMO LICENSE", notices.read_text())

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
            seed = root / "seed.json"
            result = self.run_cli(
                root,
                "build-reviewed",
                "--input",
                str(draft),
                "--existing-seed",
                str(existing_seed),
                "--seed-output",
                str(seed),
                "--provenance-output",
                str(root / "provenance.json"),
                "--notices-output",
                str(root / "notices.txt"),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(seed.read_text())[0]["meaning"]["zh-Hant"], "原住民上方縮寫")

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
                    items[0]["example"]["translation"]["zh-Hant"] = ""
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
                self.assertIn("required text", result.stderr.lower())

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
