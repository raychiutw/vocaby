import SwiftData
import SwiftUI

@main
struct WordingDailyApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
                .tint(AppTheme.accent)
                .modelContainer(for: [
                    WordProgress.self,
                    DailySession.self,
                    DailySessionItem.self,
                    QuizResult.self
                ])
        }
    }
}
