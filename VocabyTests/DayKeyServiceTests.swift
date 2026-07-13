import XCTest
@testable import Vocaby

final class DayKeyServiceTests: XCTestCase {
    func testDayKeyHonorsInjectedTimeZone() {
        let taipeiService = DayKeyService(calendar: calendar(timeZone: "Asia/Taipei"))
        let losAngelesService = DayKeyService(calendar: calendar(timeZone: "America/Los_Angeles"))
        let date = date("2026-03-07T16:30:00Z")

        XCTAssertEqual(taipeiService.dayKey(for: date), "2026-03-08")
        XCTAssertEqual(losAngelesService.dayKey(for: date), "2026-03-07")
    }

    func testDayKeyStaysOnSameLocalDayAcrossDSTJump() {
        let service = DayKeyService(calendar: calendar(timeZone: "America/Los_Angeles"))

        XCTAssertEqual(service.dayKey(for: date("2026-03-08T09:30:00Z")), "2026-03-08")
        XCTAssertEqual(service.dayKey(for: date("2026-03-08T10:30:00Z")), "2026-03-08")
    }

    func testStreakRelationshipContinuesOnlyFromYesterday() {
        let service = DayKeyService(calendar: calendar(timeZone: "Asia/Taipei"))

        XCTAssertEqual(
            service.streakRelationship(previousCompletedDayKey: "2026-07-09", currentDayKey: "2026-07-10"),
            .continues
        )
        XCTAssertEqual(
            service.streakRelationship(previousCompletedDayKey: "2026-07-10", currentDayKey: "2026-07-10"),
            .sameDay
        )
    }

    func testStreakRelationshipMarksMissedAndBackwardDates() {
        let service = DayKeyService(calendar: calendar(timeZone: "Asia/Taipei"))

        XCTAssertEqual(
            service.streakRelationship(previousCompletedDayKey: "2026-07-08", currentDayKey: "2026-07-10"),
            .missed
        )
        XCTAssertEqual(
            service.streakRelationship(previousCompletedDayKey: "2026-07-10", currentDayKey: "2026-07-09"),
            .backwardDate
        )
    }

    func testStreakCountsConsecutiveCompletedDaysThroughToday() {
        let service = StreakService(dayKeyService: dayKeyService())

        XCTAssertEqual(
            service.streakCount(
                from: [
                    session(dayKey: "2026-07-08"),
                    session(dayKey: "2026-07-09"),
                    session(dayKey: "2026-07-10")
                ],
                currentDayKey: "2026-07-10"
            ),
            3
        )
    }

    func testStreakContinuesFromYesterdayBeforeTodayIsComplete() {
        let service = StreakService(dayKeyService: dayKeyService())

        XCTAssertEqual(
            service.streakCount(
                from: [
                    session(dayKey: "2026-07-08"),
                    session(dayKey: "2026-07-09"),
                    session(dayKey: "2026-07-10", isCompleted: false)
                ],
                currentDayKey: "2026-07-10"
            ),
            2
        )
    }

    func testStreakResetsWhenTodayFollowsAMissedDay() {
        let service = StreakService(dayKeyService: dayKeyService())

        XCTAssertEqual(
            service.streakCount(
                from: [session(dayKey: "2026-07-08"), session(dayKey: "2026-07-10")],
                currentDayKey: "2026-07-10"
            ),
            1
        )
    }

    func testStreakCountsDuplicateCompletedDayKeyOnce() {
        let service = StreakService(dayKeyService: dayKeyService())

        XCTAssertEqual(
            service.streakCount(
                from: [
                    session(dayKey: "2026-07-09"),
                    session(dayKey: "2026-07-09"),
                    session(dayKey: "2026-07-10")
                ],
                currentDayKey: "2026-07-10"
            ),
            2
        )
    }

    func testStreakIgnoresFutureCompletionAfterDateMovesBackward() {
        let service = StreakService(dayKeyService: dayKeyService())

        XCTAssertEqual(
            service.streakCount(
                from: [
                    session(dayKey: "2026-07-09"),
                    session(dayKey: "2026-07-10"),
                    session(dayKey: "2026-07-11")
                ],
                currentDayKey: "2026-07-10"
            ),
            2
        )
    }

    func testStreakExcludesCompletedSessionsWithoutItems() {
        let service = StreakService(dayKeyService: dayKeyService())

        XCTAssertEqual(
            service.streakCount(
                from: [
                    session(dayKey: "2026-07-09"),
                    session(dayKey: "2026-07-10", itemCount: 0)
                ],
                currentDayKey: "2026-07-10"
            ),
            1
        )
        XCTAssertEqual(
            service.streakCount(
                from: [session(dayKey: "2026-07-10", itemCount: 0)],
                currentDayKey: "2026-07-10"
            ),
            0
        )
    }

    private func calendar(timeZone identifier: String) -> Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = Locale(identifier: "en_US_POSIX")
        calendar.timeZone = TimeZone(identifier: identifier)!
        return calendar
    }

    private func dayKeyService() -> DayKeyService {
        DayKeyService(calendar: calendar(timeZone: "Asia/Taipei"))
    }

    private func session(
        dayKey: String,
        isCompleted: Bool = true,
        itemCount: Int = 1
    ) -> DailySession {
        let session = DailySession(
            dayKey: dayKey,
            targetItemCount: itemCount,
            completedAt: isCompleted ? date("2026-07-10T02:00:00Z") : nil
        )
        session.items = (0..<itemCount).map { index in
            DailySessionItem(
                itemID: "\(dayKey)-\(index)",
                position: index,
                answeredAt: isCompleted ? date("2026-07-10T02:00:00Z") : nil,
                wasCorrect: isCompleted
            )
        }
        return session
    }

    private func date(_ value: String) -> Date {
        ISO8601DateFormatter().date(from: value)!
    }
}
