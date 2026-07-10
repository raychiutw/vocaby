import Foundation

struct UserPreferences: Codable, Equatable {
    static let defaults = UserPreferences(
        selectedLevel: .basic,
        reminderHour: 8,
        reminderMinute: 30,
        remindersEnabled: false,
        onboardingCompleted: false
    )

    var selectedLevel: VocabularyLevel
    var reminderHour: Int?
    var reminderMinute: Int?
    var remindersEnabled: Bool
    var onboardingCompleted: Bool

    var enabledReminderDateComponents: DateComponents? {
        guard
            remindersEnabled,
            let reminderHour,
            let reminderMinute,
            (0...23).contains(reminderHour),
            (0...59).contains(reminderMinute)
        else {
            return nil
        }

        var components = DateComponents()
        components.hour = reminderHour
        components.minute = reminderMinute
        return components
    }

    func reminderTimeDate(calendar: Calendar = .current) -> Date {
        calendar.date(from: DateComponents(hour: reminderHour ?? 8, minute: reminderMinute ?? 30)) ?? Date()
    }

    mutating func setReminderTime(_ date: Date, calendar: Calendar = .current) {
        reminderHour = calendar.component(.hour, from: date)
        reminderMinute = calendar.component(.minute, from: date)
    }
}

struct UserPreferencesStore {
    static let storageKey = "WordingDailyUserPreferences"

    private let userDefaults: UserDefaults
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(userDefaults: UserDefaults = .standard) {
        self.userDefaults = userDefaults
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
    }

    func read() -> UserPreferences {
        guard let data = userDefaults.data(forKey: Self.storageKey) else {
            return .defaults
        }

        return (try? decoder.decode(UserPreferences.self, from: data)) ?? .defaults
    }

    func write(_ preferences: UserPreferences) throws {
        let data = try encoder.encode(preferences)
        userDefaults.set(data, forKey: Self.storageKey)
    }
}
