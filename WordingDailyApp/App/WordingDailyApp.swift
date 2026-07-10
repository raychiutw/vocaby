import SwiftUI

@main
struct WordingDailyApp: App {
    var body: some Scene {
        WindowGroup {
            RootTabView()
                .tint(AppTheme.accent)
        }
    }
}
