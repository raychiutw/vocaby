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

    private func item(
        _ id: String,
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
            level: .basic,
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
