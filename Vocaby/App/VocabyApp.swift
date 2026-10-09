import SwiftData
import SwiftUI
import UIKit
import UserNotifications

extension Notification.Name {
    static let vocabyInternalURL = Notification.Name("vocaby.internal-url")
}

final class VocabyDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
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
            NotificationCenter.default.post(name: .vocabyInternalURL, object: url)
        }
    }
}

@main
struct Vocaby: App {
    @UIApplicationDelegateAdaptor(VocabyDelegate.self) private var appDelegate

    private var clock: AppClock {
        #if DEBUG
        // UI test 以 `-VOCABY_FIXED_NOW 2026-07-10T09:00:00+08:00` 固定「現在」;Release 不含此鉤子。
        AppClock.fixed(fromLaunchValue: UserDefaults.standard.string(forKey: "VOCABY_FIXED_NOW")) ?? .system
        #else
        .system
        #endif
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(\.appClock, clock)
                .tint(AppTheme.accent)
                .modelContainer(for: [
                    WordProgress.self,
                    DailySession.self,
                    DailySessionItem.self,
                    QuizResult.self,
                    PracticeAttemptRecord.self,
                    AchievementRecord.self
                ])
        }
    }
}
