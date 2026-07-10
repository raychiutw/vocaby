import XCTest
@testable import WordingDailyApp

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

    private func calendar(timeZone identifier: String) -> Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = Locale(identifier: "en_US_POSIX")
        calendar.timeZone = TimeZone(identifier: identifier)!
        return calendar
    }

    private func date(_ value: String) -> Date {
        ISO8601DateFormatter().date(from: value)!
    }
}
