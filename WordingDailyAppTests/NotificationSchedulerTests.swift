import UserNotifications
import XCTest
@testable import WordingDailyApp

final class NotificationSchedulerTests: XCTestCase {
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
}
