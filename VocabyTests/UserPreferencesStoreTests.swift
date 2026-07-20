import XCTest
@testable import Vocaby

final class UserPreferencesStoreTests: XCTestCase {
    func testDefaultsStartAtBasicWithReminderOffAndOnboardingIncomplete() {
        let store = UserPreferencesStore(userDefaults: makeDefaults())
        let preferences = store.read()

        XCTAssertEqual(preferences.selectedLevel, .basic)
        XCTAssertEqual(preferences.reminderHour, 8)
        XCTAssertEqual(preferences.reminderMinute, 30)
        XCTAssertFalse(preferences.remindersEnabled)
        XCTAssertFalse(preferences.onboardingCompleted)
        XCTAssertEqual(preferences.dailyGoal, 10)
        XCTAssertFalse(preferences.autoplayPronunciation)
        XCTAssertEqual(preferences.appearance, .system)
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

    func testLegacyPreferencesDecodeWithNewDefaults() throws {
        let defaults = makeDefaults()
        defaults.set(Data(#"{"selectedLevel":"basic","reminderHour":8,"reminderMinute":30,"remindersEnabled":false,"onboardingCompleted":true}"#.utf8), forKey: UserPreferencesStore.storageKey)

        let preferences = UserPreferencesStore(userDefaults: defaults).read()

        XCTAssertEqual(preferences.dailyGoal, 10)
        XCTAssertFalse(preferences.autoplayPronunciation)
        XCTAssertEqual(preferences.appearance, .system)
    }

    func testDailyGoalClampsAndRoundsToFive() {
        XCTAssertEqual(UserPreferences.validDailyGoal(7), 10)
        XCTAssertEqual(UserPreferences.validDailyGoal(43), 45)
        XCTAssertEqual(UserPreferences.validDailyGoal(103), 100)
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

    func testCompletingOnboardingStoresLevelAndReminderChoice() {
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = Locale(identifier: "en_US_POSIX")
        calendar.timeZone = TimeZone(identifier: "Asia/Taipei")!
        var preferences = UserPreferences.defaults
        let reminderTime = calendar.date(from: DateComponents(year: 2026, month: 7, day: 10, hour: 7, minute: 15))!

        preferences.completeOnboarding(
            selectedLevel: .intermediate,
            remindersEnabled: true,
            reminderTime: reminderTime,
            calendar: calendar
        )

        XCTAssertTrue(preferences.onboardingCompleted)
        XCTAssertEqual(preferences.selectedLevel, .intermediate)
        XCTAssertTrue(preferences.remindersEnabled)
        XCTAssertEqual(preferences.reminderHour, 7)
        XCTAssertEqual(preferences.reminderMinute, 15)
    }

    func testCompletingOnboardingWithSkippedReminderKeepsReminderOff() {
        var preferences = UserPreferences(
            selectedLevel: .advanced,
            reminderHour: 21,
            reminderMinute: 30,
            remindersEnabled: true,
            onboardingCompleted: false
        )

        preferences.completeOnboarding(
            selectedLevel: .basic,
            remindersEnabled: false,
            reminderTime: nil
        )

        XCTAssertTrue(preferences.onboardingCompleted)
        XCTAssertEqual(preferences.selectedLevel, .basic)
        XCTAssertFalse(preferences.remindersEnabled)
        XCTAssertEqual(preferences.reminderHour, 21)
        XCTAssertEqual(preferences.reminderMinute, 30)
    }

    private func makeDefaults() -> UserDefaults {
        let suiteName = "UserPreferencesStoreTests.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defaults.removePersistentDomain(forName: suiteName)
        return defaults
    }
}
