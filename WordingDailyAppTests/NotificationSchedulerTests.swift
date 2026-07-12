import UserNotifications
import XCTest
@testable import WordingDailyApp

final class NotificationSchedulerTests: XCTestCase {
    func testDailyReminderIncludesTodayDeepLink() {
        let request = NotificationScheduler().dailyReminderRequest(
            hour: 8,
            minute: 30,
            title: "Reminder",
            body: "Practice"
        )

        XCTAssertEqual(NotificationScheduler.deepLinkUserInfoKey, "wording-daily.internal-url")
        XCTAssertEqual(
            request.content.userInfo[NotificationScheduler.deepLinkUserInfoKey] as? String,
            "wordingdaily://today"
        )
    }

    func testDailyReminderUsesFixedWordingDailyIdentifierAndRepeatingTime() throws {
        let request = NotificationScheduler().dailyReminderRequest(
            hour: 8,
            minute: 30,
            title: "今天的 10 個表達準備好了",
            body: "用幾分鐘完成今天的練習。"
        )

        XCTAssertEqual(request.identifier, NotificationScheduler.dailyReminderIdentifier)
        XCTAssertEqual(request.content.title, "今天的 10 個表達準備好了")
        XCTAssertEqual(request.content.body, "用幾分鐘完成今天的練習。")
        XCTAssertNotNil(request.content.sound)

        let trigger = try XCTUnwrap(request.trigger as? UNCalendarNotificationTrigger)
        XCTAssertTrue(trigger.repeats)
        XCTAssertEqual(trigger.dateComponents.hour, 8)
        XCTAssertEqual(trigger.dateComponents.minute, 30)
    }

    func testCancellationOnlyTargetsWordingDailyReminderIdentifiers() {
        let scheduler = NotificationScheduler()

        XCTAssertEqual(
            NotificationScheduler.reminderRequestIdentifiers,
            ["wording-daily.daily-reminder"]
        )
        XCTAssertEqual(
            scheduler.cancellationRequestIdentifiers(),
            NotificationScheduler.reminderRequestIdentifiers
        )
    }

    func testAuthorizationStatusMapsSystemValues() {
        XCTAssertEqual(ReminderAuthorizationStatus(.notDetermined), .notDetermined)
        XCTAssertEqual(ReminderAuthorizationStatus(.authorized), .authorized)
        XCTAssertEqual(ReminderAuthorizationStatus(.provisional), .authorized)
        XCTAssertEqual(ReminderAuthorizationStatus(.ephemeral), .authorized)
        XCTAssertEqual(ReminderAuthorizationStatus(.denied), .denied)
    }

    func testPlanSchedulesEnabledReminderWhenAuthorized() {
        let scheduler = NotificationScheduler()
        let preferences = UserPreferences(
            selectedLevel: .basic,
            reminderHour: 7,
            reminderMinute: 15,
            remindersEnabled: true,
            onboardingCompleted: true
        )

        let plan = scheduler.dailyReminderPlan(
            for: preferences,
            authorizationStatus: .authorized,
            title: "Today's 10 expression upgrades are ready.",
            body: "Take a few minutes to finish today's practice."
        )

        XCTAssertEqual(
            plan,
            .schedule(
                hour: 7,
                minute: 15,
                title: "Today's 10 expression upgrades are ready.",
                body: "Take a few minutes to finish today's practice."
            )
        )
    }

    func testPlanRequestsAuthorizationForEnabledReminderWhenPermissionIsNotDetermined() {
        let scheduler = NotificationScheduler()
        let preferences = UserPreferences(
            selectedLevel: .basic,
            reminderHour: 7,
            reminderMinute: 15,
            remindersEnabled: true,
            onboardingCompleted: true
        )

        XCTAssertEqual(
            scheduler.dailyReminderPlan(
                for: preferences,
                authorizationStatus: .notDetermined,
                title: "Today's 10 expression upgrades are ready.",
                body: "Take a few minutes to finish today's practice."
            ),
            .requestAuthorization
        )
    }

    func testPlanCancelsReminderWhenDisabledOrDenied() {
        let scheduler = NotificationScheduler()
        let disabledPreferences = UserPreferences(
            selectedLevel: .basic,
            reminderHour: 7,
            reminderMinute: 15,
            remindersEnabled: false,
            onboardingCompleted: true
        )
        let deniedPreferences = UserPreferences(
            selectedLevel: .basic,
            reminderHour: 7,
            reminderMinute: 15,
            remindersEnabled: true,
            onboardingCompleted: true
        )

        XCTAssertEqual(
            scheduler.dailyReminderPlan(
                for: disabledPreferences,
                authorizationStatus: .authorized,
                title: "Today's 10 expression upgrades are ready.",
                body: "Take a few minutes to finish today's practice."
            ),
            .cancel
        )
        XCTAssertEqual(
            scheduler.dailyReminderPlan(
                for: deniedPreferences,
                authorizationStatus: .denied,
                title: "Today's 10 expression upgrades are ready.",
                body: "Take a few minutes to finish today's practice."
            ),
            .cancel
        )
    }

    func testPlanCancelsEnabledReminderWhenTimeIsMissing() {
        let scheduler = NotificationScheduler()
        let preferences = UserPreferences(
            selectedLevel: .basic,
            reminderHour: nil,
            reminderMinute: 15,
            remindersEnabled: true,
            onboardingCompleted: true
        )

        XCTAssertEqual(
            scheduler.dailyReminderPlan(
                for: preferences,
                authorizationStatus: .authorized,
                title: "Today's 10 expression upgrades are ready.",
                body: "Take a few minutes to finish today's practice."
            ),
            .cancel
        )
    }
}
