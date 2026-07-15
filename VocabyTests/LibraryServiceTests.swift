import XCTest
@testable import Vocaby

final class LibraryServiceTests: XCTestCase {
    func testLearnedItemsRequireQuizResultAndRespectSearch() {
        let seedItems = [
            item("basic-001", sortOrder: 1, plainExpression: "very good", upgradedExpression: "excellent"),
            item("basic-002", sortOrder: 2, plainExpression: "very tired", upgradedExpression: "exhausted"),
            item("basic-003", sortOrder: 3, plainExpression: "help me", upgradedExpression: "give me a hand")
        ]
        let progressRows = [
            WordProgress(itemID: "basic-001", level: .basic),
            WordProgress(itemID: "basic-002", level: .basic),
            WordProgress(itemID: "basic-003", level: .basic)
        ]
        let quizResults = [
            QuizResult(dayKey: "2026-07-10", itemID: "basic-001", selectedOptionIndex: 0, correctOptionIndex: 0),
            QuizResult(dayKey: "2026-07-10", itemID: "basic-003", selectedOptionIndex: 1, correctOptionIndex: 0)
        ]

        let rows = LibraryService().items(
            from: seedItems,
            progressRows: progressRows,
            quizResults: quizResults,
            scope: .learned,
            query: "hand",
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(rows.map(\.id), ["basic-003"])
    }

    func testSavedItemsComeFromSavedProgressAndFollowSeedOrder() {
        let seedItems = [
            item("basic-002", sortOrder: 2),
            item("basic-001", sortOrder: 1),
            item("basic-ja-001", sortOrder: 3, supportLanguageCodes: ["ja"])
        ]
        let progressRows = [
            WordProgress(itemID: "basic-002", level: .basic, isSaved: true),
            WordProgress(itemID: "basic-001", level: .basic, isSaved: true),
            WordProgress(itemID: "basic-ja-001", level: .basic, isSaved: true)
        ]

        let rows = LibraryService().items(
            from: seedItems,
            progressRows: progressRows,
            quizResults: [],
            scope: .saved,
            query: "",
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(rows.map(\.id), ["basic-001", "basic-002"])
    }

    func testLevelSummariesCountEligibleTotalsAndDistinctLearnedItems() {
        let seedItems = [
            item("basic-001", level: .basic, sortOrder: 1),
            item("basic-002", level: .basic, sortOrder: 2),
            item("intermediate-001", level: .intermediate, sortOrder: 1),
            item("advanced-001", level: .advanced, sortOrder: 1),
            item("advanced-ja-001", level: .advanced, sortOrder: 2, supportLanguageCodes: ["ja"]),
            item("advanced-fr-001", level: .advanced, sortOrder: 3, contentLanguageCode: "fr")
        ]
        let quizResults = [
            QuizResult(dayKey: "2026-07-10", itemID: "basic-001", selectedOptionIndex: 0, correctOptionIndex: 0),
            QuizResult(dayKey: "2026-07-11", itemID: "basic-001", selectedOptionIndex: 1, correctOptionIndex: 0),
            QuizResult(dayKey: "2026-07-10", itemID: "advanced-001", selectedOptionIndex: 0, correctOptionIndex: 0),
            QuizResult(dayKey: "2026-07-10", itemID: "removed-001", selectedOptionIndex: 0, correctOptionIndex: 0),
            QuizResult(dayKey: "2026-07-10", itemID: "advanced-ja-001", selectedOptionIndex: 0, correctOptionIndex: 0)
        ]

        let summaries = LibraryService().levelSummaries(
            from: seedItems,
            quizResults: quizResults,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(summaries, [
            .init(level: .basic, learnedCount: 1, totalCount: 2),
            .init(level: .intermediate, learnedCount: 0, totalCount: 1),
            .init(level: .advanced, learnedCount: 1, totalCount: 1)
        ])
    }

    func testLevelSummariesIncludeZeroTotalLevelsWithZeroProgress() {
        let summaries = LibraryService().levelSummaries(
            from: [item("basic-001", level: .basic, sortOrder: 1)],
            quizResults: [],
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(summaries.map(\.level), [.basic, .intermediate, .advanced])
        XCTAssertEqual(summaries[0].progress, 0)
        XCTAssertEqual(summaries[1], .init(level: .intermediate, learnedCount: 0, totalCount: 0))
        XCTAssertEqual(summaries[1].progress, 0)
        XCTAssertEqual(summaries[2].progress, 0)
    }

    func testSavedOnlyItemDoesNotCountAsLearned() {
        let seedItems = [item("basic-001", level: .basic, sortOrder: 1)]
        let savedProgress = [WordProgress(itemID: "basic-001", level: .basic, isSaved: true)]
        let service = LibraryService()

        let savedRows = service.items(
            from: seedItems,
            progressRows: savedProgress,
            quizResults: [],
            scope: .saved,
            query: "",
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant"
        )
        let summaries = service.levelSummaries(
            from: seedItems,
            quizResults: [],
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(savedRows.map(\.id), ["basic-001"])
        XCTAssertEqual(summaries[0], .init(level: .basic, learnedCount: 0, totalCount: 1))
    }

    private func item(
        _ id: String,
        level: VocabularyLevel = .basic,
        sortOrder: Int,
        plainExpression: String = "plain",
        upgradedExpression: String = "upgraded",
        contentLanguageCode: String = "en",
        supportLanguageCodes: [String] = ["zh-Hant"]
    ) -> VocabularySeedItem {
        let pronunciationID = "\(id)-pronunciation-1"
        let senseID = "\(id)-sense-1"
        return VocabularySeedItem(
            id: id,
            level: level,
            sortOrder: sortOrder,
            contentLanguageCode: contentLanguageCode,
            supportLanguageCodes: supportLanguageCodes,
            plainExpression: plainExpression,
            upgradedExpression: upgradedExpression,
            primarySenseID: senseID,
            pronunciations: [.init(id: pronunciationID, ipa: "tɛst", speechLocale: "en-US", region: "US")],
            senses: [.init(
                id: senseID,
                partOfSpeech: upgradedExpression.contains(" ") ? .phrase : .noun,
                meaning: ["en": "meaning", "zh-Hant": "meaning"],
                example: .init(text: "Example.", translation: ["zh-Hant": "例句。"]),
                pronunciationIDs: [pronunciationID]
            )],
            quiz: VocabularyQuiz(prompt: ["en": "prompt", "zh-Hant": "prompt"], options: ["A", "B"], correctOptionIndex: 0)
        )
    }
}
