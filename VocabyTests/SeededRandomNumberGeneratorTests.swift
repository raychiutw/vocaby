import XCTest
@testable import Vocaby

final class SeededRandomNumberGeneratorTests: XCTestCase {
    func testSameSeedProducesSameSequence() {
        var a = SeededRandomNumberGenerator(seed: 42)
        var b = SeededRandomNumberGenerator(seed: 42)
        XCTAssertEqual((0..<8).map { _ in a.next() }, (0..<8).map { _ in b.next() })
    }

    func testDifferentSeedsProduceDifferentSequences() {
        var a = SeededRandomNumberGenerator(seed: 1)
        var b = SeededRandomNumberGenerator(seed: 2)
        XCTAssertNotEqual((0..<8).map { _ in a.next() }, (0..<8).map { _ in b.next() })
    }

    func testLaunchValueParsing() {
        XCTAssertEqual(SeededRandomNumberGenerator(fromLaunchValue: "7")?.seed, 7)
        XCTAssertNil(SeededRandomNumberGenerator(fromLaunchValue: nil))
        XCTAssertNil(SeededRandomNumberGenerator(fromLaunchValue: "abc"))
    }
}
