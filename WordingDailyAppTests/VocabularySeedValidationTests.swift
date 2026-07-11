import XCTest
@testable import WordingDailyApp

final class VocabularySeedValidationTests: XCTestCase {
    func testBundledSeedHasCompleteRichEntries() throws {
        let items = try SeedLoader().loadBundledSeed()

        XCTAssertEqual(items.count, 5_221)
        XCTAssertEqual(items.filter { $0.level == .basic }.count, 980)
        XCTAssertEqual(items.filter { $0.level == .intermediate }.count, 1_630)
        XCTAssertEqual(items.filter { $0.level == .advanced }.count, 2_611)
        for item in items {
            XCTAssertFalse(item.pronunciations.isEmpty, item.id)
            XCTAssertTrue((1...3).contains(item.senses.count), item.id)
            XCTAssertEqual(item.primarySense.id, item.primarySenseID, item.id)
            let pronunciationIDs = Set(item.pronunciations.map(\.id))
            XCTAssertTrue(item.senses.allSatisfy { sense in
                !sense.pronunciationIDs.isEmpty
                    && Set(sense.pronunciationIDs).isSubset(of: pronunciationIDs)
                    && !sense.meaning["en", default: ""].isEmpty
                    && !sense.meaning["zh-Hant", default: ""].isEmpty
                    && !sense.example.text.isEmpty
                    && !sense.example.translation["zh-Hant", default: ""].isEmpty
            }, item.id)
        }
        XCTAssertNoThrow(try SeedValidator.validate(items))
    }

    func testBundledVocabularyNoticesExist() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "ThirdPartyNotices", withExtension: "txt"))
        XCTAssertFalse(try String(contentsOf: url, encoding: .utf8).isEmpty)
    }

    func testValidationRejectsDuplicateIDs() throws {
        let item = try XCTUnwrap(SeedLoader.sampleItems.first)

        XCTAssertThrowsError(try SeedValidator.validate([item, item])) { error in
            XCTAssertEqual(error as? SeedValidationError, .duplicateID(item.id))
        }
    }

    func testBundledSeedHasUniqueUpgradedExpressions() throws {
        let items = try SeedLoader().loadBundledSeed()
        let normalized = items.map {
            $0.upgradedExpression.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        }

        XCTAssertEqual(Set(normalized).count, items.count)
    }

    func testBundledSeedKeepsQuizAndPronunciationAligned() throws {
        for item in try SeedLoader().loadBundledSeed() {
            XCTAssertEqual(item.quiz.options[item.quiz.correctOptionIndex], item.upgradedExpression, item.id)
            XCTAssertTrue(item.pronunciations.allSatisfy { $0.speechLocale.hasPrefix("en-") }, item.id)
        }
    }

    func testValidationRejectsUnknownPronunciationReference() throws {
        var item = try XCTUnwrap(SeedLoader.sampleItems.first)
        item.senses[0].pronunciationIDs = ["missing"]

        XCTAssertThrowsError(try SeedValidator.validate([item])) { error in
            XCTAssertEqual(error as? SeedValidationError, .invalidPronunciationReference(item.id))
        }
    }

    func testValidationRejectsInvalidCorrectOptionIndex() throws {
        var item = try XCTUnwrap(SeedLoader.sampleItems.first)
        item.quiz.correctOptionIndex = item.quiz.options.count

        XCTAssertThrowsError(try SeedValidator.validate([item])) { error in
            XCTAssertEqual(error as? SeedValidationError, .invalidCorrectOptionIndex(item.id))
        }
    }

    func testValidationRejectsMissingRequiredField() throws {
        var item = try XCTUnwrap(SeedLoader.sampleItems.first)
        item.upgradedExpression = ""

        XCTAssertThrowsError(try SeedValidator.validate([item])) { error in
            XCTAssertEqual(error as? SeedValidationError, .missingRequiredField(item.id))
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
