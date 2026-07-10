import SwiftUI

struct TodayView: View {
    @State private var isShowingSettings = false

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(alignment: .firstTextBaseline) {
                        Text("today.progress.title")
                            .font(.headline)
                        Spacer()
                        Text("0/10")
                            .font(.headline.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }

                    ProgressView(value: 0, total: 10)
                        .tint(AppTheme.accent)
                        .accessibilityLabel(Text("today.progress.accessibility"))
                        .accessibilityValue(Text("0/10"))

                    Button {
                    } label: {
                        Label("today.start.button", systemImage: "play.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .tint(AppTheme.accent)
                    .accessibilityIdentifier("today.start")
                }
                .padding(.vertical, 8)
            }

            Section {
                LabeledContent("today.due.label", value: "0")
                LabeledContent("today.preview.label", value: String(localized: "today.preview.empty"))
            }
        }
        .navigationTitle("today.title")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    isShowingSettings = true
                } label: {
                    Image(systemName: "gearshape")
                }
                .accessibilityLabel(Text("settings.title"))
            }
        }
        .sheet(isPresented: $isShowingSettings) {
            NavigationStack {
                SettingsView()
            }
        }
    }
}

#Preview {
    NavigationStack {
        TodayView()
    }
}
