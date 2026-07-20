import Charts
import SwiftData
import SwiftUI

private struct LearningDay: Identifiable {
    let date: Date
    let count: Int
    var id: Date { date }
}

private struct LearningStateSlice: Identifiable {
    let name: String
    let count: Int
    var id: String { String(describing: name) }
}

struct LearningProgressView: View {
    @Query private var sessions: [DailySession]
    @Query private var progressRows: [WordProgress]
    @State private var rangeDays = 7

    private let dayKeyService = DayKeyService()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                Picker("progress.range.accessibility", selection: $rangeDays) {
                    Text("progress.range.7").tag(7)
                    Text("progress.range.30").tag(30)
                }
                .pickerStyle(.segmented)

                if progressRows.isEmpty && sessions.isEmpty {
                    ContentUnavailableView(
                        "progress.empty.title",
                        systemImage: "chart.xyaxis.line",
                        description: Text("progress.empty.description")
                    )
                } else {
                    trendSection
                    heatmapSection
                    distributionSection
                    achievementPreview
                }
            }
            .frame(maxWidth: 640)
            .padding()
            .frame(maxWidth: .infinity)
        }
        .navigationTitle("progress.title")
    }

    private var trendSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("progress.trend.title").font(.headline)
            Chart(trendDays) { day in
                AreaMark(
                    x: .value("Date", day.date),
                    y: .value("Learned", day.count)
                )
                .foregroundStyle(brandGradient.opacity(0.22))
                LineMark(
                    x: .value("Date", day.date),
                    y: .value("Learned", day.count)
                )
                .foregroundStyle(brandGradient)
                .interpolationMethod(.catmullRom)
            }
            .frame(height: 220)
            .accessibilityLabel(Text("progress.trend.accessibility"))
            .accessibilityValue(Text(trendAccessibilityValue))
        }
    }

    private var heatmapSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("progress.heatmap.title").font(.headline)
            ScrollView(.horizontal) {
                LazyHGrid(rows: Array(repeating: GridItem(.fixed(15), spacing: 4), count: 7), spacing: 4) {
                    ForEach(heatmapDays) { day in
                        RoundedRectangle(cornerRadius: 3)
                            .fill(heatmapColor(day.count))
                            .frame(width: 15, height: 15)
                            .overlay {
                                if Calendar.current.isDateInToday(day.date) {
                                    RoundedRectangle(cornerRadius: 3)
                                        .stroke(.primary, lineWidth: 1.5)
                                }
                            }
                            .accessibilityLabel(Text(day.date.formatted(date: .abbreviated, time: .omitted)))
                            .accessibilityValue(Text("\(day.count)"))
                    }
                }
            }
            .defaultScrollAnchor(.trailing)
        }
    }

    private var distributionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("progress.distribution.title").font(.headline)
            Chart(distribution) { slice in
                SectorMark(
                    angle: .value("Count", slice.count),
                    innerRadius: .ratio(0.58),
                    angularInset: 2
                )
                .foregroundStyle(by: .value("State", String(localized: String.LocalizationValue(slice.name))))
            }
            .frame(height: 220)
            .accessibilityLabel(Text("progress.distribution.accessibility"))
            .accessibilityValue(Text(distributionAccessibilityValue))
        }
    }

    private var achievementPreview: some View {
        NavigationLink {
            AchievementWallView(progressRows: progressRows, sessions: sessions)
        } label: {
            Label("achievement.wall.title", systemImage: "medal")
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
    }

    private var trendDays: [LearningDay] {
        days(endingAt: Date(), count: rangeDays)
    }

    private var heatmapDays: [LearningDay] {
        days(endingAt: Date(), count: 15 * 7)
    }

    private func days(endingAt date: Date, count: Int) -> [LearningDay] {
        let calendar = Calendar.current
        let end = calendar.startOfDay(for: date)
        let sessionCounts = Dictionary(uniqueKeysWithValues: sessions.map { ($0.dayKey, $0.completedItemCount) })
        return (0..<count).compactMap { offset in
            guard let day = calendar.date(byAdding: .day, value: offset - count + 1, to: end) else { return nil }
            return LearningDay(date: day, count: sessionCounts[dayKeyService.dayKey(for: day)] ?? 0)
        }
    }

    private var distribution: [LearningStateSlice] {
        let mastered = progressRows.filter { $0.masteredAt != nil }.count
        let learning = progressRows.filter { $0.firstSeenAt != nil && $0.masteredAt == nil }.count
        let new = progressRows.filter { $0.firstSeenAt == nil }.count
        return [
            LearningStateSlice(name: "progress.state.new", count: new),
            LearningStateSlice(name: "progress.state.learning", count: learning),
            LearningStateSlice(name: "progress.state.mastered", count: mastered)
        ]
    }

    private var trendAccessibilityValue: String {
        trendDays.map { "\($0.date.formatted(date: .numeric, time: .omitted)): \($0.count)" }.joined(separator: ", ")
    }

    private var distributionAccessibilityValue: String {
        distribution.map { "\(String(localized: String.LocalizationValue($0.name))): \($0.count)" }.joined(separator: ", ")
    }

    private func heatmapColor(_ count: Int) -> Color {
        switch count {
        case 0: Color(.tertiarySystemFill)
        case 1...4: AppTheme.accent.opacity(0.25)
        case 5...9: AppTheme.accent.opacity(0.45)
        case 10...19: AppTheme.accent.opacity(0.7)
        default: AppTheme.accent
        }
    }

    private var brandGradient: LinearGradient {
        LinearGradient(colors: [AppTheme.accent, Color(red: 0.08, green: 0.72, blue: 0.65)], startPoint: .leading, endPoint: .trailing)
    }
}

private struct AchievementWallView: View {
    let progressRows: [WordProgress]
    let sessions: [DailySession]

    private var achievements: [(String, String, Bool)] {
        let learned = progressRows.filter { $0.firstSeenAt != nil }.count
        let mastered = progressRows.filter { $0.masteredAt != nil }.count
        let saved = progressRows.filter(\.isSaved).count
        let maximumDay = sessions.map(\.completedItemCount).max() ?? 0
        return [
            ("achievement.first", "sparkles", learned >= 1),
            ("achievement.streak3", "flame", sessions.count >= 3),
            ("achievement.streak7", "flame.fill", sessions.count >= 7),
            ("achievement.streak30", "calendar", sessions.count >= 30),
            ("achievement.learn100", "books.vertical", learned >= 100),
            ("achievement.learn500", "books.vertical.fill", learned >= 500),
            ("achievement.master100", "checkmark.seal", mastered >= 100),
            ("achievement.save10", "star.fill", saved >= 10),
            ("achievement.perfect", "trophy", false),
            ("achievement.day50", "bolt.fill", maximumDay >= 50)
        ]
    }

    var body: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 140), spacing: 16)], spacing: 16) {
                ForEach(Array(achievements.enumerated()), id: \.offset) { _, achievement in
                    VStack(spacing: 12) {
                        Image(systemName: achievement.1)
                            .font(.largeTitle)
                            .foregroundStyle(achievement.2 ? AppTheme.accent : .secondary)
                        Text(LocalizedStringKey(achievement.0))
                            .font(.subheadline.bold())
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity, minHeight: 130)
                    .padding()
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
                    .opacity(achievement.2 ? 1 : 0.5)
                }
            }
            .padding()
        }
        .navigationTitle("achievement.wall.title")
    }
}
