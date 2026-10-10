import XCTest
@testable import Vocaby

final class AppClockTests: XCTestCase {
    func testFixedClockAlwaysReturnsTheSameInstant() {
        let instant = Date(timeIntervalSince1970: 1_800_000_000)
        let clock = AppClock.fixed(instant)

        XCTAssertEqual(clock.now(), instant)
        XCTAssertEqual(clock.now(), instant)
    }

    func testSystemClockFollowsRealTime() {
        let before = Date()
        let reading = AppClock.system.now()
        let after = Date()

        XCTAssertGreaterThanOrEqual(reading, before)
        XCTAssertLessThanOrEqual(reading, after)
    }

    func testLaunchArgumentValueParsesIntoFixedClock() throws {
        let clock = try XCTUnwrap(AppClock.fixed(fromLaunchValue: "2026-07-10T09:00:00+08:00"))

        XCTAssertEqual(clock.now(), ISO8601DateFormatter().date(from: "2026-07-10T09:00:00+08:00"))
        XCTAssertNil(AppClock.fixed(fromLaunchValue: "not-a-date"))
        XCTAssertNil(AppClock.fixed(fromLaunchValue: nil))
    }
}
