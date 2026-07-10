import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var preferences: UserPreferences
    private let preferencesStore: UserPreferencesStore
    private let calendar: Calendar

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
                Toggle("settings.reminders.toggle", isOn: $preferences.remindersEnabled)

                DatePicker(
                    "settings.reminders.time",
                    selection: reminderTimeBinding,
                    displayedComponents: .hourAndMinute
                )
                .disabled(!preferences.remindersEnabled)
            }

            Section {
                LabeledContent("settings.language.label", value: String(localized: "settings.language.system"))
            }
        }
        .navigationTitle("settings.title")
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

    private var reminderTimeBinding: Binding<Date> {
        Binding {
            preferences.reminderTimeDate(calendar: calendar)
        } set: { newDate in
            preferences.setReminderTime(newDate, calendar: calendar)
        }
    }
}

#Preview {
    NavigationStack {
        SettingsView()
    }
}
