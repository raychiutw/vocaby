import Charts
import SwiftData
import SwiftUI
import UIKit

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
    @Environment(\.modelContext) private var modelContext
    @Query private var sessions: [DailySession]
    @Query private var progressRows: [WordProgress]
    @Query private var attempts: [PracticeAttemptRecord]
    @Query private var achievementRecords: [AchievementRecord]
    @State private var rangeDays = 7
    @State private var celebrationStartedAt: Date?

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
        .overlay {
            if let celebrationStartedAt {
                ConfettiCanvas(startedAt: celebrationStartedAt)
                    .allowsHitTesting(false)
                    .accessibilityHidden(true)
            }
        }
        .task(id: achievementFingerprint) {
            unlockAchievementsIfNeeded()
        }
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
            AchievementWallView(unlockedIDs: unlockedAchievementIDs)
        } label: {
            Label("achievement.wall.title", systemImage: "medal")
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
    }

    private var achievementMetrics: AchievementMetrics {
        .make(progressRows: progressRows, sessions: sessions, attempts: attempts)
    }

    private var unlockedAchievementIDs: Set<AchievementID> {
        Set(achievementRecords.compactMap { AchievementID(rawValue: $0.achievementID) })
    }

    private var achievementFingerprint: String {
        [progressRows.count, sessions.count, attempts.count, achievementRecords.count]
            .map(String.init)
            .joined(separator: "-")
    }

    @MainActor
    private func unlockAchievementsIfNeeded() {
        let newlyUnlocked = AchievementEngine().newlyUnlocked(
            metrics: achievementMetrics,
            existing: unlockedAchievementIDs
        )
        guard !newlyUnlocked.isEmpty else { return }
        let now = Date()
        newlyUnlocked.forEach {
            modelContext.insert(AchievementRecord(achievementID: $0.rawValue, unlockedAt: now))
        }
        try? modelContext.save()
        celebrationStartedAt = now
        UINotificationFeedbackGenerator().notificationOccurred(.success)
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
    let unlockedIDs: Set<AchievementID>

    private var achievements: [(AchievementID, String, String)] {
        return [
            (.firstStudy, "achievement.first", "sparkles"),
            (.streak3, "achievement.streak3", "flame"),
            (.streak7, "achievement.streak7", "flame.fill"),
            (.streak30, "achievement.streak30", "calendar"),
            (.learn100, "achievement.learn100", "books.vertical"),
            (.learn500, "achievement.learn500", "books.vertical.fill"),
            (.master100, "achievement.master100", "checkmark.seal"),
            (.save10, "achievement.save10", "star.fill"),
            (.perfectPractice, "achievement.perfect", "trophy"),
            (.day50, "achievement.day50", "bolt.fill")
        ]
    }

    var body: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 140), spacing: 16)], spacing: 16) {
                ForEach(Array(achievements.enumerated()), id: \.offset) { _, achievement in
                    VStack(spacing: 12) {
                        Image(systemName: achievement.2)
                            .font(.largeTitle)
                            .foregroundStyle(unlockedIDs.contains(achievement.0) ? AppTheme.accent : .secondary)
                        Text(LocalizedStringKey(achievement.1))
                            .font(.subheadline.bold())
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity, minHeight: 130)
                    .padding()
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16))
                    .opacity(unlockedIDs.contains(achievement.0) ? 1 : 0.5)
                }
            }
            .padding()
        }
        .navigationTitle("achievement.wall.title")
    }
}

private struct ConfettiCanvas: View {
    let startedAt: Date

    var body: some View {
        TimelineView(.animation) { timeline in
            let elapsed = timeline.date.timeIntervalSince(startedAt)
            Canvas { context, size in
                guard elapsed < 3 else { return }
                for index in 0..<72 {
                    let seed = Double(index)
                    let progress = min(1, elapsed / 2.6)
                    let x = size.width * (0.08 + 0.84 * abs(sin(seed * 12.9898)))
                    let drift = sin(seed * 2.3 + elapsed * 4) * 28
                    let y = -20 + (size.height + 40) * progress * (0.45 + 0.55 * abs(cos(seed)))
                    let rect = CGRect(x: x + drift, y: y, width: 7, height: 12)
                    let colors: [Color] = [AppTheme.accent, .teal, .yellow, .pink, .orange]
                    context.fill(Path(roundedRect: rect, cornerRadius: 2), with: .color(colors[index % colors.count]))
                }
            }
            .opacity(max(0, 1 - elapsed / 3))
        }
        .ignoresSafeArea()
    }
}
