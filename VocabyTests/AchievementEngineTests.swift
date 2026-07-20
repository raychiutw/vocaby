import XCTest
@testable import Vocaby

final class AchievementEngineTests: XCTestCase {
    func testUnlocksThresholdAchievementsAndIsIdempotent() {
        let metrics = AchievementMetrics(
            learnedCount: 100,
            masteredCount: 100,
            savedCount: 10,
            currentStreak: 7,
            maximumDailyCount: 50,
            hasPerfectPractice: true
        )

        let first = AchievementEngine().newlyUnlocked(metrics: metrics, existing: [])
        XCTAssertTrue(first.contains(.firstStudy))
        XCTAssertTrue(first.contains(.streak7))
        XCTAssertTrue(first.contains(.perfectPractice))
        XCTAssertFalse(first.contains(.streak30))
        XCTAssertFalse(first.contains(.learn500))
        XCTAssertTrue(AchievementEngine().newlyUnlocked(metrics: metrics, existing: Set(first)).isEmpty)
    }

    func testPerfectPracticeRequiresEveryAnswerInOneRunToBeCorrect() {
        let attempts = [
            PracticeAttemptRecord(runID: "mixed", itemID: "one", level: .basic, mode: .mixed, wasCorrect: true),
            PracticeAttemptRecord(runID: "mixed", itemID: "two", level: .basic, mode: .mixed, wasCorrect: false),
            PracticeAttemptRecord(runID: "perfect", itemID: "three", level: .basic, mode: .mixed, wasCorrect: true)
        ]
        let metrics = AchievementMetrics.make(progressRows: [], sessions: [], attempts: attempts)
        XCTAssertTrue(metrics.hasPerfectPractice)
    }
}
