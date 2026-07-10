import Foundation
import UserNotifications

enum ReminderAuthorizationStatus: Equatable {
    case notDetermined
    case authorized
    case denied

    init(_ status: UNAuthorizationStatus) {
        switch status {
        case .notDetermined:
            self = .notDetermined
        case .authorized, .provisional, .ephemeral:
            self = .authorized
        case .denied:
            self = .denied
        @unknown default:
            self = .denied
        }
    }
}

enum DailyReminderPlan: Equatable {
    case cancel
    case requestAuthorization
    case schedule(hour: Int, minute: Int, title: String, body: String)
}

struct NotificationScheduler {
    static let dailyReminderIdentifier = "wording-daily.daily-reminder"
    static let reminderRequestIdentifiers = [dailyReminderIdentifier]

    func dailyReminderPlan(
        for preferences: UserPreferences,
        authorizationStatus: ReminderAuthorizationStatus,
        title: String,
        body: String
    ) -> DailyReminderPlan {
        guard
            let dateComponents = preferences.enabledReminderDateComponents,
            let hour = dateComponents.hour,
            let minute = dateComponents.minute
        else {
            return .cancel
        }

        switch authorizationStatus {
        case .notDetermined:
            return .requestAuthorization
        case .authorized:
            return .schedule(
                hour: hour,
                minute: minute,
                title: title,
                body: body
            )
        case .denied:
            return .cancel
        }
    }

    func dailyReminderRequest(
        hour: Int,
        minute: Int,
        title: String,
        body: String
    ) -> UNNotificationRequest {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default

        var dateComponents = DateComponents()
        dateComponents.hour = hour
        dateComponents.minute = minute

        let trigger = UNCalendarNotificationTrigger(dateMatching: dateComponents, repeats: true)
        return UNNotificationRequest(identifier: Self.dailyReminderIdentifier, content: content, trigger: trigger)
    }

    func cancellationRequestIdentifiers() -> [String] {
        Self.reminderRequestIdentifiers
    }

    func cancelReminders(in center: UNUserNotificationCenter = .current()) {
        let identifiers = cancellationRequestIdentifiers()
        center.removePendingNotificationRequests(withIdentifiers: identifiers)
        center.removeDeliveredNotifications(withIdentifiers: identifiers)
    }

    func scheduleDailyReminder(
        hour: Int,
        minute: Int,
        title: String,
        body: String,
        in center: UNUserNotificationCenter = .current()
    ) async throws {
        cancelReminders(in: center)
        try await center.add(dailyReminderRequest(hour: hour, minute: minute, title: title, body: body))
    }
}
