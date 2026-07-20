import XCTest
@testable import Vocaby

final class SM2Tests: XCTestCase {
    private let scheduler = SM2()
    private let now = Date(timeIntervalSince1970: 1_700_000_000)

    func testFirstAndSecondSuccessfulIntervalsAreOneAndSixDays() {
        let first = scheduler.schedule(state: SM2State(), quality: 5, answeredAt: now)
        let second = scheduler.schedule(state: first.state, quality: 5, answeredAt: now)

        XCTAssertEqual(first.state.intervalDays, 1)
        XCTAssertEqual(second.state.intervalDays, 6)
    }

    func testLaterIntervalMultipliesByUpdatedEaseFactor() {
        let state = SM2State(easeFactor: 2.5, repetitionCount: 2, intervalDays: 6)
        let result = scheduler.schedule(state: state, quality: 5, answeredAt: now)

        XCTAssertEqual(result.state.intervalDays, 16)
    }

    func testFailureResetsRepetitionsAndReturnsInTenMinutes() {
        let state = SM2State(easeFactor: 2.5, repetitionCount: 3, intervalDays: 16)
        let result = scheduler.schedule(state: state, quality: 1, answeredAt: now)

        XCTAssertEqual(result.state.repetitionCount, 0)
        XCTAssertEqual(result.state.intervalDays, 0)
        XCTAssertEqual(result.nextReviewAt.timeIntervalSince(now), 600, accuracy: 0.001)
        XCTAssertFalse(result.isMastered)
    }

    func testEaseFactorNeverDropsBelowFloor() {
        var state = SM2State(easeFactor: 1.3, repetitionCount: 0, intervalDays: 0)
        for _ in 0..<10 {
            state = scheduler.schedule(state: state, quality: 0, answeredAt: now).state
        }
        XCTAssertEqual(state.easeFactor, 1.3, accuracy: 0.0001)
    }

    func testQualityIsClampedToValidRange() {
        XCTAssertEqual(
            scheduler.schedule(state: SM2State(), quality: 99, answeredAt: now).state,
            scheduler.schedule(state: SM2State(), quality: 5, answeredAt: now).state
        )
        XCTAssertEqual(
            scheduler.schedule(state: SM2State(), quality: -99, answeredAt: now).state,
            scheduler.schedule(state: SM2State(), quality: 0, answeredAt: now).state
        )
    }

    func testMasteryRequiresFourRepetitionsAndTwentyOneDayInterval() {
        let short = scheduler.schedule(
            state: SM2State(easeFactor: 1.3, repetitionCount: 3, intervalDays: 10),
            quality: 3,
            answeredAt: now
        )
        let long = scheduler.schedule(
            state: SM2State(easeFactor: 2.5, repetitionCount: 3, intervalDays: 16),
            quality: 5,
            answeredAt: now
        )

        XCTAssertFalse(short.isMastered)
        XCTAssertTrue(long.isMastered)
    }

    func testQualityFourIncreasesEaseLessThanQualityFive() {
        let four = scheduler.schedule(state: SM2State(), quality: 4, answeredAt: now)
        let five = scheduler.schedule(state: SM2State(), quality: 5, answeredAt: now)
        XCTAssertLessThan(four.state.easeFactor, five.state.easeFactor)
    }

    func testSuccessfulReviewSchedulesAfterAnsweredDate() {
        let result = scheduler.schedule(state: SM2State(), quality: 5, answeredAt: now)
        XCTAssertGreaterThan(result.nextReviewAt, now)
    }
}
