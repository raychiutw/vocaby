import XCTest
@testable import Vocaby

final class TodayProgressTests: XCTestCase {
    private let answeredAt = Date(timeIntervalSince1970: 1_800_000_000)

    func testWithoutASessionTheTotalFallsBackToTheDailyGoal() {
        let progress = TodayProgress(session: nil, dailyGoal: 10)

        XCTAssertEqual(progress.completed, 0)
        XCTAssertEqual(progress.total, 10)
        XCTAssertNil(progress.nextItemID)
    }

    func testTheDailyGoalIsOnlyReadWhenTheSessionHasNoItems() {
        var reads = 0
        let goal = { () -> Int in reads += 1; return 10 }
        let withItems = session([DailySessionItem(itemID: "a", position: 0)])

        _ = TodayProgress(session: withItems, dailyGoal: goal())
        XCTAssertEqual(reads, 0, "有項目時不該去讀偏好")

        _ = TodayProgress(session: nil, dailyGoal: goal())
        XCTAssertEqual(reads, 1)
    }

    func testCountsAnsweredItemsAndPicksTheFirstUnansweredByPosition() {
        // 故意不照 position 排列,結果不能依賴陣列順序
        let session = session([
            DailySessionItem(itemID: "c", position: 2),
            DailySessionItem(itemID: "a", position: 0, answeredAt: answeredAt, wasCorrect: true),
            DailySessionItem(itemID: "b", position: 1)
        ])

        let progress = TodayProgress(session: session, dailyGoal: 10)

        XCTAssertEqual(progress.completed, 1)
        XCTAssertEqual(progress.total, 3, "有項目時以項目數為準,不是每日目標")
        XCTAssertEqual(progress.nextItemID, "b")
    }

    func testWhenEverythingIsAnsweredThereIsNoNextItem() {
        let session = session([
            DailySessionItem(itemID: "a", position: 0, answeredAt: answeredAt, wasCorrect: true),
            DailySessionItem(itemID: "b", position: 1, answeredAt: answeredAt, wasCorrect: false)
        ])

        let progress = TodayProgress(session: session, dailyGoal: 10)

        XCTAssertEqual(progress.completed, 2)
        XCTAssertEqual(progress.total, 2)
        XCTAssertNil(progress.nextItemID)
    }

    func testWidgetSnapshotIsBuiltFromTheSessionWithoutAnyViewState() {
        let session = session([
            DailySessionItem(itemID: "basic-001", position: 0, answeredAt: answeredAt, wasCorrect: true),
            DailySessionItem(itemID: "basic-002", position: 1)
        ])

        let snapshot = WidgetSnapshot.today(
            dayKey: "2026-07-10",
            session: session,
            seedItems: [seed("basic-001"), seed("basic-002")],
            streakCount: 4,
            dailyGoal: 10,
            generatedAt: answeredAt
        )

        XCTAssertEqual(snapshot.dayKey, "2026-07-10")
        XCTAssertEqual(snapshot.progressCompleted, 1)
        XCTAssertEqual(snapshot.progressTotal, 2)
        XCTAssertEqual(snapshot.streakCount, 4)
        XCTAssertEqual(snapshot.generatedAt, answeredAt)
        XCTAssertEqual(snapshot.displayExpression?.itemID, "basic-002")
        XCTAssertEqual(snapshot.displayExpression?.upgradedExpression, "upgraded basic-002")
    }

    func testWidgetSnapshotHasNoExpressionWhenTheNextItemIsNotInTheSeed() {
        let session = session([DailySessionItem(itemID: "removed-item", position: 0)])

        let snapshot = WidgetSnapshot.today(
            dayKey: "2026-07-10", session: session, seedItems: [seed("basic-001")],
            streakCount: 0, dailyGoal: 10, generatedAt: answeredAt
        )

        XCTAssertNil(snapshot.displayExpression)
    }

    private func session(_ items: [DailySessionItem]) -> DailySession {
        let session = DailySession(dayKey: "2026-07-10", targetItemCount: items.count)
        session.items = items
        return session
    }

    private func seed(_ id: String) -> VocabularySeedItem {
        let pronunciationID = "\(id)-pronunciation-1"
        let senseID = "\(id)-sense-1"
        return VocabularySeedItem(
            id: id, level: .basic, sortOrder: 1,
            contentLanguageCode: "en", supportLanguageCodes: ["zh-Hant"],
            plainExpression: "plain \(id)", upgradedExpression: "upgraded \(id)",
            primarySenseID: senseID,
            pronunciations: [.init(id: pronunciationID, ipa: "tɛst", speechLocale: "en-US", region: "US")],
            senses: [.init(
                id: senseID, partOfSpeech: .phrase,
                meaning: ["en": "meaning", "zh-Hant": "meaning"],
                example: .init(text: "Example.", translation: ["zh-Hant": "例句。"]),
                pronunciationIDs: [pronunciationID]
            )],
            quiz: VocabularyQuiz(prompt: ["en": "prompt", "zh-Hant": "prompt"], options: ["A", "B"], correctOptionIndex: 0)
        )
    }
}
