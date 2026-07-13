import XCTest
@testable import Vocaby

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
        let pronunciationID = "\(id)-pronunciation-1"
        let senseID = "\(id)-sense-1"
        return VocabularySeedItem(
            id: id,
            level: .basic,
            sortOrder: sortOrder,
            contentLanguageCode: contentLanguageCode,
            supportLanguageCodes: supportLanguageCodes,
            plainExpression: "plain \(id)",
            upgradedExpression: "upgraded \(id)",
            primarySenseID: senseID,
            pronunciations: [.init(id: pronunciationID, ipa: "tɛst", speechLocale: "en-US", region: "US")],
            senses: [.init(
                id: senseID,
                partOfSpeech: .phrase,
                meaning: ["en": "meaning", "zh-Hant": "meaning"],
                example: .init(text: "Example.", translation: ["zh-Hant": "例句。"]),
                pronunciationIDs: [pronunciationID]
            )],
            quiz: VocabularyQuiz(prompt: ["en": "prompt", "zh-Hant": "prompt"], options: ["A", "B"], correctOptionIndex: 0)
        )
    }
}
