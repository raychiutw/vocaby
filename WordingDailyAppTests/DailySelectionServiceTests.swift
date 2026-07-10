import XCTest
@testable import WordingDailyApp

final class DailySelectionServiceTests: XCTestCase {
    func testSelectsUnseenItemsForLevelLanguageAndSortOrder() {
        let items = [
            item("basic-003", level: .basic, sortOrder: 3),
            item("intermediate-001", level: .intermediate, sortOrder: 1),
            item("basic-001", level: .basic, sortOrder: 1),
            item("basic-002", level: .basic, sortOrder: 2),
            item("basic-004", level: .basic, sortOrder: 4, supportLanguageCodes: ["ja"])
        ]

        let selection = DailySelectionService().selectItems(
            from: items,
            selectedLevel: .basic,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant",
            firstSeenItemIDs: ["basic-002"],
            dueReviewItemIDs: [],
            targetCount: 2
        )

        XCTAssertEqual(selection.itemIDs, ["basic-001", "basic-003"])
        XCTAssertEqual(selection.newItemIDs, ["basic-001", "basic-003"])
        XCTAssertEqual(selection.reviewItemIDs, [])
        XCTAssertEqual(selection.status, .full)
    }

    func testFillsRemainingSlotsWithDueReviewsInProvidedOrder() {
        let items = [
            item("basic-001", level: .basic, sortOrder: 1),
            item("basic-002", level: .basic, sortOrder: 2),
            item("basic-003", level: .basic, sortOrder: 3),
            item("basic-004", level: .basic, sortOrder: 4)
        ]

        let selection = DailySelectionService().selectItems(
            from: items,
            selectedLevel: .basic,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant",
            firstSeenItemIDs: ["basic-002", "basic-003", "basic-004"],
            dueReviewItemIDs: ["basic-004", "basic-002", "missing"],
            targetCount: 3
        )

        XCTAssertEqual(selection.itemIDs, ["basic-001", "basic-004", "basic-002"])
        XCTAssertEqual(selection.newItemIDs, ["basic-001"])
        XCTAssertEqual(selection.reviewItemIDs, ["basic-004", "basic-002"])
        XCTAssertEqual(selection.status, .full)
    }

    func testReportsFewerThanTargetWhenSeedAndDueReviewsAreExhausted() {
        let items = [
            item("basic-001", level: .basic, sortOrder: 1),
            item("basic-002", level: .basic, sortOrder: 2)
        ]

        let selection = DailySelectionService().selectItems(
            from: items,
            selectedLevel: .basic,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant",
            firstSeenItemIDs: [],
            dueReviewItemIDs: [],
            targetCount: 10
        )

        XCTAssertEqual(selection.itemIDs, ["basic-001", "basic-002"])
        XCTAssertEqual(selection.status, .fewerThanTarget(availableCount: 2, targetCount: 10))
    }

    func testDueReviewsRespectLevelLanguageAndDuplicateFiltering() {
        let items = [
            item("basic-001", level: .basic, sortOrder: 1),
            item("basic-002", level: .basic, sortOrder: 2),
            item("advanced-001", level: .advanced, sortOrder: 1),
            item("basic-ja-001", level: .basic, sortOrder: 3, supportLanguageCodes: ["ja"])
        ]

        let selection = DailySelectionService().selectItems(
            from: items,
            selectedLevel: .basic,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant",
            firstSeenItemIDs: ["basic-002", "advanced-001", "basic-ja-001"],
            dueReviewItemIDs: ["basic-001", "basic-002", "advanced-001", "basic-ja-001", "basic-002"],
            targetCount: 3
        )

        XCTAssertEqual(selection.itemIDs, ["basic-001", "basic-002"])
        XCTAssertEqual(selection.newItemIDs, ["basic-001"])
        XCTAssertEqual(selection.reviewItemIDs, ["basic-002"])
        XCTAssertEqual(selection.status, .fewerThanTarget(availableCount: 2, targetCount: 3))
    }

    func testSavedOnlyProgressRemainsUnseenUntilFirstSeenTimestampIsSet() {
        let items = [
            item("basic-001", level: .basic, sortOrder: 1),
            item("basic-002", level: .basic, sortOrder: 2)
        ]
        let progressRows = [
            WordProgress(itemID: "basic-001", level: .basic, isSaved: true),
            WordProgress(
                itemID: "basic-002",
                level: .basic,
                firstSeenAt: Date(timeIntervalSince1970: 100)
            )
        ]

        let selection = DailySelectionService().selectItems(
            from: items,
            selectedLevel: .basic,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant",
            firstSeenItemIDs: Set(progressRows.compactMap { $0.firstSeenAt == nil ? nil : $0.itemID }),
            dueReviewItemIDs: [],
            targetCount: 10
        )

        XCTAssertEqual(selection.newItemIDs, ["basic-001"])
    }

    func testEligibleReviewIsNotHiddenBehindEarlierOffLevelDueRows() {
        let offLevelItems = (1...11).map { index in
            item(String(format: "advanced-%03d", index), level: .advanced, sortOrder: index)
        }
        let eligibleItem = item("basic-review", level: .basic, sortOrder: 1)
        let progressRows = offLevelItems.map { item in
            WordProgress(
                itemID: item.id,
                level: item.level,
                firstSeenAt: Date(timeIntervalSince1970: 100),
                dueDayKey: "2026-07-01"
            )
        } + [
            WordProgress(
                itemID: eligibleItem.id,
                level: eligibleItem.level,
                firstSeenAt: Date(timeIntervalSince1970: 100),
                dueDayKey: "2026-07-10"
            )
        ]
        let dueReviewItemIDs = ReviewScheduler()
            .allDueItems(from: progressRows, on: "2026-07-10")
            .map(\.itemID)

        let selection = DailySelectionService().selectItems(
            from: offLevelItems + [eligibleItem],
            selectedLevel: .basic,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant",
            firstSeenItemIDs: Set(progressRows.map(\.itemID)),
            dueReviewItemIDs: dueReviewItemIDs,
            targetCount: 10
        )

        XCTAssertEqual(selection.reviewItemIDs, ["basic-review"])
    }

    private func item(
        _ id: String,
        level: VocabularyLevel,
        sortOrder: Int,
        supportLanguageCodes: [String] = ["zh-Hant"]
    ) -> VocabularySeedItem {
        VocabularySeedItem(
            id: id,
            level: level,
            sortOrder: sortOrder,
            contentLanguageCode: "en",
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
