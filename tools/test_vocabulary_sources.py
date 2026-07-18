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

    def test_select_target_candidates_rejects_raw_inflection_senses(self):
        lemma = self.target_candidate("reduce", utility="general")
        inflection = self.target_candidate(
            "reduces", utility="general", tags=["form-of", "third-person"]
        )

        with self.assertRaisesRegex(
            vocabulary_sources.SourceError, "only 1 eligible candidate"
        ):
            vocabulary_sources.select_target_candidates(
                [inflection, lemma], [], target_count=2
            )

    def test_snapshot_target_selection_allows_pending_pronunciation_only(self):
        candidate = self.target_candidate("itinerary", utility="travel")
        candidate["candidatePronunciations"] = []

        with self.assertRaisesRegex(
            vocabulary_sources.SourceError, "only 0 eligible candidates"
        ):
            vocabulary_sources.select_target_candidates(
                [candidate], [], target_count=1
            )

        selected = vocabulary_sources.select_target_candidates(
            [candidate], [], target_count=1, require_pronunciation=False
        )

        self.assertEqual([item["target"] for item in selected], ["itinerary"])

    def test_lexical_variants_split_wiktextract_senses(self):
        record = {
            "sourceID": "wiktextract-en-2026-07-09",
            "sourceEntryRef": "book#noun#1",
            "headword": "book",
            "partOfSpeech": "noun",
            "cefr": "A1",
            "definitions": ["A written work.", "To reserve."],
            "examples": ["I read a book.", "Please book a room."],
            "relatedTerms": ["volume", "reserve"],
            "iliRefs": [],
            "senses": [
                {
                    "id": "book-noun",
                    "partOfSpeech": "noun",
                    "glosses": ["A written work."],
                    "examples": ["I read a book."],
                    "translations": {},
                    "tags": [],
                },
                {
                    "id": "book-verb",
                    "partOfSpeech": "verb",
                    "glosses": ["To reserve."],
                    "examples": ["Please book a room."],
                    "translations": {},
                    "tags": [],
                },
            ],
        }

        variants = vocabulary_sources.lexical_variants(record)

        self.assertEqual(
            [
                (
                    item["partOfSpeech"],
                    item["definitions"],
                    item["examples"],
                    item["senseRefs"],
                )
                for item in variants
            ],
            [
                ("noun", ["A written work."], ["I read a book."], ["book-noun"]),
                ("verb", ["To reserve."], ["Please book a room."], ["book-verb"]),
            ],
        )

    def test_prepare_100k_snapshot_mode_keeps_lexical_target_pending_pronunciation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()
            (input_dir / "lex.jsonl").write_text(
                json.dumps(
                    {
                        "sourceID": "lex",
                        "sourceEntryRef": "itinerary#noun#1",
                        "headword": "itinerary",
                        "partOfSpeech": "noun",
                        "cefr": None,
                        "definitions": ["A planned route for a journey."],
                        "examples": ["Our itinerary includes three cities."],
                        "relatedTerms": [],
                        "translations": {},
                        "pronunciations": [],
                        "forms": [],
                        "senses": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            retained = root / "retained.json"
            retained.write_text("[]", encoding="utf-8")
            output = root / "targets.jsonl"

            with self.assertRaisesRegex(
                vocabulary_sources.SourceError, "only 0 eligible candidates"
            ):
                vocabulary_sources.prepare_100k(
                    input_dir,
                    retained,
                    output,
                    {"lex"},
                    target_count=1,
                    reserve_count=0,
                )

            result = vocabulary_sources.prepare_100k(
                input_dir,
                retained,
                output,
                {"lex"},
                target_count=1,
                reserve_count=0,
                snapshot_targets=True,
            )

            self.assertEqual(result, {"retained": 0, "target": 1, "reserve": 0})
            self.assertEqual(json.loads(output.read_text())["target"], "itinerary")

    def test_translation_sources_do_not_create_english_lexical_senses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()
            rows = [
                {
                    "sourceID": "cc-cedict-2026-07-11",
                    "sourceEntryRef": "line-1:籃子",
                    "headword": "a basket carried on the back",
                    "partOfSpeech": None,
                    "cefr": None,
                    "definitions": ["a basket carried on the back"],
                    "examples": [],
                    "relatedTerms": [],
                    "translations": {"zh-Hant": ["背簍"]},
                    "pronunciations": [],
                    "forms": [],
                    "senses": [],
                },
                {
                    "sourceID": "pron",
                    "sourceEntryRef": "pron:a basket carried on the back",
                    "headword": "a basket carried on the back",
                    "partOfSpeech": None,
                    "cefr": None,
                    "definitions": [],
                    "examples": [],
                    "relatedTerms": [],
                    "translations": {},
                    "pronunciations": [
                        {
                            "notation": "ipa",
                            "value": "ə bɑːskɪt",
                            "speechLocale": "en-US",
                            "region": "General",
                            "tags": [],
                        }
                    ],
                    "forms": [],
                    "senses": [],
                },
            ]
            for source_id in ("cc-cedict-2026-07-11", "pron"):
                (input_dir / f"{source_id}.jsonl").write_text(
                    "".join(
                        json.dumps(row) + "\n"
                        for row in rows
                        if row["sourceID"] == source_id
                    ),
                    encoding="utf-8",
                )

            candidates = vocabulary_sources.assemble_target_candidates(
                input_dir,
                {"cc-cedict-2026-07-11", "pron"},
                set(),
            )

            candidate = next(
                item
                for item in candidates
                if item["target"] == "a basket carried on the back"
            )
            self.assertEqual(candidate["candidateSenses"], [])

    def test_assemble_target_candidates_prioritizes_trusted_cefr_part_before_truncating(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            rows = [
                {
                    "sourceID": "cefr-j-1.6",
                    "sourceEntryRef": "at#preposition#A1",
                    "headword": "at",
                    "partOfSpeech": "preposition",
                    "cefr": "A1",
                    "definitions": [],
                    "examples": [],
                    "senses": [],
                    "pronunciations": [],
                    "forms": [],
                },
                *[
                    {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": f"at#noun#{index}",
                        "headword": "at",
                        "partOfSpeech": "noun",
                        "cefr": None,
                        "definitions": [f"unrelated noun sense {index}"],
                        "examples": [],
                        "senses": [],
                        "pronunciations": [],
                        "forms": [],
                    }
                    for index in range(3)
                ],
                {
                    "sourceID": "wiktextract-en-2026-07-09",
                    "sourceEntryRef": "at#prep#1",
                    "headword": "at",
                    "partOfSpeech": "preposition",
                    "cefr": None,
                    "definitions": ["In or near a particular place."],
                    "examples": ["Meet me at the station."],
                    "senses": [],
                    "pronunciations": [
                        {
                            "notation": "ipa",
                            "value": "æt",
                            "speechLocale": "en-US",
                            "region": "General",
                            "tags": [],
                        }
                    ],
                    "forms": [],
                },
            ]
            (input_dir / "records.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            candidate = vocabulary_sources.assemble_target_candidates(
                input_dir,
                {"cefr-j-1.6", "oewn-2025", "wiktextract-en-2026-07-09"},
                set(),
            )[0]

            self.assertEqual(candidate["trustedCEFRParts"], ["preposition"])
            self.assertEqual(
                [sense["partOfSpeech"] for sense in candidate["candidateSenses"]],
                ["preposition"],
            )
            self.assertEqual(
                candidate["candidateSenses"][0]["glosses"],
                ["In or near a particular place."],
            )

    def test_assemble_target_candidates_rejects_untrusted_inflection_side_sense(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            rows = [
                {
                    "sourceID": "wiktextract-en-2026-07-09",
                    "sourceEntryRef": "asked#adj#1",
                    "headword": "asked",
                    "partOfSpeech": "adjective",
                    "cefr": None,
                    "definitions": ["Arsed; willing to make an effort."],
                    "examples": [],
                    "senses": [],
                    "pronunciations": [
                        {
                            "notation": "ipa",
                            "value": "æskt",
                            "speechLocale": "en-US",
                            "region": "General",
                            "tags": [],
                        }
                    ],
                    "forms": [],
                },
                {
                    "sourceID": "wiktextract-en-2026-07-09",
                    "sourceEntryRef": "asked#verb#1",
                    "headword": "asked",
                    "partOfSpeech": "verb",
                    "cefr": None,
                    "definitions": ["simple past of ask"],
                    "examples": [],
                    "senses": [
                        {
                            "id": "asked-form",
                            "partOfSpeech": "verb",
                            "glosses": ["simple past of ask"],
                            "examples": [],
                            "tags": ["form-of", "past"],
                        }
                    ],
                    "pronunciations": [],
                    "forms": [],
                },
            ]
            (input_dir / "records.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            candidates = vocabulary_sources.assemble_target_candidates(
                input_dir,
                {"wiktextract-en-2026-07-09"},
                set(),
            )

            with self.assertRaisesRegex(
                vocabulary_sources.SourceError,
                "only 0 eligible candidates",
            ):
                vocabulary_sources.select_target_candidates(
                    candidates,
                    [],
                    target_count=1,
                )

    def test_assemble_and_review_keep_inflection_with_trusted_cefr_part(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            rows = [
                {
                    "sourceID": "cefr-j-1.6",
                    "sourceEntryRef": "did#do-verb#A1",
                    "headword": "did",
                    "partOfSpeech": "do-verb",
                    "cefr": "A1",
                    "definitions": [],
                    "examples": [],
                    "senses": [],
                    "pronunciations": [],
                    "forms": [],
                },
                {
                    "sourceID": "wiktextract-en-2026-07-09",
                    "sourceEntryRef": "did#verb#1",
                    "headword": "did",
                    "partOfSpeech": "verb",
                    "cefr": None,
                    "definitions": ["simple past of do"],
                    "examples": ["I did the work before lunch."],
                    "senses": [
                        {
                            "id": "did-form",
                            "partOfSpeech": "verb",
                            "glosses": ["simple past of do"],
                            "examples": ["I did the work before lunch."],
                            "tags": ["form-of", "past"],
                        }
                    ],
                    "pronunciations": [],
                    "forms": [],
                },
            ]
            (input_dir / "records.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            candidate = vocabulary_sources.assemble_target_candidates(
                input_dir,
                {"cefr-j-1.6", "wiktextract-en-2026-07-09"},
                set(),
            )[0]
            candidate["partOfSpeech"] = "verb"

            self.assertEqual(
                [sense["id"] for sense in candidate["candidateSenses"]],
                ["did-form"],
            )
            self.assertEqual(
                [sense["id"] for sense in vocabulary_sources.review_senses(candidate)],
                ["did-form"],
            )
            selected = vocabulary_sources.select_target_candidates(
                [candidate],
                [],
                target_count=1,
                require_pronunciation=False,
            )
            self.assertEqual(selected[0]["target"], "did")

    def test_assemble_target_candidates_preserves_primary_source_sense_order(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            rows = [
                {
                    "sourceID": "cefr-j-1.6",
                    "sourceEntryRef": "she#pronoun#A1",
                    "headword": "she",
                    "partOfSpeech": "pronoun",
                    "cefr": "A1",
                    "definitions": [],
                    "examples": [],
                    "senses": [],
                    "pronunciations": [],
                    "forms": [],
                },
                {
                    "sourceID": "wiktextract-en-2026-07-09",
                    "sourceEntryRef": "she#pron#1",
                    "headword": "she",
                    "partOfSpeech": "pronoun",
                    "cefr": None,
                    "definitions": [],
                    "examples": [],
                    "senses": [
                        {
                            "id": "z-common",
                            "partOfSpeech": "pronoun",
                            "glosses": ["The female person previously mentioned."],
                            "examples": ["She called this morning."],
                            "tags": [],
                        },
                        {
                            "id": "a-ship",
                            "partOfSpeech": "pronoun",
                            "glosses": ["A ship or boat."],
                            "examples": [
                                "She sailed at dawn.",
                                "She entered the harbor before noon.",
                            ],
                            "tags": [],
                        },
                        {
                            "id": "weather",
                            "partOfSpeech": "pronoun",
                            "glosses": ["A country or nation."],
                            "examples": [],
                            "tags": [],
                        },
                        {
                            "id": "personified-object",
                            "partOfSpeech": "pronoun",
                            "glosses": ["A personified object."],
                            "examples": [],
                            "tags": [],
                        },
                    ],
                    "pronunciations": [
                        {
                            "notation": "ipa",
                            "value": "ʃiː",
                            "speechLocale": "en-US",
                            "region": "General",
                            "tags": [],
                        }
                    ],
                    "forms": [],
                },
            ]
            (input_dir / "records.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            candidate = vocabulary_sources.assemble_target_candidates(
                input_dir,
                {"cefr-j-1.6", "wiktextract-en-2026-07-09"},
                set(),
            )[0]

            self.assertEqual(candidate["candidateSenses"][0]["id"], "z-common")
            self.assertEqual(len(candidate["candidateSenses"]), 4)

    def test_review_senses_uses_source_order_as_final_tiebreaker(self):
        packet = {
            "id": "vocab-she",
            "target": "she",
            "sourceRefs": [],
            "candidateSenses": [
                {
                    "id": "z-common",
                    "partOfSpeech": "pronoun",
                    "glosses": ["The female person previously mentioned."],
                    "examples": [],
                    "tags": [],
                    "sourceRef": {"sourceID": "wiktextract", "sourceEntryRef": "she"},
                },
                {
                    "id": "a-ship",
                    "partOfSpeech": "pronoun",
                    "glosses": ["A ship or boat."],
                    "examples": ["She sailed at dawn."],
                    "tags": [],
                    "sourceRef": {"sourceID": "wiktextract", "sourceEntryRef": "she"},
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "z-common")

    def test_assemble_target_candidates_marks_pn_records_as_proper(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            rows = [
                {
                    "sourceID": "freedict-eng-zho-2025.11.23",
                    "sourceEntryRef": "japan#place",
                    "headword": "Japan",
                    "partOfSpeech": "pn",
                    "cefr": None,
                    "definitions": ["A country in East Asia."],
                    "examples": [],
                    "senses": [],
                    "pronunciations": [],
                    "forms": [],
                },
                {
                    "sourceID": "wiktextract-en-2026-07-09",
                    "sourceEntryRef": "japan#noun",
                    "headword": "japan",
                    "partOfSpeech": "noun",
                    "cefr": None,
                    "definitions": ["A glossy black lacquer."],
                    "examples": [],
                    "senses": [],
                    "pronunciations": [
                        {
                            "notation": "ipa",
                            "value": "dʒəpæn",
                            "speechLocale": "en-US",
                            "region": "General",
                            "tags": [],
                        }
                    ],
                    "forms": [],
                },
            ]
            (input_dir / "records.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            candidate = vocabulary_sources.assemble_target_candidates(
                input_dir,
                {"freedict-eng-zho-2025.11.23", "wiktextract-en-2026-07-09"},
                set(),
            )[0]

            self.assertTrue(candidate["isProperName"])

    def test_canonical_part_of_speech_maps_cefr_auxiliary_labels_to_verb(self):
        self.assertEqual(
            {
                value: vocabulary_sources.canonical_part_of_speech(value)
                for value in ("be-verb", "do-verb", "have-verb", "modal auxiliary")
            },
            {
                "be-verb": "verb",
                "do-verb": "verb",
                "have-verb": "verb",
                "modal auxiliary": "verb",
            },
        )

    def test_assemble_target_candidates_prefers_richer_wiktextract_sense_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            rows = [
                {
                    "sourceID": "oewn-2025",
                    "sourceEntryRef": "phone#n#earpiece",
                    "headword": "phone",
                    "partOfSpeech": "noun",
                    "cefr": None,
                    "definitions": ["An electro-acoustic earpiece."],
                    "examples": ["The operator wore a phone."],
                    "senses": [],
                    "pronunciations": [],
                    "forms": [],
                },
                {
                    "sourceID": "wiktextract-en-2026-07-09",
                    "sourceEntryRef": "phone#noun#1",
                    "headword": "phone",
                    "partOfSpeech": "noun",
                    "cefr": None,
                    "definitions": ["A device used to speak with someone at a distance."],
                    "examples": [
                        "My phone rang.",
                        "Please answer the phone.",
                        "She called me on the phone.",
                    ],
                    "senses": [],
                    "pronunciations": [
                        {
                            "notation": "ipa",
                            "value": "foʊn",
                            "speechLocale": "en-US",
                            "region": "General",
                            "tags": [],
                        }
                    ],
                    "forms": [],
                },
            ]
            (input_dir / "records.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            candidate = vocabulary_sources.assemble_target_candidates(
                input_dir,
                {"oewn-2025", "wiktextract-en-2026-07-09"},
                set(),
            )[0]

            self.assertEqual(
                candidate["candidateSenses"][0]["sourceRef"]["sourceID"],
                "wiktextract-en-2026-07-09",
            )

    def test_assemble_target_candidates_prefers_wiktextract_before_other_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            input_dir = Path(directory)
            rows = [
                {
                    "sourceID": "grundwortschatz-voc-en-004977a",
                    "sourceEntryRef": "glasses#weak",
                    "headword": "glasses",
                    "partOfSpeech": "noun",
                    "cefr": "A2",
                    "definitions": ["An amorphous solid."],
                    "examples": ["Looking glasses were displayed."],
                    "senses": [],
                    "pronunciations": [],
                    "forms": [],
                },
                {
                    "sourceID": "wiktextract-en-2026-07-09",
                    "sourceEntryRef": "glasses#noun#1",
                    "headword": "glasses",
                    "partOfSpeech": "noun",
                    "cefr": None,
                    "definitions": ["Frames bearing two lenses worn in front of the eyes."],
                    "examples": [],
                    "senses": [],
                    "pronunciations": [],
                    "forms": [],
                },
            ]
            (input_dir / "records.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            candidate = vocabulary_sources.assemble_target_candidates(
                input_dir,
                {"grundwortschatz-voc-en-004977a", "wiktextract-en-2026-07-09"},
                set(),
            )[0]

            self.assertEqual(
                candidate["candidateSenses"][0]["sourceRef"]["sourceID"],
                "wiktextract-en-2026-07-09",
            )

    def test_review_senses_keeps_pre_ranked_wiktextract_ahead_of_oewn(self):
        packet = {
            "id": "vocab-phone",
            "target": "phone",
            "sourceRefs": [],
            "candidateSenses": [
                {
                    "id": "phone-common",
                    "partOfSpeech": "noun",
                    "glosses": ["A device used to speak with someone at a distance."],
                    "examples": ["Please answer the phone."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "phone#noun#1",
                    },
                },
                {
                    "id": "phone-earpiece",
                    "partOfSpeech": "noun",
                    "glosses": ["An electro-acoustic earpiece."],
                    "examples": ["The operator wore a phone."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "phone#n#earpiece",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "phone-common")

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

    def test_targets_to_seed_is_deterministic_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_input = root / "first.jsonl"
            second_input = root / "second.jsonl"
            first_output = root / "first.json"
            second_output = root / "second.json"
            rows = [{"target": "invoice"}, {"target": "breakfast"}]
            first_input.write_text(
                "".join(json.dumps(item) + "\n" for item in rows),
                encoding="utf-8",
            )
            second_input.write_text(
                "".join(json.dumps(item) + "\n" for item in reversed(rows)),
                encoding="utf-8",
            )

            first_count = vocabulary_sources.targets_to_seed(
                first_input, first_output
            )
            second_count = vocabulary_sources.targets_to_seed(
                second_input, second_output
            )

            self.assertEqual(first_count, 2)
            self.assertEqual(first_output.read_bytes(), second_output.read_bytes())
            self.assertEqual(
                json.loads(first_output.read_text()),
                [
                    {"upgradedExpression": "breakfast"},
                    {"upgradedExpression": "invoice"},
                ],
            )

            second_input.write_text(
                json.dumps({"target": "invoice"})
                + "\n"
                + json.dumps({"target": "INVOICE"})
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(vocabulary_sources.SourceError, "duplicate"):
                vocabulary_sources.targets_to_seed(second_input, second_output)

    def test_targets_to_seed_includes_retained_snapshot_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue = root / "queue.jsonl"
            queue.write_text(
                json.dumps({"target": "itinerary"}) + "\n",
                encoding="utf-8",
            )
            retained = root / "retained.json"
            retained.write_text(
                json.dumps([{"upgradedExpression": "breakfast"}]),
                encoding="utf-8",
            )
            output = root / "targets.json"

            count = vocabulary_sources.targets_to_seed(
                queue, output, retained_path=retained
            )

            self.assertEqual(count, 2)
            self.assertEqual(
                json.loads(output.read_text()),
                [
                    {"upgradedExpression": "breakfast"},
                    {"upgradedExpression": "itinerary"},
                ],
            )

    def test_wiktextract_discovery_targets_add_verified_pronunciation_headwords(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()
            records = [
                {
                    "sourceID": "pron",
                    "sourceEntryRef": "itinerary",
                    "headword": "Itinerary",
                    "pronunciations": [
                        {"notation": "ipa", "value": "aɪˈtɪnərɛri"}
                    ],
                },
                {
                    "sourceID": "pron",
                    "sourceEntryRef": "missing",
                    "headword": "missing",
                    "pronunciations": [],
                },
                {
                    "sourceID": "blocked",
                    "sourceEntryRef": "blocked",
                    "headword": "blocked",
                    "pronunciations": [
                        {"notation": "ipa", "value": "blɒkt"}
                    ],
                },
            ]
            (input_dir / "records.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in records),
                encoding="utf-8",
            )
            retained = root / "targets.json"
            retained.write_text(
                json.dumps([{"upgradedExpression": "breakfast"}]),
                encoding="utf-8",
            )
            output = root / "discovery.json"

            count = vocabulary_sources.wiktextract_discovery_targets(
                input_dir, retained, output, {"pron"}
            )

            self.assertEqual(count, 2)
            self.assertEqual(
                json.loads(output.read_text()),
                [
                    {"upgradedExpression": "breakfast"},
                    {"upgradedExpression": "itinerary"},
                ],
            )

    def test_frozen_100k_baseline_inputs(self):
        expected_hashes = {
            "Vocaby/Resources/VocabularySeed.json": "0fad7a08386e7b9448448ce8dc2144dd6571d0614594a9c049d0e1147bb541d9",
            "Content/VocabularyProvenance.json": "eacf3d158eec48fab86f437e74975f3feff55145427201d8a3d8bfc7aa45188f",
            "Vocaby/Resources/ThirdPartyNotices.txt": "3f152459c424d7451fc08c3ea65f17e7d368d335bd78a93afda2307408e55d5c",
            "Content/Sources/source-manifest.json": "6b31b1c9d0790dbe7335f43b8bd768f780d2d6211fd91d7fdb14ac10e7500ec3",
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

    def test_rich_review_rejects_review_only_example_placeholder(self):
        item = self.rich_review_record()
        target = item["upgradedExpression"]
        item["senses"][0]["example"]["text"] = (
            f'The expression "{target}" is being reviewed.'
        )

        with self.assertRaisesRegex(
            vocabulary_sources.SourceError, "review-only example placeholder"
        ):
            vocabulary_sources.validate_reviewed_item(item)

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

    def test_rich_review_accepts_translation_ending_with_chinese_quote(self):
        item = self.rich_review_record()
        item["senses"][0]["example"]["translation"]["zh-Hant"] = (
            "她說：「讓我來帶領會議。」"
        )

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
                    "ipa": "ɪmˈpɝmənənt",
                    "speechLocale": "en-US",
                    "region": "General",
                }
            ],
        )
        self.assertEqual(references, [source_ref])

    def test_review_pronunciations_preserves_phrase_word_boundaries(self):
        pronunciations, _ = vocabulary_sources.review_pronunciations(
            "work shift",
            [
                {
                    "notation": "ipa",
                    "value": "wɝk ʃɪft",
                    "region": "General",
                }
            ],
            {},
        )

        self.assertEqual(pronunciations[0]["ipa"], "wɝk ʃɪft")

    def test_review_pronunciations_collapses_duplicate_rhotic_transcription(self):
        pronunciations, _ = vocabulary_sources.review_pronunciations(
            "spadework",
            [
                {
                    "notation": "ipa",
                    "value": "ˈspeɪdˌwɝɹk",
                    "region": "General",
                }
            ],
            {},
        )

        self.assertEqual(pronunciations[0]["ipa"], "ˈspeɪdˌwɝk")

    def test_review_pronunciations_does_not_add_cmudict_when_verified_ipa_exists(self):
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

        self.assertEqual(
            [item["region"] for item in pronunciations], ["General", "General"]
        )
        self.assertEqual(pronunciations[0]["id"], "leverage-general-1")
        self.assertNotIn(
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

    def test_review_senses_prefers_literal_sense_over_idiomatic_side_sense(self):
        packet = {
            "id": "long-time-1",
            "target": "long time",
            "definition": "",
            "partOfSpeech": "phrase",
            "candidateSenses": [
                {
                    "id": "greeting",
                    "partOfSpeech": "phrase",
                    "glosses": ["Used as part of a greeting."],
                    "examples": ["Long time no see!"],
                    "tags": ["idiomatic"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "long time#intj#1",
                    },
                },
                {
                    "id": "meta",
                    "partOfSpeech": "phrase",
                    "glosses": [
                        "Used other than figuratively or idiomatically: see long, time."
                    ],
                    "examples": ["You've been away for a long time."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "long time#phrase#1",
                    },
                },
                {
                    "id": "regional-adult-sense",
                    "partOfSpeech": "noun",
                    "glosses": ["An overnight meeting with a sex worker."],
                    "examples": [],
                    "tags": ["indonesia", "thailand"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "long time#noun#1",
                    },
                },
                {
                    "id": "literal",
                    "partOfSpeech": "noun",
                    "glosses": ["A prolonged period of time."],
                    "examples": [],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "long time#noun#1",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "literal")

    def test_review_senses_keeps_common_idiom_ahead_of_secondary_literal_sense(self):
        packet = {
            "id": "as-well-1",
            "target": "as well",
            "definition": "",
            "partOfSpeech": "phrase",
            "candidateSenses": [
                {
                    "id": "also",
                    "partOfSpeech": "adverb",
                    "glosses": ["In addition; also."],
                    "examples": ["Please bring an umbrella as well."],
                    "tags": ["idiomatic"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "as well#adv#1",
                    },
                },
                {
                    "id": "same-effect",
                    "partOfSpeech": "adverb",
                    "glosses": ["To the same effect."],
                    "examples": ["They might as well walk."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "as well#adv#2",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "also")

    def test_review_senses_keeps_an_exact_humorous_register_sense(self):
        source_ref = {
            "sourceID": "wiktextract-en-2026-07-09",
            "sourceEntryRef": "beauty sleep#noun#4452",
        }
        packet = {
            "id": "vocab-61d057fafd1d088a",
            "target": "beauty sleep",
            "definition": "Extra sleep; also (generally), any sleep; (countable) an instance of this; an extra nap.",
            "partOfSpeech": "noun",
            "selectionStatus": "target",
            "sourceRefs": [
                {
                    "sourceID": "oewn-2025",
                    "sourceEntryRef": "beauty sleep#n#15298861-n",
                },
                source_ref,
            ],
            "candidateSenses": [
                {
                    "id": "3ee40b1d9a120694",
                    "partOfSpeech": "noun",
                    "glosses": [
                        "Extra sleep; also (generally), any sleep; (countable) an instance of this; an extra nap."
                    ],
                    "examples": [],
                    "tags": ["humorous", "idiomatic", "uncountable"],
                    "sourceRef": source_ref,
                }
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "3ee40b1d9a120694")
        self.assertEqual(senses[0]["partOfSpeech"], "noun")
        self.assertEqual(senses[0]["sourceRef"], source_ref)

    def test_review_senses_does_not_promote_a_humorous_multi_candidate_target(self):
        humorous_ref = {
            "sourceID": "wiktextract-en-2026-07-09",
            "sourceEntryRef": "wise guy#noun#humorous",
        }
        packet = {
            "id": "wise-guy",
            "target": "wise guy",
            "definition": "A person who makes jokes at inappropriate times.",
            "partOfSpeech": "noun",
            "selectionStatus": "target",
            "sourceRefs": [humorous_ref],
            "candidateSenses": [
                {
                    "id": "humorous",
                    "partOfSpeech": "noun",
                    "glosses": ["A person who makes jokes at inappropriate times."],
                    "examples": [],
                    "tags": ["humorous"],
                    "sourceRef": humorous_ref,
                },
                {
                    "id": "neutral",
                    "partOfSpeech": "noun",
                    "glosses": ["A person regarded as clever or knowledgeable."],
                    "examples": [],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "wise guy#noun#neutral",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertNotEqual(senses[0]["id"], "humorous")

    def test_review_senses_does_not_promote_an_unanchored_humorous_target(self):
        packet = {
            "id": "vocab-61d057fafd1d088a",
            "target": "beauty sleep",
            "definition": "Extra sleep.",
            "partOfSpeech": "noun",
            "selectionStatus": "target",
            "sourceRefs": [
                {
                    "sourceID": "oewn-2025",
                    "sourceEntryRef": "beauty sleep#n#15298861-n",
                }
            ],
            "candidateSenses": [
                {
                    "id": "humorous",
                    "partOfSpeech": "noun",
                    "glosses": ["Extra sleep."],
                    "examples": [],
                    "tags": ["humorous"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "beauty sleep#noun#4452",
                    },
                }
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertNotEqual(senses[0]["id"], "humorous")

    def test_review_senses_does_not_promote_a_definitionless_humorous_target(self):
        source_ref = {
            "sourceID": "wiktextract-en-2026-07-09",
            "sourceEntryRef": "beauty sleep#noun#4452",
        }
        packet = {
            "id": "vocab-61d057fafd1d088a",
            "target": "beauty sleep",
            "definition": "",
            "partOfSpeech": "noun",
            "selectionStatus": "target",
            "sourceRefs": [source_ref],
            "candidateSenses": [
                {
                    "id": "humorous",
                    "partOfSpeech": "noun",
                    "glosses": ["Extra sleep."],
                    "examples": [],
                    "tags": ["humorous"],
                    "sourceRef": source_ref,
                }
            ],
        }

        self.assertEqual(vocabulary_sources.review_senses(packet), [])

    def test_review_senses_does_not_promote_humorous_without_target_status(self):
        source_ref = {
            "sourceID": "wiktextract-en-2026-07-09",
            "sourceEntryRef": "beauty sleep#noun#4452",
        }
        packet = {
            "id": "vocab-61d057fafd1d088a",
            "target": "beauty sleep",
            "definition": "Extra sleep.",
            "partOfSpeech": "noun",
            "sourceRefs": [source_ref],
            "candidateSenses": [
                {
                    "id": "humorous",
                    "partOfSpeech": "noun",
                    "glosses": ["Extra sleep."],
                    "examples": [],
                    "tags": ["humorous"],
                    "sourceRef": source_ref,
                }
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertNotEqual(senses[0]["id"], "humorous")

    def test_review_senses_prefers_verb_for_negative_contraction(self):
        packet = {
            "id": "should-not-1",
            "target": "shouldn't",
            "definition": "",
            "partOfSpeech": "phrase",
            "candidateSenses": [
                {
                    "id": "noun",
                    "partOfSpeech": "noun",
                    "glosses": ["Something that should not be done."],
                    "examples": [],
                    "tags": ["informal"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "shouldn't#noun#1",
                    },
                },
                {
                    "id": "verb",
                    "partOfSpeech": "verb",
                    "glosses": ["Should not (negative auxiliary)."],
                    "examples": [],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "shouldn't#verb#1",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "verb")

    def test_review_senses_prefers_contraction_over_regional_apostrophe_sense(self):
        packet = {
            "id": "that-is-1",
            "target": "that's",
            "definition": "",
            "partOfSpeech": "phrase",
            "candidateSenses": [
                {
                    "id": "regional-determiner",
                    "partOfSpeech": "determiner",
                    "glosses": ["Whose, in some regional dialects."],
                    "examples": ["The dog that's leg was hurt."],
                    "tags": ["canada", "northern-ireland"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "that's#det#1",
                    },
                },
                {
                    "id": "that-is",
                    "partOfSpeech": "phrase",
                    "glosses": ["That is."],
                    "examples": ["That's the book I need."],
                    "tags": ["contraction"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "that's#contraction#1",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "that-is")

    def test_review_senses_prefers_phrase_over_unrelated_noun_for_multiword_target(self):
        packet = {
            "id": "excuse-me-1",
            "target": "excuse me",
            "definition": "",
            "partOfSpeech": "phrase",
            "candidateSenses": [
                {
                    "id": "dance",
                    "partOfSpeech": "noun",
                    "glosses": ["An old-fashioned type of dance."],
                    "examples": [],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "excuse me#noun#1",
                    },
                },
                {
                    "id": "polite-request",
                    "partOfSpeech": "phrase",
                    "glosses": ["Said as a polite request for attention."],
                    "examples": [],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "excuse me#phrase#1",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "polite-request")

    def test_review_senses_drops_additional_part_without_trusted_cefr_evidence(self):
        packet = {
            "id": "bank-basic-0001",
            "target": "action",
            "definition": "something done to achieve a purpose",
            "example": "We need to take action today.",
            "partOfSpeech": "noun",
            "trustedCEFRParts": ["noun"],
            "sourceRefs": [
                {"sourceID": "oewn-2025", "sourceEntryRef": "action#n#1"}
            ],
            "candidateSenses": [
                {
                    "id": "action-noun",
                    "partOfSpeech": "noun",
                    "glosses": ["something done to achieve a purpose"],
                    "examples": ["We need to take action today."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "action#n#1",
                    },
                },
                {
                    "id": "action-verb",
                    "partOfSpeech": "verb",
                    "glosses": ["put into effect"],
                    "examples": ["We can action the request today."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "action#v#1",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual([sense["id"] for sense in senses], ["action-noun"])

    def test_review_senses_keeps_exact_primary_over_closer_unrelated_distance(self):
        packet = {
            "id": "bank-basic-0001",
            "target": "action",
            "definition": "the state of being active",
            "example": "Now is the time for action.",
            "partOfSpeech": "noun",
            "trustedCEFRParts": ["noun"],
            "sourceRefs": [
                {"sourceID": "oewn-2025", "sourceEntryRef": "action#n#active"}
            ],
            "candidateSenses": [
                {
                    "id": "action-betting",
                    "partOfSpeech": "noun",
                    "glosses": ["the opportunity to act during a betting round"],
                    "examples": ["The action moved to the next player."],
                    "tags": [],
                    "reviewDistance": 0.1,
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "action#noun#betting",
                    },
                },
                {
                    "id": "action-active",
                    "partOfSpeech": "noun",
                    "glosses": ["the state of being active"],
                    "examples": ["Now is the time for action."],
                    "tags": [],
                    "reviewDistance": 0.4,
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "action#n#active",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual([sense["id"] for sense in senses], ["action-active"])

    def test_review_senses_uses_the_exact_selected_gloss_from_a_multi_gloss_sense(self):
        packet = {
            "id": "bank-basic-0001",
            "target": "after",
            "definition": "Subsequently to; following in time; later than.",
            "example": "We had lunch after the meeting.",
            "partOfSpeech": "preposition",
            "candidateSenses": [
                {
                    "id": "after-preposition",
                    "partOfSpeech": "preposition",
                    "glosses": [
                        "Subsequently to; following in time; later than.",
                        "Subsequently to and in spite of.",
                    ],
                    "examples": ["We had lunch after the meeting."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "after#prep#1",
                    },
                }
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(
            senses[0]["meaning"],
            "Subsequently to; following in time; later than.",
        )

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

    def test_review_senses_hydrates_an_additional_sense_only_from_aligned_examples(self):
        packet = {
            "id": "bank-intermediate-0036",
            "target": "ache",
            "definition": "have a desire for something that is not present",
            "example": "She ached for a cigarette.",
            "partOfSpeech": "verb",
            "sourceRefs": [
                {"sourceID": "oewn-2025", "sourceEntryRef": "ache#v#1"}
            ],
            "candidateSenses": [
                {
                    "id": "ache#v#1",
                    "partOfSpeech": "verb",
                    "glosses": ["have a desire for something that is not present"],
                    "examples": ["She ached for a cigarette."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "ache#v#1",
                    },
                },
                {
                    "id": "ache#n#1",
                    "partOfSpeech": "noun",
                    "glosses": ["a dull persistent pain"],
                    "examples": [],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "oewn-2025",
                        "sourceEntryRef": "ache#n#1",
                    },
                },
                {
                    "id": "wiktextract-ache-noun",
                    "partOfSpeech": "noun",
                    "glosses": ["continued dull pain"],
                    "examples": ["You may feel a minor ache in your side."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "ache#noun#1",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(
            [sense["id"] for sense in senses],
            ["ache#v#1", "ache#n#1"],
        )
        self.assertEqual(
            senses[1]["exampleCandidate"],
            "You may feel a minor ache in your side.",
        )

    def test_review_senses_prefers_untagged_everyday_context_over_abstract_context(self):
        packet = {
            "id": "bank-basic-0576",
            "target": "free",
            "definition": "Unconstrained.",
            "example": "The fundamental group is free of rank two.",
            "partOfSpeech": "adjective",
            "sourceRefs": [],
            "candidateSenses": [
                {
                    "id": "abstract-free",
                    "partOfSpeech": "adjective",
                    "glosses": ["Unconstrained."],
                    "examples": ["The fundamental group is free of rank two."],
                    "tags": ["abstract"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "free#abstract",
                    },
                },
                {
                    "id": "social-free-fragment",
                    "partOfSpeech": "adjective",
                    "glosses": ["Unconstrained."],
                    "examples": ["a free person"],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "free#social-fragment",
                    },
                },
                {
                    "id": "social-free-sentence",
                    "partOfSpeech": "adjective",
                    "glosses": ["Unconstrained."],
                    "examples": ["This is a free country."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "free#social-sentence",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "social-free-fragment")
        self.assertEqual(senses[0]["exampleCandidate"], "This is a free country.")

    def test_review_senses_prefers_the_candidate_closest_to_the_lesson_context(self):
        packet = {
            "id": "bank-basic-0576",
            "target": "free",
            "definition": "Unconstrained.",
            "example": "I thought that the metro was free, so I went without a ticket.",
            "partOfSpeech": "adjective",
            "sourceRefs": [],
            "candidateSenses": [
                {
                    "id": "physical-free",
                    "partOfSpeech": "adjective",
                    "glosses": ["Unconstrained.", "Not attached; loose."],
                    "examples": ["In these mushrooms, the gills are free."],
                    "tags": ["physical"],
                    "reviewDistance": 1.03,
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "free#physical",
                    },
                },
                {
                    "id": "free-of-charge",
                    "partOfSpeech": "adjective",
                    "glosses": ["Obtainable without any payment."],
                    "examples": ["It's free real estate."],
                    "tags": [],
                    "reviewDistance": 0.89,
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "free#no-payment",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "free-of-charge")
        self.assertEqual(senses[0]["meaning"], "Obtainable without any payment.")

    def test_review_senses_keeps_the_lesson_sense_when_sources_are_too_distant(self):
        packet = {
            "id": "bank-basic-0612",
            "target": "forest",
            "definition": "A dense tract of trees and undergrowth.",
            "example": "Because of these trees, he can't see the forest.",
            "partOfSpeech": "noun",
            "sourceRefs": [
                {"sourceID": "vocaby-original", "sourceEntryRef": "bank-basic-0612"}
            ],
            "candidateSenses": [
                {
                    "id": "figurative-forest",
                    "partOfSpeech": "noun",
                    "glosses": ["Any dense collection or amount."],
                    "examples": ["A forest of criticism surrounded the proposal."],
                    "tags": [],
                    "reviewDistance": 1.15,
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "forest#figurative",
                    },
                }
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "bank-basic-0612-sense-1")
        self.assertEqual(senses[0]["meaning"], "A dense tract of trees and undergrowth.")
        self.assertEqual(
            senses[0]["exampleCandidate"],
            "Because of these trees, he can't see the forest.",
        )

    def test_review_senses_uses_a_source_sense_when_new_target_has_no_lesson_definition(self):
        packet = {
            "id": "vocab-new",
            "target": "i'll",
            "cefr": "A2",
            "sourceRefs": [],
            "candidateSenses": [
                {
                    "id": "i-will",
                    "partOfSpeech": "phrase",
                    "glosses": ["I will."],
                    "examples": [],
                    "tags": ["alt-of", "contraction"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "i'll#contraction#1",
                    },
                }
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "i-will")
        self.assertEqual(senses[0]["meaning"], "I will.")

    def test_review_senses_rejects_new_target_with_only_alternative_form_senses(self):
        packet = {
            "id": "vocab-new",
            "target": "told",
            "cefr": "A2",
            "sourceRefs": [],
            "candidateSenses": [
                {
                    "id": "unrelated-acronym",
                    "partOfSpeech": "noun",
                    "glosses": ["Acronym of take-off and landing data."],
                    "examples": [],
                    "tags": ["abbreviation", "acronym", "alt-of"],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "told#noun#1",
                    },
                }
            ],
        }

        self.assertEqual(vocabulary_sources.review_senses(packet), [])

    def test_review_senses_prefers_new_target_sense_with_a_source_example(self):
        packet = {
            "id": "vocab-new",
            "target": "doing",
            "cefr": "A1",
            "sourceRefs": [],
            "candidateSenses": [
                {
                    "id": "sound",
                    "partOfSpeech": "phrase",
                    "glosses": ["A sound made when an elastic object is struck."],
                    "examples": [],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "doing#intj#1",
                    },
                },
                {
                    "id": "action",
                    "partOfSpeech": "noun",
                    "glosses": ["A deed or action."],
                    "examples": ["This is his doing."],
                    "tags": [],
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "doing#noun#1",
                    },
                },
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["id"], "action")
        self.assertEqual(senses[0]["exampleCandidate"], "This is his doing.")

    def test_review_senses_uses_the_specific_final_gloss(self):
        packet = {
            "id": "bank-basic-0181",
            "target": "boy",
            "definition": "a youthful male person",
            "example": "That tall boy saved the drowning child.",
            "exampleTranslationMode": "parallel",
            "partOfSpeech": "noun",
            "sourceRefs": [],
            "candidateSenses": [
                {
                    "id": "male-child",
                    "partOfSpeech": "noun",
                    "glosses": ["A male human.", "A male child."],
                    "examples": ["Kieran plays football with other boys."],
                    "tags": [],
                    "reviewDistance": 0.80,
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "boy#noun",
                    },
                }
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["meaning"], "A male child.")
        self.assertEqual(
            senses[0]["exampleCandidate"],
            "That tall boy saved the drowning child.",
        )

    def test_source_sentence_check_rejects_titles_and_phrases(self):
        self.assertFalse(
            vocabulary_sources.looks_like_source_sentence(
                "aged", "Caring for My Aged Mother XXIII."
            )
        )
        self.assertFalse(
            vocabulary_sources.looks_like_source_sentence(
                "attractive", "A book with attractive illustrations."
            )
        )
        self.assertTrue(
            vocabulary_sources.looks_like_source_sentence(
                "author", "She authored this play."
            )
        )
        self.assertTrue(
            vocabulary_sources.looks_like_source_sentence(
                "menu", "The server handed us the menu."
            )
        )
        self.assertTrue(
            vocabulary_sources.looks_like_source_sentence(
                "bench", "Bench the poodles at the dog show."
            )
        )
        self.assertTrue(
            vocabulary_sources.looks_like_source_sentence(
                "along", "John played the piano and everyone sang along."
            )
        )

    def test_review_senses_does_not_align_examples_by_target_word_alone(self):
        packet = {
            "id": "bench-1",
            "target": "bench",
            "definition": "exhibit on a bench",
            "example": "Bench the poodles at the dog show.",
            "exampleTranslationMode": "usage-note",
            "partOfSpeech": "verb",
            "sourceRefs": [
                {"sourceID": "oewn-2025", "sourceEntryRef": "bench#verb"}
            ],
            "candidateSenses": [
                {
                    "id": "weightlifting",
                    "partOfSpeech": "verb",
                    "glosses": ["To lift by bench pressing."],
                    "examples": ["I heard he can bench 150 pounds."],
                    "tags": [],
                    "reviewDistance": 1.23,
                    "sourceRef": {
                        "sourceID": "wiktextract-en-2026-07-09",
                        "sourceEntryRef": "bench#verb#weightlifting",
                    },
                }
            ],
        }

        senses = vocabulary_sources.review_senses(packet)

        self.assertEqual(senses[0]["meaning"], "exhibit on a bench")
        self.assertEqual(
            senses[0]["exampleCandidate"],
            "Bench the poodles at the dog show.",
        )

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

    def test_wiktextract_snapshot_can_write_deterministic_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_source(root)
            source = root / "all.jsonl.gz"
            with gzip.open(source, "wt", encoding="utf-8") as stream:
                for word in ("charlie", "alpha", "bravo"):
                    stream.write(
                        json.dumps(
                            {
                                "word": word,
                                "lang_code": "en",
                                "pos": "noun",
                                "senses": [{"glosses": [f"Meaning of {word}."]}],
                            }
                        )
                        + "\n"
                    )
            seed = root / "seed.json"
            seed.write_text(
                json.dumps(
                    [
                        {"upgradedExpression": "alpha"},
                        {"upgradedExpression": "bravo"},
                        {"upgradedExpression": "charlie"},
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "targets.jsonl.gz"

            result = vocabulary_sources.snapshot_wiktextract(
                source.as_uri(), seed, output, records_per_shard=2
            )

            self.assertEqual(result["records"], 3)
            self.assertEqual(len(result["shards"]), 2)
            self.assertEqual(
                [Path(item["path"]).name for item in result["shards"]],
                ["targets-0001.jsonl.gz", "targets-0002.jsonl.gz"],
            )
            kept = []
            for item in result["shards"]:
                path = Path(item["path"])
                self.assertEqual(item["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    kept.extend(json.loads(line)["word"] for line in stream)
            self.assertEqual(kept, ["alpha", "bravo", "charlie"])

    def test_wiktextract_adapter_imports_verified_raw_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_dir = root / "Content/Sources/Raw/wiktextract"
            raw_dir.mkdir(parents=True)
            raw_files = []
            for number, word in enumerate(("alpha", "bravo"), 1):
                path = raw_dir / f"targets-{number:04d}.jsonl.gz"
                with gzip.open(path, "wt", encoding="utf-8") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "word": word,
                                "lang_code": "en",
                                "pos": "noun",
                                "senses": [
                                    {
                                        "glosses": [f"Meaning of {word}."],
                                        "examples": [
                                            {"text": f"The word {word} appears here.", "type": "example"}
                                        ],
                                    }
                                ],
                            }
                        )
                        + "\n"
                    )
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
                        "id": "wiktextract-test",
                        "adapter": "wiktextract_jsonl_gz",
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
            output = root / "wiktextract.jsonl"

            result = self.run_cli(
                root,
                "import-source",
                "wiktextract-test",
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                [json.loads(line)["headword"] for line in output.read_text().splitlines()],
                ["alpha", "bravo"],
            )

    def test_import_wiktextract_shards_merges_temporary_discovery_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for number, word in enumerate(("bravo", "alpha"), 1):
                path = root / f"part-{number:04d}.jsonl.gz"
                with gzip.open(path, "wt", encoding="utf-8") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "word": word,
                                "lang_code": "en",
                                "pos": "noun",
                                "senses": [{"glosses": [f"Meaning of {word}."]}],
                            }
                        )
                        + "\n"
                    )
                paths.append(path)
            output = root / "imported.jsonl"

            count = vocabulary_sources.import_wiktextract_shards(
                list(reversed(paths)), "wiktextract-test", output
            )

            self.assertEqual(count, 2)
            self.assertEqual(
                [json.loads(line)["headword"] for line in output.read_text().splitlines()],
                ["alpha", "bravo"],
            )

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
            self.assertEqual([item["senseRank"] for item in records], [0, 1])
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

    def test_prepare_enrichment_prefers_same_part_of_speech_cefr_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()
            lexical = [
                {
                    "sourceID": "oewn",
                    "sourceEntryRef": "book#noun#1",
                    "headword": "book",
                    "partOfSpeech": "noun",
                    "cefr": None,
                    "definitions": ["a written work"],
                    "examples": ["The book is on the table."],
                    "relatedTerms": [],
                    "translations": {},
                    "pronunciations": [],
                    "forms": [],
                    "senseRefs": ["book-noun"],
                    "senses": [],
                },
                {
                    "sourceID": "oewn",
                    "sourceEntryRef": "book#verb#1",
                    "headword": "book",
                    "partOfSpeech": "verb",
                    "cefr": None,
                    "definitions": ["reserve"],
                    "examples": ["Please book a room."],
                    "relatedTerms": [],
                    "translations": {},
                    "pronunciations": [],
                    "forms": [],
                    "senseRefs": ["book-verb"],
                    "senses": [],
                },
            ]
            (input_dir / "oewn.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in lexical),
                encoding="utf-8",
            )
            (input_dir / "cefr.jsonl").write_text(
                json.dumps(
                    {
                        **lexical[0],
                        "sourceID": "cefr",
                        "sourceEntryRef": "book#noun#A1",
                        "cefr": "A1",
                        "definitions": [],
                        "examples": [],
                        "senseRefs": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            existing = root / "existing.json"
            existing.write_text("[]", encoding="utf-8")
            current = root / "current.json"
            current.write_text(
                json.dumps(
                    [
                        {
                            "id": "bank-basic-0001",
                            "level": "basic",
                            "sortOrder": 1,
                            "plainExpression": "written work",
                            "upgradedExpression": "book",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "queue.jsonl"

            vocabulary_sources.prepare_enrichment(
                input_dir,
                existing,
                {"basic": 0, "intermediate": 0, "advanced": 0},
                output,
                current_seed_path=current,
                approved_source_ids={"oewn", "cefr"},
            )

            packet = json.loads(output.read_text())
            self.assertEqual(packet["partOfSpeech"], "n")
            self.assertEqual(packet["definition"], "a written work")

    def test_prepare_enrichment_prefers_cefr_j_part_over_other_cefr_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()
            noun = {
                "sourceID": "oewn",
                "sourceEntryRef": "add#noun#condition",
                "headword": "ADD",
                "partOfSpeech": "noun",
                "cefr": None,
                "definitions": ["an attention-related condition"],
                "examples": [],
                "relatedTerms": [],
                "translations": {},
                "pronunciations": [],
                "forms": [],
                "senseRefs": ["add-noun"],
                "senses": [],
            }
            verb = {
                **noun,
                "sourceEntryRef": "add#verb#increase",
                "headword": "add",
                "partOfSpeech": "verb",
                "definitions": ["put something together with something else"],
                "examples": ["Please add your name to the list."],
                "senseRefs": ["add-verb"],
            }
            (input_dir / "oewn.jsonl").write_text(
                json.dumps(noun) + "\n" + json.dumps(verb) + "\n",
                encoding="utf-8",
            )
            (input_dir / "cefr-j.jsonl").write_text(
                json.dumps(
                    {
                        **verb,
                        "sourceID": "cefr-j",
                        "sourceEntryRef": "add#verb#A1",
                        "cefr": "A1",
                        "definitions": [],
                        "examples": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (input_dir / "grundwortschatz.jsonl").write_text(
                json.dumps(
                    {
                        **noun,
                        "sourceID": "grundwortschatz",
                        "sourceEntryRef": "add#noun#A1",
                        "cefr": "A1",
                        "definitions": [
                            "an attention-related condition",
                            "put something together with something else",
                        ],
                        "examples": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            existing = root / "existing.json"
            existing.write_text("[]", encoding="utf-8")
            current = root / "current.json"
            current.write_text(
                json.dumps(
                    [
                        {
                            "id": "bank-basic-0001",
                            "level": "basic",
                            "sortOrder": 1,
                            "plainExpression": "put together",
                            "upgradedExpression": "add",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "queue.jsonl"

            vocabulary_sources.prepare_enrichment(
                input_dir,
                existing,
                {"basic": 0, "intermediate": 0, "advanced": 0},
                output,
                current_seed_path=current,
                approved_source_ids={"oewn", "cefr-j", "grundwortschatz"},
            )

            packet = json.loads(output.read_text())
            self.assertEqual(packet["partOfSpeech"], "v")
            self.assertEqual(
                packet["definition"], "put something together with something else"
            )

    def test_prepare_enrichment_prefers_translation_aligned_parallel_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()

            def record(source_id, reference, headword, **values):
                return {
                    "sourceID": source_id,
                    "sourceEntryRef": reference,
                    "headword": headword,
                    "partOfSpeech": values.get("partOfSpeech"),
                    "cefr": values.get("cefr"),
                    "definitions": values.get("definitions", []),
                    "examples": values.get("examples", []),
                    "relatedTerms": values.get("relatedTerms", []),
                    "translations": values.get("translations", {}),
                    "pronunciations": [],
                    "forms": [],
                    "senseRefs": values.get("senseRefs", []),
                    "iliRefs": values.get("iliRefs", []),
                    "senses": [],
                    **(
                        {"senseRank": values["senseRank"]}
                        if "senseRank" in values
                        else {}
                    ),
                }

            sources = [
                record(
                    "oewn",
                    "address#n#computer",
                    "address",
                    partOfSpeech="noun",
                    definitions=["a computer code that identifies stored data"],
                    iliRefs=["i-computer"],
                    senseRefs=["computer"],
                    senseRank=0,
                ),
                record(
                    "oewn",
                    "address#n#postal",
                    "address",
                    partOfSpeech="noun",
                    definitions=["the place where a person can be contacted"],
                    iliRefs=["i-postal"],
                    senseRefs=["postal"],
                    senseRank=1,
                ),
                record(
                    "cefr-j",
                    "address#noun#A1",
                    "address",
                    partOfSpeech="noun",
                    cefr="A1",
                ),
                record(
                    "omw-ili-map",
                    "postal-map",
                    "postal-map",
                    senseRefs=["pwn-postal"],
                    iliRefs=["i-postal"],
                ),
                record(
                    "omw-ili-map",
                    "computer-map",
                    "computer-map",
                    senseRefs=["pwn-computer"],
                    iliRefs=["i-computer"],
                ),
                record(
                    "cow-0.9",
                    "pwn-postal:地址",
                    "地址",
                    senseRefs=["pwn-postal"],
                ),
                record(
                    "cow-0.9",
                    "pwn-computer:尋址",
                    "尋址",
                    senseRefs=["pwn-computer"],
                ),
                record(
                    "cc-cedict",
                    "address:地址",
                    "address",
                    definitions=["address", "location"],
                    translations={"zh-Hant": ["地址"]},
                ),
                record(
                    "cc-cedict",
                    "address:尋址",
                    "address",
                    definitions=["address", "locate data in memory"],
                    translations={"zh-Hant": ["尋址"]},
                ),
                record(
                    "tatoeba",
                    "sentence-1",
                    "What is your address?",
                    examples=["What is your address?"],
                    translations={"zh-Hant": ["你的地址是什麼？"]},
                ),
                record(
                    "tatoeba",
                    "sentence-2",
                    "address",
                    examples=["Please write down your address."],
                    translations={"zh-Hant": ["請寫下你的地址。"]},
                ),
                record(
                    "tatoeba",
                    "sentence-3",
                    "address",
                    examples=["The computer address identifies the stored data."],
                    translations={"zh-Hant": ["軟體使用記憶體尋址。"]},
                ),
            ]
            for index, item in enumerate(sources):
                (input_dir / f"source-{index}.jsonl").write_text(
                    json.dumps(item, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            existing = root / "existing.json"
            existing.write_text("[]", encoding="utf-8")
            current = root / "current.json"
            current.write_text(
                json.dumps(
                    [
                        {
                            "id": "bank-basic-0001",
                            "level": "basic",
                            "sortOrder": 1,
                            "plainExpression": "contact location",
                            "upgradedExpression": "address",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "queue.jsonl"

            vocabulary_sources.prepare_enrichment(
                input_dir,
                existing,
                {"basic": 0, "intermediate": 0, "advanced": 0},
                output,
                current_seed_path=current,
                approved_source_ids={item["sourceID"] for item in sources},
            )

            packet = json.loads(output.read_text())
            self.assertEqual(
                packet["definition"], "the place where a person can be contacted"
            )
            self.assertEqual(packet["example"], "What is your address?")
            self.assertEqual(packet["exampleTranslationDraft"], "你的地址是什麼？")

    def test_prepare_enrichment_prefers_common_oewn_sense_when_translation_is_same(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()

            def record(source_id, reference, headword, **values):
                return {
                    "sourceID": source_id,
                    "sourceEntryRef": reference,
                    "headword": headword,
                    "partOfSpeech": values.get("partOfSpeech"),
                    "cefr": values.get("cefr"),
                    "definitions": values.get("definitions", []),
                    "examples": values.get("examples", []),
                    "relatedTerms": values.get("relatedTerms", []),
                    "translations": values.get("translations", {}),
                    "pronunciations": [],
                    "forms": [],
                    "senseRefs": values.get("senseRefs", []),
                    "iliRefs": values.get("iliRefs", []),
                    "senses": [],
                    **(
                        {"senseRank": values["senseRank"]}
                        if "senseRank" in values
                        else {}
                    ),
                }

            sources = [
                record(
                    "oewn",
                    "back#n#body",
                    "back",
                    partOfSpeech="noun",
                    definitions=[
                        "(of people and animals) the rear part of the body from the neck to the waist"
                    ],
                    examples=["His back hurt after the long flight."],
                    senseRefs=["body"],
                    senseRank=0,
                ),
                record(
                    "oewn",
                    "back#n#garment",
                    "back",
                    partOfSpeech="noun",
                    definitions=["the part of a garment that covers the back of the body"],
                    examples=["They pinned a sign on the back of his shirt."],
                    senseRefs=["garment"],
                    iliRefs=["i-garment"],
                    senseRank=6,
                ),
                record(
                    "oewn",
                    "back#v#backward",
                    "back",
                    partOfSpeech="verb",
                    definitions=["travel backward"],
                    examples=["Please move back."],
                    senseRefs=["backward"],
                    iliRefs=["i-backward"],
                    senseRank=0,
                ),
                record(
                    "cefr-j",
                    "back#noun#A1",
                    "back",
                    partOfSpeech="noun",
                    cefr="A1",
                ),
                record(
                    "cefr-j",
                    "back#verb#A1",
                    "back",
                    partOfSpeech="verb",
                    cefr="A1",
                ),
                record(
                    "omw-ili-map",
                    "garment-map",
                    "garment-map",
                    senseRefs=["pwn-garment"],
                    iliRefs=["i-garment"],
                ),
                record(
                    "omw-ili-map",
                    "backward-map",
                    "backward-map",
                    senseRefs=["pwn-backward"],
                    iliRefs=["i-backward"],
                ),
                record(
                    "cow-0.9",
                    "pwn-garment:背",
                    "背",
                    senseRefs=["pwn-garment"],
                ),
                record(
                    "cow-0.9",
                    "pwn-backward:後退",
                    "後退",
                    senseRefs=["pwn-backward"],
                ),
                record(
                    "cc-cedict",
                    "back:背",
                    "back",
                    definitions=["back", "rear part of the body"],
                    translations={"zh-Hant": ["背"]},
                ),
                record(
                    "tatoeba",
                    "sentence-1",
                    "My back itches.",
                    examples=["My back itches."],
                    translations={"zh-Hant": ["我的背很癢。"]},
                ),
                record(
                    "tatoeba",
                    "sentence-2",
                    "Please move back.",
                    examples=["Please move back."],
                    translations={"zh-Hant": ["請往後退。"]},
                ),
            ]
            for index, item in enumerate(sources):
                (input_dir / f"source-{index}.jsonl").write_text(
                    json.dumps(item, ensure_ascii=False) + "\n", encoding="utf-8"
                )
            existing = root / "existing.json"
            existing.write_text("[]", encoding="utf-8")
            current = root / "current.json"
            current.write_text(
                json.dumps(
                    [
                        {
                            "id": "bank-basic-0001",
                            "level": "basic",
                            "sortOrder": 1,
                            "plainExpression": "rear body part",
                            "upgradedExpression": "back",
                            "senses": [{"partOfSpeech": "noun"}],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "queue.jsonl"

            vocabulary_sources.prepare_enrichment(
                input_dir,
                existing,
                {"basic": 0, "intermediate": 0, "advanced": 0},
                output,
                current_seed_path=current,
                approved_source_ids={item["sourceID"] for item in sources},
            )

            packet = json.loads(output.read_text())
            self.assertEqual(
                packet["definition"],
                "(of people and animals) the rear part of the body from the neck to the waist",
            )

    def test_prepare_enrichment_prefers_sense_matching_cefr_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()
            lexical = [
                {
                    "sourceID": "grundwortschatz",
                    "sourceEntryRef": "bench#noun#rare",
                    "headword": "bench",
                    "partOfSpeech": "noun",
                    "cefr": None,
                    "definitions": ["a lifted weight used by people at a gym"],
                    "examples": ["His bench increased after a month of training."],
                    "relatedTerms": [],
                    "translations": {},
                    "pronunciations": [],
                    "forms": [],
                    "senseRefs": ["bench-rare"],
                    "senses": [],
                },
                {
                    "sourceID": "grundwortschatz",
                    "sourceEntryRef": "bench#noun#common",
                    "headword": "bench",
                    "partOfSpeech": "noun",
                    "cefr": None,
                    "definitions": ["a long seat for several people"],
                    "examples": ["We sat together on a park bench."],
                    "relatedTerms": [],
                    "translations": {},
                    "pronunciations": [],
                    "forms": [],
                    "senseRefs": ["bench-common"],
                    "senses": [],
                },
            ]
            (input_dir / "grundwortschatz.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in lexical),
                encoding="utf-8",
            )
            (input_dir / "cefr.jsonl").write_text(
                json.dumps(
                    {
                        **lexical[1],
                        "sourceID": "cefr",
                        "sourceEntryRef": "bench#noun#A2",
                        "cefr": "A2",
                        "definitions": [
                            "a long seat for several people",
                            (
                                "a lifted weight used by people at a gym; people lift "
                                "the weight while seated at a bench"
                            ),
                        ],
                        "examples": [],
                        "senseRefs": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            existing = root / "existing.json"
            existing.write_text("[]", encoding="utf-8")
            current = root / "current.json"
            current.write_text(
                json.dumps(
                    [
                        {
                            "id": "bank-basic-0001",
                            "level": "basic",
                            "sortOrder": 1,
                            "plainExpression": "long seat",
                            "upgradedExpression": "bench",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "queue.jsonl"

            vocabulary_sources.prepare_enrichment(
                input_dir,
                existing,
                {"basic": 0, "intermediate": 0, "advanced": 0},
                output,
                current_seed_path=current,
                approved_source_ids={"grundwortschatz", "cefr"},
            )

            packet = json.loads(output.read_text())
            self.assertEqual(packet["definition"], "a long seat for several people")
            self.assertEqual(packet["example"], "We sat together on a park bench.")

    def test_prepare_enrichment_prefers_first_oewn_sense_without_source_example(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "imported"
            input_dir.mkdir()
            common = {
                "sourceID": "oewn",
                "sourceEntryRef": "actor#noun#common",
                "headword": "actor",
                "partOfSpeech": "noun",
                "cefr": None,
                "definitions": ["a person who performs in a play or film"],
                "examples": [],
                "relatedTerms": ["performer"],
                "translations": {},
                "pronunciations": [],
                "forms": [],
                "senseRefs": ["actor-common"],
                "senses": [],
            }
            uncommon = {
                **common,
                "sourceEntryRef": "actor#noun#uncommon",
                "definitions": ["a doer"],
                "examples": ["He was the main actor in the dispute."],
                "relatedTerms": ["doer"],
                "senseRefs": ["actor-uncommon"],
            }
            (input_dir / "oewn.jsonl").write_text(
                json.dumps(common) + "\n" + json.dumps(uncommon) + "\n",
                encoding="utf-8",
            )
            (input_dir / "cefr.jsonl").write_text(
                json.dumps(
                    {
                        **common,
                        "sourceID": "cefr",
                        "sourceEntryRef": "actor#noun#A1",
                        "cefr": "A1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            existing = root / "existing.json"
            existing.write_text("[]", encoding="utf-8")
            current = root / "current.json"
            current.write_text(
                json.dumps(
                    [
                        {
                            "id": "bank-basic-0001",
                            "level": "basic",
                            "sortOrder": 1,
                            "plainExpression": "performer",
                            "upgradedExpression": "actor",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "queue.jsonl"

            vocabulary_sources.prepare_enrichment(
                input_dir,
                existing,
                {"basic": 0, "intermediate": 0, "advanced": 0},
                output,
                current_seed_path=current,
                approved_source_ids={"oewn", "cefr"},
            )

            packet = json.loads(output.read_text())
            self.assertEqual(
                packet["definition"], "a person who performs in a play or film"
            )
            self.assertEqual(packet["example"], "")

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

    def test_prepare_enrichment_requires_context_for_unaligned_parallel_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            tatoeba_path = input_dir / "tatoeba.jsonl"
            tatoeba = json.loads(tatoeba_path.read_text())
            tatoeba["headword"] = "That was excellent."
            tatoeba["examples"] = ["That was excellent."]
            tatoeba["translations"] = {"zh-Hant": ["那真優秀。"]}
            tatoeba_path.write_text(
                json.dumps(tatoeba, ensure_ascii=False) + "\n", encoding="utf-8"
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
            packet = json.loads(output.read_text())
            self.assertEqual(packet["example"], "She shared an excellent idea.")
            self.assertIsNone(packet["exampleTranslationDraft"])

    def test_prepare_enrichment_keeps_english_candidate_when_translation_is_unmatched(self):
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

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads((root / "draft.jsonl").read_text())["translationDraft"],
                "",
            )

    def test_prepare_enrichment_ignores_uncorroborated_freedict_translation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            freedict_path = input_dir / "freedict.jsonl"
            freedict = json.loads(freedict_path.read_text())
            freedict["sourceID"] = "freedict-eng-zho-2025.11.23"
            freedict_path.write_text(
                json.dumps(freedict, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            cedict = {
                **freedict,
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
            self.assertEqual(packet["translationDraft"], "")
            self.assertNotIn(
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

    def test_prepare_enrichment_ignores_freedict_part_of_speech_mismatch(self):
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

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads((root / "draft.jsonl").read_text())["translationDraft"],
                "",
            )

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
                "sourceID": "cc-cedict-2026-07-11",
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

    def test_prepare_enrichment_omits_a_source_example_without_the_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            lexical_path = input_dir / "oewn-2025.jsonl"
            lexical = json.loads(lexical_path.read_text())
            lexical["examples"] = ["She shared a superb idea."]
            lexical_path.write_text(json.dumps(lexical) + "\n", encoding="utf-8")
            (input_dir / "tatoeba.jsonl").unlink()

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
            self.assertEqual(json.loads(output.read_text())["example"], "")

    def test_prepare_enrichment_omits_a_fragmentary_source_example(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir, existing_seed = self.make_enrichment_sources(root)
            lexical_path = input_dir / "oewn-2025.jsonl"
            lexical = json.loads(lexical_path.read_text())
            lexical["examples"] = ["Excellent service"]
            lexical_path.write_text(json.dumps(lexical) + "\n", encoding="utf-8")
            (input_dir / "tatoeba.jsonl").unlink()
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
            self.assertEqual(json.loads(output.read_text())["example"], "")

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
