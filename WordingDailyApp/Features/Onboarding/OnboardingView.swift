import SwiftUI

struct OnboardingView: View {
    private enum Step {
        case welcome
        case level
        case reminder
    }

    let initialPreferences: UserPreferences
    let onComplete: (UserPreferences) -> Void
    private let calendar: Calendar

    @State private var step: Step = .welcome
    @State private var selectedLevel: VocabularyLevel?
    @State private var reminderTime: Date

    init(
        initialPreferences: UserPreferences = .defaults,
        calendar: Calendar = .current,
        onComplete: @escaping (UserPreferences) -> Void
    ) {
        self.initialPreferences = initialPreferences
        self.calendar = calendar
        self.onComplete = onComplete
        _selectedLevel = State(initialValue: nil)
        _reminderTime = State(initialValue: initialPreferences.reminderTimeDate(calendar: calendar))
    }

    var body: some View {
        NavigationStack {
            content
                .navigationTitle(navigationTitle)
                .toolbar(.hidden, for: .navigationBar)
        }
        .tint(AppTheme.accent)
    }

    @ViewBuilder
    private var content: some View {
        switch step {
        case .welcome:
            VStack(alignment: .leading, spacing: 24) {
                Spacer()
                Text("onboarding.welcome.title")
                    .font(.largeTitle.bold())
                Text("onboarding.welcome.message")
                    .font(.body)
                    .foregroundStyle(.secondary)
                Spacer()
                Button {
                    step = .level
                } label: {
                    Text("onboarding.continue")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            }
            .padding(24)
        case .level:
            Form {
                Section {
                    Picker("onboarding.level.title", selection: levelSelection) {
                        Text("settings.level.basic").tag(VocabularyLevel?.some(.basic))
                        Text("settings.level.intermediate").tag(VocabularyLevel?.some(.intermediate))
                        Text("settings.level.advanced").tag(VocabularyLevel?.some(.advanced))
                    }
                    .pickerStyle(.inline)
                } header: {
                    Text("onboarding.level.title")
                } footer: {
                    Text("onboarding.level.message")
                }

                Section {
                    Button("onboarding.level.continue") {
                        step = .reminder
                    }
                    .disabled(selectedLevel == nil)
                }
            }
        case .reminder:
            Form {
                Section {
                    DatePicker(
                        "settings.reminders.time",
                        selection: $reminderTime,
                        displayedComponents: .hourAndMinute
                    )
                } header: {
                    Text("onboarding.reminder.title")
                } footer: {
                    Text("onboarding.reminder.message")
                }

                Section {
                    Button("onboarding.reminder.enable") {
                        complete(remindersEnabled: true)
                    }
                    Button("onboarding.reminder.skip", role: .cancel) {
                        complete(remindersEnabled: false)
                    }
                }
            }
        }
    }

    private var navigationTitle: LocalizedStringKey {
        switch step {
        case .welcome:
            "onboarding.welcome.title"
        case .level:
            "onboarding.level.title"
        case .reminder:
            "onboarding.reminder.title"
        }
    }

    private var levelSelection: Binding<VocabularyLevel?> {
        Binding {
            selectedLevel
        } set: { newValue in
            selectedLevel = newValue
        }
    }

    private func complete(remindersEnabled: Bool) {
        var preferences = initialPreferences
        preferences.completeOnboarding(
            selectedLevel: selectedLevel ?? .basic,
            remindersEnabled: remindersEnabled,
            reminderTime: remindersEnabled ? reminderTime : nil,
            calendar: calendar
        )
        onComplete(preferences)
    }
}

#Preview {
    OnboardingView { _ in }
}
