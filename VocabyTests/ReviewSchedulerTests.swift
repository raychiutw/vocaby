import XCTest
@testable import Vocaby

final class ReviewSchedulerTests: XCTestCase {
    func testCorrectAnswersFollowReviewLadderAndMasterAtFour() {
        let scheduler = ReviewScheduler(dayKeyService: dayKeyService())
        let progress = WordProgress(itemID: "basic-001", level: .basic)

        scheduler.applyAnswer(to: progress, wasCorrect: true, answeredAt: date("2026-07-10T02:00:00Z"), context: .dailyPractice)
        XCTAssertEqual(progress.correctCount, 1)
        XCTAssertEqual(progress.dueDayKey, "2026-07-11")
        XCTAssertNil(progress.masteredAt)

        scheduler.applyAnswer(to: progress, wasCorrect: true, answeredAt: date("2026-07-11T02:00:00Z"), context: .review)
        XCTAssertEqual(progress.correctCount, 2)
        XCTAssertEqual(progress.dueDayKey, "2026-07-14")

        scheduler.applyAnswer(to: progress, wasCorrect: true, answeredAt: date("2026-07-14T02:00:00Z"), context: .review)
        XCTAssertEqual(progress.correctCount, 3)
        XCTAssertEqual(progress.dueDayKey, "2026-07-21")

        scheduler.applyAnswer(to: progress, wasCorrect: true, answeredAt: date("2026-07-21T02:00:00Z"), context: .review)
        XCTAssertEqual(progress.correctCount, 4)
        XCTAssertNil(progress.dueDayKey)
        XCTAssertNotNil(progress.masteredAt)
    }

    func testWrongDailyPracticeAnswerSchedulesSameDayReview() {
        let scheduler = ReviewScheduler(dayKeyService: dayKeyService())
        let progress = WordProgress(itemID: "basic-001", level: .basic, correctCount: 2)

        scheduler.applyAnswer(to: progress, wasCorrect: false, answeredAt: date("2026-07-10T02:00:00Z"), context: .dailyPractice)

        XCTAssertEqual(progress.correctCount, 2)
        XCTAssertEqual(progress.wrongCount, 1)
        XCTAssertEqual(progress.dueDayKey, "2026-07-10")
        XCTAssertNil(progress.masteredAt)
    }

    func testWrongReviewAnswerSchedulesNextDay() {
        let scheduler = ReviewScheduler(dayKeyService: dayKeyService())
        let firstSeenAt = date("2026-07-01T02:00:00Z")
        let answeredAt = date("2026-07-10T02:00:00Z")
        let progress = WordProgress(
            itemID: "basic-001",
            level: .basic,
            firstSeenAt: firstSeenAt,
            correctCount: 2
        )

        scheduler.applyAnswer(to: progress, wasCorrect: false, answeredAt: answeredAt, context: .review)

        XCTAssertEqual(progress.correctCount, 2)
        XCTAssertEqual(progress.wrongCount, 1)
        XCTAssertEqual(progress.dueDayKey, "2026-07-11")
        XCTAssertEqual(progress.firstSeenAt, firstSeenAt)
        XCTAssertEqual(progress.lastReviewedAt, answeredAt)
        XCTAssertNil(progress.masteredAt)
    }

    func testPersistedSessionItemContextSchedulesReviewFillForNextDay() {
        let scheduler = ReviewScheduler(dayKeyService: dayKeyService())
        let answeredAt = date("2026-07-10T02:00:00Z")
        let newProgress = WordProgress(itemID: "basic-001", level: .basic)
        let reviewProgress = WordProgress(itemID: "basic-002", level: .basic)

        scheduler.applyAnswer(
            to: newProgress,
            wasCorrect: false,
            answeredAt: answeredAt,
            context: DailySessionItem(itemID: "basic-001", position: 0).reviewAnswerContext
        )
        scheduler.applyAnswer(
            to: reviewProgress,
            wasCorrect: false,
            answeredAt: answeredAt,
            context: DailySessionItem(itemID: "basic-002", position: 1, isReviewFill: true).reviewAnswerContext
        )

        XCTAssertEqual(newProgress.dueDayKey, "2026-07-10")
        XCTAssertEqual(reviewProgress.dueDayKey, "2026-07-11")
    }

    func testDueItemsExcludeMasteredAndFutureThenSortByDueDayWrongCountAndID() {
        let scheduler = ReviewScheduler(dayKeyService: dayKeyService())
        let dueLowWrong = progress("basic-002", dueDayKey: "2026-07-10", wrongCount: 1)
        let dueHighWrong = progress("basic-001", dueDayKey: "2026-07-10", wrongCount: 3)
        let olderDue = progress("basic-003", dueDayKey: "2026-07-09", wrongCount: 1)
        let future = progress("basic-004", dueDayKey: "2026-07-11", wrongCount: 9)
        let mastered = progress("basic-005", dueDayKey: "2026-07-09", wrongCount: 9, masteredAt: date("2026-07-09T02:00:00Z"))

        let dueItems = scheduler.dueItems(
            from: [dueLowWrong, dueHighWrong, olderDue, future, mastered],
            on: "2026-07-10",
            limit: 20
        )

        XCTAssertEqual(dueItems.map(\.itemID), ["basic-003", "basic-001", "basic-002"])
    }

    func testDueItemsRespectLimit() {
        let scheduler = ReviewScheduler(dayKeyService: dayKeyService())
        let dueItems = (1...25).map { index in
            progress(String(format: "basic-%03d", index), dueDayKey: "2026-07-10", wrongCount: 0)
        }

        XCTAssertEqual(scheduler.dueItems(from: dueItems, on: "2026-07-10", limit: 20).count, 20)
    }

    func testDueCountReportsAllItemsBeyondQueueLimit() {
        let scheduler = ReviewScheduler(dayKeyService: dayKeyService())
        let dueItems = (1...25).map { index in
            progress(String(format: "basic-%03d", index), dueDayKey: "2026-07-10", wrongCount: 0)
        }

        XCTAssertEqual(scheduler.dueCount(from: dueItems, on: "2026-07-10"), 25)
    }

    private func progress(
        _ itemID: String,
        dueDayKey: String,
        wrongCount: Int,
        masteredAt: Date? = nil
    ) -> WordProgress {
        WordProgress(
            itemID: itemID,
            level: .basic,
            correctCount: 0,
            dueDayKey: dueDayKey,
            wrongCount: wrongCount,
            masteredAt: masteredAt
        )
    }

    private func dayKeyService() -> DayKeyService {
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = Locale(identifier: "en_US_POSIX")
        calendar.timeZone = TimeZone(identifier: "Asia/Taipei")!
        return DayKeyService(calendar: calendar)
    }

    private func date(_ value: String) -> Date {
        ISO8601DateFormatter().date(from: value)!
    }
}
