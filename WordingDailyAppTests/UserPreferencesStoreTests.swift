import XCTest
@testable import WordingDailyApp

final class UserPreferencesStoreTests: XCTestCase {
    func testDefaultsStartAtBasicWithReminderOffAndOnboardingIncomplete() {
        let store = UserPreferencesStore(userDefaults: makeDefaults())
        let preferences = store.read()

        XCTAssertEqual(preferences.selectedLevel, .basic)
        XCTAssertEqual(preferences.reminderHour, 8)
        XCTAssertEqual(preferences.reminderMinute, 30)
        XCTAssertFalse(preferences.remindersEnabled)
        XCTAssertFalse(preferences.onboardingCompleted)
        XCTAssertNil(preferences.enabledReminderDateComponents)
    }

    func testWritesAndReadsPreferences() throws {
        let store = UserPreferencesStore(userDefaults: makeDefaults())
        let preferences = UserPreferences(
            selectedLevel: .advanced,
            reminderHour: 21,
            reminderMinute: 5,
            remindersEnabled: true,
            onboardingCompleted: true
        )

        try store.write(preferences)

        XCTAssertEqual(store.read(), preferences)
        XCTAssertEqual(store.read().enabledReminderDateComponents?.hour, 21)
        XCTAssertEqual(store.read().enabledReminderDateComponents?.minute, 5)
    }

    func testCorruptStoredPreferencesFallsBackToDefaults() {
        let defaults = makeDefaults()
        defaults.set(Data("not json".utf8), forKey: UserPreferencesStore.storageKey)
        let store = UserPreferencesStore(userDefaults: defaults)

        XCTAssertEqual(store.read(), .defaults)
    }

    func testReminderTimeDateRoundTripsThroughCalendarComponents() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = Locale(identifier: "en_US_POSIX")
        calendar.timeZone = TimeZone(identifier: "Asia/Taipei")!
        var preferences = UserPreferences.defaults
        let date = calendar.date(from: DateComponents(year: 2026, month: 7, day: 10, hour: 21, minute: 45))!

        preferences.setReminderTime(date, calendar: calendar)

        XCTAssertEqual(preferences.reminderHour, 21)
        XCTAssertEqual(preferences.reminderMinute, 45)
        XCTAssertEqual(calendar.component(.hour, from: preferences.reminderTimeDate(calendar: calendar)), 21)
        XCTAssertEqual(calendar.component(.minute, from: preferences.reminderTimeDate(calendar: calendar)), 45)
    }

    private func makeDefaults() -> UserDefaults {
        let suiteName = "UserPreferencesStoreTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }
}
