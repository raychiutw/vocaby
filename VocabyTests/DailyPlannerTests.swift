import XCTest
@testable import Vocaby

final class DailyPlannerTests: XCTestCase {
    private let now = DayKeyService().date(for: "2026-07-10")!

    func testPicksTheFirstTenItemsOfTheSelectedLevelInSortOrder() {
        let seed = (1...12).map { item(String(format: "basic-%03d", $0), .basic, $0) }
            + [item("mid-001", .intermediate, 1)]

        let plan = DailyPlanner().plan(seed: seed, progressRows: [], preferences: .defaults, now: now)

        XCTAssertEqual(plan.itemIDs, (1...10).map { String(format: "basic-%03d", $0) })
        XCTAssertTrue(plan.reviewItemIDs.isEmpty)
    }

    func testSkipsItemsThatWereAlreadySeen() {
        let seed = (1...12).map { item(String(format: "basic-%03d", $0), .basic, $0) }
        let seen = (1...3).map { WordProgress(itemID: String(format: "basic-%03d", $0), level: .basic, firstSeenAt: now) }

        let plan = DailyPlanner().plan(seed: seed, progressRows: seen, preferences: .defaults, now: now)

        XCTAssertEqual(plan.itemIDs.first, "basic-004")
        XCTAssertFalse(plan.itemIDs.contains("basic-001"))
    }

    func testFillsTheRemainderWithDueReviewsWhenNewItemsRunOut() {
        let seed = (1...4).map { item(String(format: "basic-%03d", $0), .basic, $0) }
        let due = WordProgress(itemID: "basic-001", level: .basic, firstSeenAt: now, dueDayKey: "2026-07-10")

        let plan = DailyPlanner().plan(seed: seed, progressRows: [due], preferences: .defaults, now: now)

        XCTAssertEqual(Set(plan.itemIDs), ["basic-001", "basic-002", "basic-003", "basic-004"])
        XCTAssertEqual(plan.reviewItemIDs, ["basic-001"])
    }

    func testRespectsTheRetryDelayOfAFailedCard() {
        let seed = [item("basic-001", .basic, 1)]
        let failed = WordProgress(
            itemID: "basic-001", level: .basic, firstSeenAt: now,
            dueDayKey: "2026-07-10", nextReviewAt: now.addingTimeInterval(600)
        )
        let planner = DailyPlanner()

        XCTAssertTrue(planner.plan(seed: seed, progressRows: [failed], preferences: .defaults, now: now.addingTimeInterval(599)).reviewItemIDs.isEmpty)
        XCTAssertEqual(planner.plan(seed: seed, progressRows: [failed], preferences: .defaults, now: now.addingTimeInterval(600)).reviewItemIDs, ["basic-001"])
    }

    func testTargetCountFollowsTheDailyGoal() {
        let seed = (1...40).map { item(String(format: "basic-%03d", $0), .basic, $0) }
        var preferences = UserPreferences.defaults
        preferences.dailyGoal = 20

        let plan = DailyPlanner().plan(seed: seed, progressRows: [], preferences: preferences, now: now)

        XCTAssertEqual(plan.itemIDs.count, 20)
    }

    private func item(_ id: String, _ level: VocabularyLevel, _ sortOrder: Int) -> VocabularySeedItem {
        let pronunciationID = "\(id)-pronunciation-1"
        let senseID = "\(id)-sense-1"
        return VocabularySeedItem(
            id: id, level: level, sortOrder: sortOrder,
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
