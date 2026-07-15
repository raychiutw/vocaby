import SwiftUI

private struct LearningSettingsSheet: ViewModifier {
    @State private var isShowingSettings = false

    func body(content: Content) -> some View {
        content
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        isShowingSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                    .accessibilityLabel(Text("learning.profile.accessibility"))
                }
            }
            .sheet(isPresented: $isShowingSettings) {
                NavigationStack {
                    SettingsView()
                }
            }
    }
}

extension View {
    func minimumInteractiveSize() -> some View {
        frame(minWidth: 44, minHeight: 44)
            .contentShape(Rectangle())
    }

    func learningSettingsSheet() -> some View {
        modifier(LearningSettingsSheet())
    }

    @ViewBuilder
    func prominentActionStyle(tint: Color = AppTheme.accent) -> some View {
        if #available(iOS 26.0, *) {
            self
                .buttonStyle(.glassProminent)
                .tint(tint)
                .foregroundStyle(AppTheme.prominentInk)
        } else {
            self
                .buttonStyle(.borderedProminent)
                .tint(tint)
                .foregroundStyle(AppTheme.prominentInk)
        }
    }

    @ViewBuilder
    func bottomActionChrome() -> some View {
        if #available(iOS 26.0, *) {
            self
        } else {
            self.background(.regularMaterial)
        }
    }
}

struct CompactMetadataRow: View {
    let title: String
    let subtitle: String
    let systemImage: String
    let tint: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: systemImage)
                .font(.title3)
                .foregroundStyle(tint)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.body.weight(.medium))
                    .foregroundStyle(.primary)

                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}
