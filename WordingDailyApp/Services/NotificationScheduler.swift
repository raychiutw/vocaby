import Foundation
import UserNotifications

struct NotificationScheduler {
    static let dailyReminderIdentifier = "wording-daily.daily-reminder"
    static let reminderRequestIdentifiers = [dailyReminderIdentifier]

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
