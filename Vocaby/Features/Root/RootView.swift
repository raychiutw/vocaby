import SwiftUI

struct RootView: View {
    @State private var preferences: UserPreferences
    private let preferencesStore: UserPreferencesStore

    init(preferencesStore: UserPreferencesStore = UserPreferencesStore()) {
        self.preferencesStore = preferencesStore
        _preferences = State(initialValue: preferencesStore.read())
    }

    var body: some View {
        Group {
            if preferences.onboardingCompleted {
                RootTabView()
            } else {
                OnboardingView(initialPreferences: preferences) { updatedPreferences in
                    preferences = updatedPreferences
                    try? preferencesStore.write(updatedPreferences)
                }
            }
        }
        .preferredColorScheme(preferredColorScheme)
        .onReceive(NotificationCenter.default.publisher(for: .vocabyPreferencesDidChange)) { _ in
            preferences = preferencesStore.read()
        }
    }

    private var preferredColorScheme: ColorScheme? {
        switch preferences.appearance {
        case .system: nil
        case .light: .light
        case .dark: .dark
        }
    }
}

#Preview {
    RootView()
}
