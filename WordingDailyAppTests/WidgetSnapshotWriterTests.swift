import XCTest
@testable import WordingDailyApp

final class WidgetSnapshotWriterTests: XCTestCase {
    func testWritesAndReadsVersionedSnapshot() throws {
        let defaults = makeDefaults()
        let writer = WidgetSnapshotWriter(userDefaults: defaults)
        let snapshot = WidgetSnapshot(
            dayKey: "2026-07-10",
            progressCompleted: 6,
            progressTotal: 10,
            streakCount: 4,
            displayExpression: WidgetSnapshotExpression(
                itemID: "basic-001",
                plainExpression: "very good",
                upgradedExpression: "excellent"
            ),
            generatedAt: date("2026-07-10T02:00:00Z")
        )

        try writer.write(snapshot)

        XCTAssertEqual(writer.read(), snapshot)
        XCTAssertEqual(writer.read()?.version, WidgetSnapshot.currentVersion)
    }

    func testFallbackSnapshotUsesIntentionalEmptyState() {
        let fallback = WidgetSnapshot.fallback(
            dayKey: "2026-07-10",
            generatedAt: date("2026-07-10T02:00:00Z")
        )

        XCTAssertEqual(fallback.version, WidgetSnapshot.currentVersion)
        XCTAssertEqual(fallback.dayKey, "2026-07-10")
        XCTAssertEqual(fallback.progressCompleted, 0)
        XCTAssertEqual(fallback.progressTotal, 10)
        XCTAssertEqual(fallback.streakCount, 0)
        XCTAssertNil(fallback.displayExpression)
    }

    func testCorruptStoredSnapshotFallsBack() {
        let defaults = makeDefaults()
        defaults.set(Data("not json".utf8), forKey: WidgetSnapshotWriter.snapshotKey)
        let writer = WidgetSnapshotWriter(userDefaults: defaults)
        let fallback = WidgetSnapshot.fallback(
            dayKey: "2026-07-10",
            generatedAt: date("2026-07-10T02:00:00Z")
        )

        XCTAssertEqual(
            writer.snapshotOrFallback(dayKey: "2026-07-10", generatedAt: date("2026-07-10T02:00:00Z")),
            fallback
        )
    }

    private func makeDefaults() -> UserDefaults {
        let suiteName = "WidgetSnapshotWriterTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }

    private func date(_ value: String) -> Date {
        ISO8601DateFormatter().date(from: value)!
    }
}
