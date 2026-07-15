from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LearningUIContractTests(unittest.TestCase):
    def source(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_content_screens_do_not_use_report_style_labeled_content(self):
        for relative in (
            "Vocaby/Features/Today/TodayView.swift",
            "Vocaby/Features/Review/ReviewView.swift",
            "Vocaby/Features/Library/LibraryView.swift",
            "Vocaby/Features/Practice/PracticeView.swift",
            "Vocaby/Features/Shared/VocabularyEntryContentView.swift",
        ):
            with self.subTest(relative=relative):
                self.assertNotIn("LabeledContent(", self.source(relative))

    def test_settings_entry_uses_settings_semantics(self):
        source = self.source("Vocaby/Features/Shared/LearningChrome.swift")
        self.assertIn('Image(systemName: "gearshape")', source)
        self.assertNotIn("person.crop.circle", source)

    def test_spelling_uses_ascii_capable_keyboard(self):
        source = self.source("Vocaby/Features/Practice/PracticeView.swift")
        self.assertIn(".keyboardType(.asciiCapable)", source)
        self.assertNotIn("if question.mode != .spelling", source)
        self.assertNotIn(
            'if question.mode == .spelling {\n                Button {',
            source,
        )

    def test_quiz_feedback_does_not_embed_full_dictionary(self):
        source = self.source("Vocaby/Features/Practice/PracticeView.swift")
        feedback = source[source.index("if let feedback = runState.currentFeedback"):]
        feedback = feedback[:feedback.index("private var resultContent")]
        self.assertNotIn("VocabularyEntryContentView(", feedback)

    def test_feedback_collapses_irrelevant_answer_rows(self):
        source = self.source("Vocaby/Features/Practice/PracticeView.swift")
        self.assertIn("ForEach(visibleOptions(for: question)", source)
        self.assertIn("private func visibleOptions(for question: QuizQuestion)", source)

    def test_audio_controls_use_the_shared_minimum_interactive_size(self):
        chrome = self.source("Vocaby/Features/Shared/LearningChrome.swift")
        self.assertIn("func minimumInteractiveSize()", chrome)
        self.assertIn("frame(minWidth: 44, minHeight: 44)", chrome)
        self.assertIn(".contentShape(Rectangle())", chrome)

        for relative in (
            "Vocaby/Features/Practice/PracticeView.swift",
            "Vocaby/Features/Shared/VocabularyEntryContentView.swift",
        ):
            with self.subTest(relative=relative):
                self.assertIn(".minimumInteractiveSize()", self.source(relative))

    def test_accessibility_type_moves_next_action_into_the_list(self):
        source = self.source("Vocaby/Features/Practice/PracticeView.swift")
        self.assertIn("@Environment(\\.dynamicTypeSize)", source)
        self.assertIn("dynamicTypeSize.isAccessibilitySize", source)
        self.assertIn("private var nextButton", source)


if __name__ == "__main__":
    unittest.main()
