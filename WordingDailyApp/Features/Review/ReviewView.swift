import SwiftUI

struct ReviewView: View {
    var body: some View {
        List {
            Section {
                HStack(alignment: .firstTextBaseline) {
                    Text("review.due.title")
                        .font(.headline)
                    Spacer()
                    Text("0")
                        .font(.title3.monospacedDigit())
                        .foregroundStyle(AppTheme.reviewAmber)
                }

                Button {
                } label: {
                    Label("review.start.button", systemImage: "arrow.triangle.2.circlepath")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
                .disabled(true)
            }

            Section {
                Text("review.empty.message")
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("review.title")
    }
}

#Preview {
    NavigationStack {
        ReviewView()
    }
}
