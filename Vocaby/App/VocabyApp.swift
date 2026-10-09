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

    private let clock = Vocaby.launchClock()

    private static func launchClock() -> AppClock {
        #if DEBUG
        // UI test 以 `-VOCABY_FIXED_NOW 2026-07-10T09:00:00+08:00` 固定「現在」;Release 不含此鉤子。
        // 值存在卻無法解析時直接失敗,免得測試默默改用真實時間而變成每天不同。
        if let value = UserDefaults.standard.string(forKey: "VOCABY_FIXED_NOW") {
            guard let clock = AppClock.fixed(fromLaunchValue: value) else {
                fatalError("VOCABY_FIXED_NOW 必須是含時區的 ISO 8601,例如 2026-07-10T09:00:00+08:00,收到:\(value)")
            }
            return clock
        }
        #endif
        return .system
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
