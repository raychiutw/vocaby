import XCTest
@testable import WordingDailyApp

final class VocabularySeedValidationTests: XCTestCase {
    func testBundledSeedHasThirtyItemsPerLevelAndPassesValidation() throws {
        let items = try SeedLoader().loadBundledSeed()

        XCTAssertEqual(items.count, 90)
        XCTAssertEqual(items.filter { $0.level == .basic }.count, 30)
        XCTAssertEqual(items.filter { $0.level == .intermediate }.count, 30)
        XCTAssertEqual(items.filter { $0.level == .advanced }.count, 30)
        XCTAssertNoThrow(try SeedValidator.validate(items))
    }

    func testValidationRejectsDuplicateIDs() throws {
        let item = try XCTUnwrap(SeedLoader.sampleItems.first)

        XCTAssertThrowsError(try SeedValidator.validate([item, item])) { error in
            XCTAssertEqual(error as? SeedValidationError, .duplicateID(item.id))
        }
    }

    func testValidationRejectsInvalidCorrectOptionIndex() throws {
        var item = try XCTUnwrap(SeedLoader.sampleItems.first)
        item.quiz.correctOptionIndex = item.quiz.options.count

        XCTAssertThrowsError(try SeedValidator.validate([item])) { error in
            XCTAssertEqual(error as? SeedValidationError, .invalidCorrectOptionIndex(item.id))
        }
    }

    func testValidationRejectsOutOfOrderSortOrderWithinLevel() throws {
        var first = try XCTUnwrap(SeedLoader.sampleItems.first)
        var second = try XCTUnwrap(SeedLoader.sampleItems.dropFirst().first)
        first.level = .basic
        second.level = .basic
        first.sortOrder = 2
        second.sortOrder = 1

        XCTAssertThrowsError(try SeedValidator.validate([first, second])) { error in
            XCTAssertEqual(error as? SeedValidationError, .sortOrderNotAscending(.basic))
        }
    }
}
