import Foundation

struct WidgetSnapshotExpression: Codable, Equatable {
    let itemID: String
    let plainExpression: String
    let upgradedExpression: String
}

struct WidgetSnapshot: Codable, Equatable {
    static let currentVersion = 1

    let version: Int
    let dayKey: String
    let progressCompleted: Int
    let progressTotal: Int
    let streakCount: Int
    let displayExpression: WidgetSnapshotExpression?
    let generatedAt: Date

    init(
        version: Int = Self.currentVersion,
        dayKey: String,
        progressCompleted: Int,
        progressTotal: Int,
        streakCount: Int,
        displayExpression: WidgetSnapshotExpression?,
        generatedAt: Date
    ) {
        self.version = version
        self.dayKey = dayKey
        self.progressCompleted = progressCompleted
        self.progressTotal = progressTotal
        self.streakCount = streakCount
        self.displayExpression = displayExpression
        self.generatedAt = generatedAt
    }

    static func fallback(dayKey: String, generatedAt: Date = Date()) -> WidgetSnapshot {
        WidgetSnapshot(
            dayKey: dayKey,
            progressCompleted: 0,
            progressTotal: 10,
            streakCount: 0,
            displayExpression: nil,
            generatedAt: generatedAt
        )
    }
}

struct WidgetSnapshotWriter {
    static let appGroupSuiteName = "group.com.raychiutw.WordingDaily"
    static let snapshotKey = "WordingDailyWidgetSnapshot"
    static let widgetKind = "WordingDailyWidget"

    private let userDefaults: UserDefaults
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(userDefaults: UserDefaults) {
        self.userDefaults = userDefaults
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
    }

    static func appGroupWriter() -> WidgetSnapshotWriter? {
        guard let defaults = UserDefaults(suiteName: appGroupSuiteName) else {
            return nil
        }

        return WidgetSnapshotWriter(userDefaults: defaults)
    }

    func write(_ snapshot: WidgetSnapshot) throws {
        let data = try encoder.encode(snapshot)
        userDefaults.set(data, forKey: Self.snapshotKey)
    }

    func read() -> WidgetSnapshot? {
        guard let data = userDefaults.data(forKey: Self.snapshotKey) else {
            return nil
        }

        return try? decoder.decode(WidgetSnapshot.self, from: data)
    }

    func snapshotOrFallback(dayKey: String, generatedAt: Date = Date()) -> WidgetSnapshot {
        guard let snapshot = read(),
              snapshot.version == WidgetSnapshot.currentVersion,
              snapshot.dayKey == dayKey else {
            return .fallback(dayKey: dayKey, generatedAt: generatedAt)
        }

        return snapshot
    }
}
