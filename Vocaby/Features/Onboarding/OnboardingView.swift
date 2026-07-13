import SwiftUI
import UserNotifications

struct OnboardingView: View {
    private enum Step {
        case welcome
        case level
        case reminder
    }

    let initialPreferences: UserPreferences
    let onComplete: (UserPreferences) -> Void
    private let calendar: Calendar
    private let notificationScheduler = NotificationScheduler()

    @State private var step: Step = .welcome
    @State private var selectedLevel: VocabularyLevel?
    @State private var reminderTime: Date
    @State private var isCompleting = false

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
                .prominentActionStyle()
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
                    .disabled(isCompleting)

                    Button("onboarding.reminder.skip", role: .cancel) {
                        complete(remindersEnabled: false)
                    }
                    .disabled(isCompleting)
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
        guard !isCompleting else { return }

        isCompleting = true
        var preferences = initialPreferences
        preferences.completeOnboarding(
            selectedLevel: selectedLevel ?? .basic,
            remindersEnabled: remindersEnabled,
            reminderTime: remindersEnabled ? reminderTime : nil,
            calendar: calendar
        )

        Task {
            let updatedPreferences = await applyReminderPreference(preferences)

            await MainActor.run {
                isCompleting = false
                onComplete(updatedPreferences)
            }
        }
    }

    private func applyReminderPreference(_ preferences: UserPreferences) async -> UserPreferences {
        var updatedPreferences = preferences
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        let title = String(localized: "notifications.daily.title")
        let body = String(localized: "notifications.daily.body")
        var plan = notificationScheduler.dailyReminderPlan(
            for: updatedPreferences,
            authorizationStatus: ReminderAuthorizationStatus(settings.authorizationStatus),
            title: title,
            body: body
        )

        if plan == .requestAuthorization {
            let granted = (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
            plan = notificationScheduler.dailyReminderPlan(
                for: updatedPreferences,
                authorizationStatus: granted ? .authorized : .denied,
                title: title,
                body: body
            )
        }

        switch plan {
        case .cancel:
            updatedPreferences.remindersEnabled = false
            notificationScheduler.cancelReminders(in: center)
        case let .schedule(hour, minute, title, body):
            try? await notificationScheduler.scheduleDailyReminder(
                hour: hour,
                minute: minute,
                title: title,
                body: body,
                in: center
            )
        case .requestAuthorization:
            break
        }

        return updatedPreferences
    }
}

#Preview {
    OnboardingView { _ in }
}
