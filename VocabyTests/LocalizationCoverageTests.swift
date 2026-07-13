import Foundation
import XCTest

final class LocalizationCoverageTests: XCTestCase {
    func testAllStringsHaveEnglishAndTraditionalChineseTranslations() throws {
        let catalog = try loadCatalog()

        XCTAssertEqual(catalog.sourceLanguage, "en")

        for (key, value) in catalog.strings {
            let english = value.localizations["en"]?.stringUnit.value.trimmingCharacters(in: .whitespacesAndNewlines)
            let traditionalChinese = value.localizations["zh-Hant"]?.stringUnit.value.trimmingCharacters(in: .whitespacesAndNewlines)

            XCTAssertFalse(english?.isEmpty ?? true, "\(key) is missing an English translation")
            XCTAssertFalse(traditionalChinese?.isEmpty ?? true, "\(key) is missing a zh-Hant translation")
        }
    }

    func testHighRiskStringsStayWithinLayoutBudgets() throws {
        let catalog = try loadCatalog()
        let budgets: [String: StringBudget] = [
            "today.tab.title": .init(en: 8, zhHant: 4),
            "review.tab.title": .init(en: 8, zhHant: 4),
            "library.tab.title": .init(en: 8, zhHant: 4),
            "widget.configuration.name": .init(en: 16, zhHant: 16),
            "widget.configuration.description": .init(en: 48, zhHant: 24),
            "widget.title": .init(en: 16, zhHant: 16),
            "widget.today": .init(en: 24, zhHant: 8),
            "widget.empty": .init(en: 28, zhHant: 10),
            "widget.completed": .init(en: 20, zhHant: 8),
            "notifications.daily.title": .init(en: 44, zhHant: 20),
            "notifications.daily.body": .init(en: 56, zhHant: 24),
            "onboarding.continue": .init(en: 24, zhHant: 12),
            "onboarding.level.continue": .init(en: 24, zhHant: 12),
            "onboarding.reminder.enable": .init(en: 24, zhHant: 12),
            "onboarding.reminder.skip": .init(en: 24, zhHant: 12),
            "today.start.button": .init(en: 24, zhHant: 12),
            "today.resume.button": .init(en: 24, zhHant: 12),
            "today.completed.button": .init(en: 24, zhHant: 12),
            "today.extraPractice.button": .init(en: 24, zhHant: 12),
            "today.vocabularyProgress.title": .init(en: 24, zhHant: 12),
            "today.vocabularyProgress.total": .init(en: 24, zhHant: 12),
            "review.start.button": .init(en: 24, zhHant: 12),
            "library.detail.definition": .init(en: 20, zhHant: 8),
            "practice.learn.startQuiz": .init(en: 24, zhHant: 12),
            "practice.next": .init(en: 24, zhHant: 12),
            "practice.submit": .init(en: 24, zhHant: 12),
            "practice.retry.button": .init(en: 24, zhHant: 12),
            "practice.center.button": .init(en: 24, zhHant: 12),
            "practice.center.title": .init(en: 24, zhHant: 12),
            "practice.center.mode.label": .init(en: 24, zhHant: 12),
            "practice.center.questions.label": .init(en: 24, zhHant: 12),
            "practice.center.timer.label": .init(en: 24, zhHant: 12),
            "practice.center.retry.toggle": .init(en: 24, zhHant: 12),
            "practice.center.mode.mixed": .init(en: 16, zhHant: 8),
            "practice.center.mode.expression": .init(en: 24, zhHant: 12),
            "practice.center.mode.meaning": .init(en: 24, zhHant: 12),
            "practice.center.mode.listening": .init(en: 24, zhHant: 12),
            "practice.center.mode.spelling": .init(en: 16, zhHant: 8),
            "practice.center.start": .init(en: 24, zhHant: 12),
            "practice.center.newRun": .init(en: 24, zhHant: 12),
            "settings.reminders.openSettings": .init(en: 24, zhHant: 12),
            "settings.language.label": .init(en: 24, zhHant: 12),
            "settings.language.openSettingsHint": .init(en: 44, zhHant: 20),
            "settings.sources.row": .init(en: 24, zhHant: 12),
            "settings.sources.title": .init(en: 24, zhHant: 12),
            "settings.sources.unavailable": .init(en: 48, zhHant: 24),
            "settings.level.label": .init(en: 24, zhHant: 12),
            "settings.reminders.toggle": .init(en: 24, zhHant: 12),
            "settings.reminders.time": .init(en: 24, zhHant: 12)
        ]

        for (key, budget) in budgets {
            let value = try XCTUnwrap(catalog.strings[key], "\(key) must stay covered by localization budget tests")
            let english = try XCTUnwrap(value.localizations["en"]?.stringUnit.value)
            let traditionalChinese = try XCTUnwrap(value.localizations["zh-Hant"]?.stringUnit.value)

            XCTAssertLessThanOrEqual(english.count, budget.en, "\(key) English text is too long for compact UI")
            XCTAssertLessThanOrEqual(traditionalChinese.count, budget.zhHant, "\(key) zh-Hant text is too long for compact UI")
        }
    }

