import SwiftData
import SwiftUI
import UIKit
import UserNotifications

extension Notification.Name {
    static let wordingDailyInternalURL = Notification.Name("wording-daily.internal-url")
}

final class WordingDailyAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        defer { completionHandler() }

        let request = response.notification.request
        guard
            request.identifier == NotificationScheduler.dailyReminderIdentifier,
            let value = request.content.userInfo[NotificationScheduler.deepLinkUserInfoKey] as? String,
            let url = URL(string: value),
            url == NotificationScheduler.dailyReminderURL
        else {
            return
        }

        DispatchQueue.main.async {
            NotificationCenter.default.post(name: .wordingDailyInternalURL, object: url)
        }
    }
}

@main
struct WordingDailyApp: App {
    @UIApplicationDelegateAdaptor(WordingDailyAppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup {
            RootView()
                .tint(AppTheme.accent)
                .modelContainer(for: [
                    WordProgress.self,
                    DailySession.self,
                    DailySessionItem.self,
                    QuizResult.self,
                    PracticeAttemptRecord.self
                ])
        }
    }
}
