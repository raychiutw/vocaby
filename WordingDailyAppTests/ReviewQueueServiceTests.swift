import XCTest
@testable import WordingDailyApp

final class ReviewQueueServiceTests: XCTestCase {
    func testQueuedItemsFollowDueProgressOrderAndRespectLanguage() {
        let seedItems = [
            item("basic-001", sortOrder: 1),
            item("basic-003", sortOrder: 3),
            item("basic-ja-001", sortOrder: 4, supportLanguageCodes: ["ja"]),
            item("spanish-001", sortOrder: 5, contentLanguageCode: "es")
        ]
        let dueProgressRows = [
            WordProgress(itemID: "basic-003", level: .basic),
            WordProgress(itemID: "basic-ja-001", level: .basic),
            WordProgress(itemID: "missing-001", level: .basic),
            WordProgress(itemID: "spanish-001", level: .basic),
            WordProgress(itemID: "basic-001", level: .basic)
        ]

        let queuedItems = ReviewQueueService().queuedItems(
            from: seedItems,
            dueProgressRows: dueProgressRows,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(queuedItems.map(\.id), ["basic-003", "basic-001"])
    }

    private func item(
        _ id: String,
        sortOrder: Int,
        contentLanguageCode: String = "en",
        supportLanguageCodes: [String] = ["zh-Hant"]
    ) -> VocabularySeedItem {
        VocabularySeedItem(
            id: id,
            level: .basic,
            sortOrder: sortOrder,
            contentLanguageCode: contentLanguageCode,
            supportLanguageCodes: supportLanguageCodes,
            plainExpression: "plain \(id)",
            upgradedExpression: "upgraded \(id)",
            meaning: ["zh-Hant": "meaning"],
            example: VocabularyExample(text: "Example.", translation: ["zh-Hant": "例句。"]),
            pronunciationText: id,
            quiz: VocabularyQuiz(prompt: ["zh-Hant": "prompt"], options: ["A", "B"], correctOptionIndex: 0)
        )
    }
}
