import Foundation

extension Notification.Name {
    static let vocabyPreferencesDidChange = Notification.Name("VocabyPreferencesDidChange")
}

enum AppAppearance: String, Codable, CaseIterable {
    case system
    case light
    case dark
}

struct UserPreferences: Codable, Equatable {
    static let defaults = UserPreferences(
        selectedLevel: .basic,
        reminderHour: 8,
        reminderMinute: 30,
        remindersEnabled: false,
        onboardingCompleted: false,
        dailyGoal: 10,
        autoplayPronunciation: false,
        appearance: .system
    )

    var selectedLevel: VocabularyLevel
    var reminderHour: Int?
    var reminderMinute: Int?
    var remindersEnabled: Bool
    var onboardingCompleted: Bool
    var dailyGoal: Int
    var autoplayPronunciation: Bool
    var appearance: AppAppearance

    init(
        selectedLevel: VocabularyLevel,
        reminderHour: Int?,
        reminderMinute: Int?,
        remindersEnabled: Bool,
        onboardingCompleted: Bool,
        dailyGoal: Int = 10,
        autoplayPronunciation: Bool = false,
        appearance: AppAppearance = .system
    ) {
        self.selectedLevel = selectedLevel
        self.reminderHour = reminderHour
        self.reminderMinute = reminderMinute
        self.remindersEnabled = remindersEnabled
        self.onboardingCompleted = onboardingCompleted
        self.dailyGoal = Self.validDailyGoal(dailyGoal)
        self.autoplayPronunciation = autoplayPronunciation
        self.appearance = appearance
    }

    private enum CodingKeys: String, CodingKey {
        case selectedLevel, reminderHour, reminderMinute, remindersEnabled, onboardingCompleted
        case dailyGoal, autoplayPronunciation, appearance
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        self.init(
            selectedLevel: try values.decode(VocabularyLevel.self, forKey: .selectedLevel),
            reminderHour: try values.decodeIfPresent(Int.self, forKey: .reminderHour),
            reminderMinute: try values.decodeIfPresent(Int.self, forKey: .reminderMinute),
            remindersEnabled: try values.decode(Bool.self, forKey: .remindersEnabled),
            onboardingCompleted: try values.decode(Bool.self, forKey: .onboardingCompleted),
            dailyGoal: try values.decodeIfPresent(Int.self, forKey: .dailyGoal) ?? 10,
            autoplayPronunciation: try values.decodeIfPresent(Bool.self, forKey: .autoplayPronunciation) ?? false,
            appearance: try values.decodeIfPresent(AppAppearance.self, forKey: .appearance) ?? .system
        )
    }

    static func validDailyGoal(_ value: Int) -> Int {
        min(100, max(10, Int((Double(value) / 5).rounded()) * 5))
    }

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

    mutating func completeOnboarding(
        selectedLevel: VocabularyLevel,
        remindersEnabled: Bool,
        reminderTime: Date?,
        calendar: Calendar = .current
    ) {
        self.selectedLevel = selectedLevel
        self.remindersEnabled = remindersEnabled
        onboardingCompleted = true

        if let reminderTime {
            setReminderTime(reminderTime, calendar: calendar)
        }
    }
}

struct UserPreferencesStore {
    static let storageKey = "VocabyUserPreferences"

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
        NotificationCenter.default.post(name: .vocabyPreferencesDidChange, object: nil)
    }
}
