import json
import tempfile
import unittest
from pathlib import Path

from tools import review_vocabulary


class ReviewVocabularyTests(unittest.TestCase):
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
            batch = json.loads((work / "enrichment-input.jsonl").read_text())
            self.assertEqual(batch["items"][0]["id"], "bank-basic-0001::bank-basic-0001-sense-1")


if __name__ == "__main__":
    unittest.main()