    func testRichVocabularyStringsHaveEnglishAndTraditionalChineseTranslations() throws {
        let catalog = try loadCatalog()
        let keys = [
            "vocabulary.pronunciation",
            "vocabulary.meaning.english",
            "vocabulary.meaning.support",
            "vocabulary.example",
            "vocabulary.additionalSenses",
            "vocabulary.region.general",
            "vocabulary.pos.noun",
            "vocabulary.pos.verb",
            "vocabulary.pos.adjective",
            "vocabulary.pos.adverb",
            "vocabulary.pos.preposition",
            "vocabulary.pos.conjunction",
            "vocabulary.pos.interjection",
            "vocabulary.pos.pronoun",
            "vocabulary.pos.determiner",
            "vocabulary.pos.phrase"
        ]

        for key in keys {
            let value = try XCTUnwrap(catalog.strings[key], "\(key) is missing")
            XCTAssertFalse(value.localizations["en"]?.stringUnit.value.isEmpty ?? true)
            XCTAssertFalse(value.localizations["zh-Hant"]?.stringUnit.value.isEmpty ?? true)
        }
    }

    func testLearningChromeStringsHaveEnglishAndTraditionalChineseTranslations() throws {
        let catalog = try loadCatalog()
        let keys = [
            "learning.profile.accessibility",
            "today.compactSummary.format",
            "today.review.estimatedTime.format",
            "today.libraryProgress.row",
            "review.estimatedTime.format",
            "review.nextUp.title",
            "library.compactProgress.format"
        ]

        for key in keys {
            let value = try XCTUnwrap(catalog.strings[key], "\(key) is missing")
            XCTAssertFalse(value.localizations["en"]?.stringUnit.value.isEmpty ?? true)
            XCTAssertFalse(value.localizations["zh-Hant"]?.stringUnit.value.isEmpty ?? true)
        }
    }

    func testSpellingInstructionsExplainTheExpectedLanguageAndOfferAnAudioHint() throws {
        let catalog = try loadCatalog()
        let prompt = try XCTUnwrap(catalog.strings["practice.mode.spelling.prompt"])
        let audioHint = try XCTUnwrap(catalog.strings["practice.spelling.audioHint"])

        XCTAssertEqual(
            prompt.localizations["zh-Hant"]?.stringUnit.value,
            "依照中文意思，輸入英文表達"
        )
        XCTAssertEqual(
            audioHint.localizations["zh-Hant"]?.stringUnit.value,
            "聽發音提示"
        )
    }

    func testQuizInstructionsDescribeEachActionWithoutInternalTerminology() throws {
        let catalog = try loadCatalog()
        let expectedTraditionalChinese = [
            "practice.mode.expression.prompt": "選出更自然的英文說法",
            "practice.mode.meaning.prompt": "選出這句英文的中文意思",
            "practice.mode.listening.prompt": "聽英文發音，選出對應表達",
            "practice.mode.spelling.prompt": "依照中文意思，輸入英文表達",
            "practice.center.mode.expression": "選更自然的說法",
            "practice.center.mode.meaning": "選中文意思",
            "practice.center.mode.listening": "聽發音選答案",
            "practice.center.mode.spelling": "拼寫英文",
            "practice.center.mode.mixed": "混合題型"
        ]

        for (key, expected) in expectedTraditionalChinese {
            XCTAssertEqual(catalog.strings[key]?.localizations["zh-Hant"]?.stringUnit.value, expected, key)
        }
    }

    private func loadCatalog() throws -> StringCatalog {
        let testFile = URL(fileURLWithPath: #filePath)
        let projectRoot = testFile
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let catalogURL = projectRoot
            .appendingPathComponent("Vocaby")
            .appendingPathComponent("Resources")
            .appendingPathComponent("Localizable.xcstrings")
        let data = try Data(contentsOf: catalogURL)
        return try JSONDecoder().decode(StringCatalog.self, from: data)
    }
}

private struct StringBudget {
    let en: Int
    let zhHant: Int
}

private struct StringCatalog: Decodable {
    let sourceLanguage: String
    let strings: [String: StringCatalogEntry]
}

private struct StringCatalogEntry: Decodable {
    let localizations: [String: StringLocalization]
}

private struct StringLocalization: Decodable {
    let stringUnit: StringUnit
}

private struct StringUnit: Decodable {
    let value: String
}
