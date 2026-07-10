import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var remindersEnabled = false
    @State private var reminderTime = Calendar.current.date(from: DateComponents(hour: 8, minute: 30)) ?? Date()

    var body: some View {
        Form {
            Section {
                Toggle("settings.reminders.toggle", isOn: $remindersEnabled)

                DatePicker(
                    "settings.reminders.time",
                    selection: $reminderTime,
                    displayedComponents: .hourAndMinute
                )
                .disabled(!remindersEnabled)
            }

            Section {
                LabeledContent("settings.language.label", value: String(localized: "settings.language.system"))
            }
        }
        .navigationTitle("settings.title")
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("common.done") {
                    dismiss()
                }
            }
        }
    }
}

#Preview {
    NavigationStack {
        SettingsView()
    }
}
