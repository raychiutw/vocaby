import XCTest
@testable import Vocaby

final class SeedCatalogTests: XCTestCase {
    private struct LoadFailure: Error {}

    func testLoadsOnceAndServesTheSameItemsAfterwards() throws {
        var loadCount = 0
        let catalog = SeedCatalog {
            loadCount += 1
            return SeedLoader.sampleItems
        }

        let first = try catalog.items()
        let second = try catalog.items()

        XCTAssertEqual(loadCount, 1)
        XCTAssertEqual(first.map(\.id), second.map(\.id))
        XCTAssertFalse(first.isEmpty)
    }

    func testAFailedLoadIsNotCachedSoTheNextCallRetries() throws {
        var attempts = 0
        let catalog = SeedCatalog {
            attempts += 1
            if attempts == 1 { throw LoadFailure() }
            return SeedLoader.sampleItems
        }

        XCTAssertThrowsError(try catalog.items())
        XCTAssertFalse(try catalog.items().isEmpty)
        _ = try catalog.items()

        XCTAssertEqual(attempts, 2, "失敗不快取;成功之後就不再載入")
    }

    func testTheBundledCatalogIsASingleSharedInstance() {
        XCTAssertTrue(SeedCatalog.bundled === SeedCatalog.bundled)
    }
}
