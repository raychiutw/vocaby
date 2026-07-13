import SwiftUI
import UIKit
import UserNotifications

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @State private var preferences: UserPreferences
    @State private var authorizationStatus: ReminderAuthorizationStatus = .notDetermined
    @State private var isUpdatingReminders = false
    private let preferencesStore: UserPreferencesStore
    private let calendar: Calendar
    private let notificationScheduler = NotificationScheduler()

    init(
        preferencesStore: UserPreferencesStore = UserPreferencesStore(),
        calendar: Calendar = .current
    ) {
        self.preferencesStore = preferencesStore
        self.calendar = calendar
        _preferences = State(initialValue: preferencesStore.read())
    }

    var body: some View {
        Form {
            Section {
                Picker("settings.level.label", selection: $preferences.selectedLevel) {
                    Text("settings.level.basic").tag(VocabularyLevel.basic)
                    Text("settings.level.intermediate").tag(VocabularyLevel.intermediate)
                    Text("settings.level.advanced").tag(VocabularyLevel.advanced)
                }
                .pickerStyle(.navigationLink)
            }

            Section {
                Toggle("settings.reminders.toggle", isOn: remindersEnabledBinding)
                    .disabled(isUpdatingReminders)

                DatePicker(
                    "settings.reminders.time",
                    selection: reminderTimeBinding,
                    displayedComponents: .hourAndMinute
                )
                .disabled(!preferences.remindersEnabled || isUpdatingReminders)

                if authorizationStatus == .denied {
                    Button("settings.reminders.openSettings") {
                        openAppSettings()
                    }
                }
            } footer: {
                if authorizationStatus == .denied {
                    Text("settings.reminders.denied.message")
                }
            }

            Section {
                Button {
                    openAppSettings()
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("settings.language.label")
                                .foregroundStyle(.primary)

                            Text("settings.language.openSettingsHint")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        Image(systemName: "chevron.right")
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(.tertiary)
                            .accessibilityHidden(true)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }

            Section {
                NavigationLink("settings.sources.row") {
                    ThirdPartyNoticesView()
                }
            }
        }
        .navigationTitle("settings.title")
        .task {
            await refreshAuthorizationStatus()
        }
        .onChange(of: preferences) { _, newValue in
            try? preferencesStore.write(newValue)
        }
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("common.done") {
                    dismiss()
                }
            }
        }
    }

    private var remindersEnabledBinding: Binding<Bool> {
        Binding {
            preferences.remindersEnabled
        } set: { isEnabled in
            preferences.remindersEnabled = isEnabled
            applyReminderPreference()
        }
    }

    private var reminderTimeBinding: Binding<Date> {
        Binding {
            preferences.reminderTimeDate(calendar: calendar)
        } set: { newDate in
            preferences.setReminderTime(newDate, calendar: calendar)
            if preferences.remindersEnabled {
                applyReminderPreference()
            }
        }
    }

    private func refreshAuthorizationStatus() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()

        await MainActor.run {
            authorizationStatus = ReminderAuthorizationStatus(settings.authorizationStatus)
        }
    }

    private func applyReminderPreference() {
        isUpdatingReminders = true
        let currentPreferences = preferences

        Task {
            let center = UNUserNotificationCenter.current()
            let title = String(localized: "notifications.daily.title")
            let body = String(localized: "notifications.daily.body")
            var updatedPreferences = currentPreferences
            let settings = await center.notificationSettings()
            var currentStatus = ReminderAuthorizationStatus(settings.authorizationStatus)
            var plan = notificationScheduler.dailyReminderPlan(
                for: updatedPreferences,
                authorizationStatus: currentStatus,
                title: title,
                body: body
            )

            if plan == .requestAuthorization {
                let granted = (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
                currentStatus = granted ? .authorized : .denied
                plan = notificationScheduler.dailyReminderPlan(
                    for: updatedPreferences,
                    authorizationStatus: currentStatus,
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

            await MainActor.run {
                preferences.reminderHour = updatedPreferences.reminderHour
                preferences.reminderMinute = updatedPreferences.reminderMinute
                preferences.remindersEnabled = updatedPreferences.remindersEnabled
                authorizationStatus = currentStatus
                isUpdatingReminders = false
                try? preferencesStore.write(preferences)
            }
        }
    }

    private func openAppSettings() {
        guard let settingsURL = URL(string: UIApplication.openSettingsURLString) else {
            return
        }

        openURL(settingsURL)
    }
}

struct ThirdPartyNoticesView: View {
    private let notices: String

    init(bundle: Bundle = .main) {
        if let url = bundle.url(forResource: "ThirdPartyNotices", withExtension: "txt"),
           let text = try? String(contentsOf: url, encoding: .utf8),
           !text.isEmpty {
            notices = text
        } else {
            notices = String(localized: "settings.sources.unavailable")
        }
    }

    var body: some View {
        ScrollView {
            Text(notices)
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
                .padding()
        }
        .navigationTitle("settings.sources.title")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationStack {
        SettingsView()
    }
}
