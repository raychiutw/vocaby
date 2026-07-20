import AVFAudio
import SwiftData
import SwiftUI
import UIKit

enum LearnGrade: Int {
    case unknown = 1
    case saved = 4
    case known = 5

    var systemImage: String {
        switch self {
        case .unknown: "xmark"
        case .saved: "star.fill"
        case .known: "checkmark"
        }
    }
}

struct LearnView: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.modelContext) private var modelContext
    @State private var items: [VocabularySeedItem] = []
    @State private var currentIndex = 0
    @State private var isRevealed = false
    @State private var dragOffset: CGSize = .zero
    @State private var knownCount = 0
    @State private var unknownCount = 0
    @State private var savedCount = 0
    @State private var errorMessage: String?
    @State private var synthesizer = AVSpeechSynthesizer()

    private let seedLoader = SeedLoader()
    private let persistence = ProgressPersistenceService()
    private let scheduler = ReviewScheduler()
    private let preferencesStore = UserPreferencesStore()
    private let swipeThreshold: CGFloat = 96

    private var currentItem: VocabularySeedItem? {
        items.indices.contains(currentIndex) ? items[currentIndex] : nil
    }

    var body: some View {
        Group {
            if let item = currentItem {
                VStack(spacing: 24) {
                    ProgressView(value: Double(currentIndex), total: Double(max(items.count, 1)))
                        .accessibilityLabel(Text("learn.progress.accessibility"))
                        .accessibilityValue(Text("\(currentIndex + 1)/\(items.count)"))

                    LearnCardView(
                        item: item,
                        isRevealed: isRevealed,
                        dragOffset: dragOffset,
                        reduceMotion: reduceMotion,
                        synthesizer: synthesizer
                    )
                    .onTapGesture { flipCard() }
                    .gesture(cardDragGesture)
                    .accessibilityAction(named: Text(isRevealed ? "learn.card.hide" : "learn.card.reveal")) {
                        flipCard()
                    }

                    HStack(spacing: 32) {
                        gradeButton(.unknown, tint: AppTheme.wrongRed, label: "learn.grade.unknown")
                        gradeButton(.saved, tint: AppTheme.accent, label: "learn.grade.saved")
                        gradeButton(.known, tint: AppTheme.correctGreen, label: "learn.grade.known")
                    }
                }
                .padding()
            } else if !items.isEmpty {
                LearnRoundSummaryView(
                    knownCount: knownCount,
                    savedCount: savedCount,
                    unknownCount: unknownCount,
                    restart: restart
                )
            } else if let errorMessage {
                ContentUnavailableView(
                    "learn.error.title",
                    systemImage: "exclamationmark.triangle",
                    description: Text(errorMessage)
                )
            } else {
                ProgressView("learn.loading")
            }
        }
        .navigationTitle("learn.title")
        .task { loadItems() }
    }

    private var cardDragGesture: some Gesture {
        DragGesture(minimumDistance: 12)
            .onChanged { dragOffset = $0.translation }
            .onEnded { value in
                if value.translation.height < -swipeThreshold,
                   abs(value.translation.height) > abs(value.translation.width) {
                    commit(.saved)
                } else if value.translation.width > swipeThreshold {
                    commit(.known)
                } else if value.translation.width < -swipeThreshold {
                    commit(.unknown)
                } else {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.75)) {
                        dragOffset = .zero
                    }
                }
            }
    }

    private func gradeButton(_ grade: LearnGrade, tint: Color, label: LocalizedStringKey) -> some View {
        Button { commit(grade) } label: {
            Image(systemName: grade.systemImage)
                .font(.title2.bold())
                .frame(width: 56, height: 56)
                .foregroundStyle(tint)
                .background(.thinMaterial, in: Circle())
        }
        .accessibilityLabel(Text(label))
    }

    private func flipCard() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        withAnimation(reduceMotion ? .easeInOut(duration: 0.15) : .spring(response: 0.45, dampingFraction: 0.78)) {
            isRevealed.toggle()
        }
    }

    private func commit(_ grade: LearnGrade) {
        guard let item = currentItem else { return }

        do {
            let progress = try persistence.wordProgress(for: item.id, level: item.level, in: modelContext)
            if grade == .saved {
                progress.isSaved = true
                savedCount += 1
            }
            scheduler.applyAnswer(
                to: progress,
                quality: grade.rawValue,
                answeredAt: Date(),
                context: .dailyPractice
            )
            try modelContext.save()

            if grade == .unknown { unknownCount += 1 } else { knownCount += 1 }
            feedback(for: grade)
            let destination = CGSize(
                width: grade == .unknown ? -500 : grade == .known ? 500 : 0,
                height: grade == .saved ? -700 : dragOffset.height
            )
            withAnimation(reduceMotion ? .easeOut(duration: 0.12) : .spring(response: 0.32, dampingFraction: 0.82)) {
                dragOffset = destination
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + (reduceMotion ? 0.12 : 0.28)) {
                currentIndex += 1
                isRevealed = false
                dragOffset = .zero
                autoplayIfNeeded()
            }
        } catch {
            errorMessage = String(localized: "learn.error.save")
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    private func loadItems() {
        do {
            let preferences = preferencesStore.read()
            items = Array(try seedLoader.loadBundledSeed()
                .filter { $0.level == preferences.selectedLevel }
                .prefix(min(preferences.dailyGoal, 10)))
            autoplayIfNeeded()
        } catch {
            errorMessage = String(localized: "learn.error.load")
        }
    }

    private func restart() {
        currentIndex = 0
        knownCount = 0
        unknownCount = 0
        savedCount = 0
        autoplayIfNeeded()
    }

    private func autoplayIfNeeded() {
        guard preferencesStore.read().autoplayPronunciation,
              let item = currentItem,
              let pronunciation = item.pronunciations.first else { return }
        synthesizer.speak(PronunciationSpeaker.makeUtterance(
            expression: item.upgradedExpression,
            pronunciation: pronunciation
        ))
    }

    private func feedback(for grade: LearnGrade) {
        switch grade {
        case .unknown:
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        case .saved:
            UISelectionFeedbackGenerator().selectionChanged()
        case .known:
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        }
    }
}

private struct LearnCardView: View {
    let item: VocabularySeedItem
    let isRevealed: Bool
    let dragOffset: CGSize
    let reduceMotion: Bool
    let synthesizer: AVSpeechSynthesizer

    private var horizontalProgress: CGFloat { min(1, abs(dragOffset.width) / 120) }
    private var verticalProgress: CGFloat { min(1, max(0, -dragOffset.height) / 120) }

    var body: some View {
        ZStack {
            cardFace(front: true)
                .opacity(isRevealed ? 0 : 1)
                .rotation3DEffect(.degrees(isRevealed && !reduceMotion ? 180 : 0), axis: (x: 0, y: 1, z: 0))
            cardFace(front: false)
                .opacity(isRevealed ? 1 : 0)
                .rotation3DEffect(.degrees(isRevealed || reduceMotion ? 0 : -180), axis: (x: 0, y: 1, z: 0))
        }
        .frame(maxWidth: .infinity, minHeight: 390)
        .background(cardTint, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(alignment: stampAlignment) { stamp }
        .offset(dragOffset)
        .rotationEffect(reduceMotion ? .zero : .degrees(Double(dragOffset.width / 24)))
        .accessibilityElement(children: .contain)
    }

    @ViewBuilder
    private func cardFace(front: Bool) -> some View {
        VStack(spacing: 18) {
            if front {
                Text(verbatim: item.upgradedExpression)
                    .font(.largeTitle.bold())
                    .multilineTextAlignment(.center)
                if let pronunciation = item.pronunciations.first {
                    Button {
                        synthesizer.speak(PronunciationSpeaker.makeUtterance(
                            expression: item.upgradedExpression,
                            pronunciation: pronunciation
                        ))
                    } label: {
                        Label("/\(pronunciation.ipa)/", systemImage: "speaker.wave.2")
                            .frame(minHeight: 44)
                    }
                    .accessibilityLabel(Text("learn.pronounce"))
                }
                Text("learn.card.tap")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            } else {
                Text(verbatim: item.primarySense.meaning["zh-Hant"] ?? item.primarySense.meaning["en"] ?? "")
                    .font(.title2.bold())
                    .multilineTextAlignment(.center)
                Text(verbatim: item.plainExpression)
                    .foregroundStyle(.secondary)
                Divider()
                Text(verbatim: item.primarySense.example.text)
                Text(verbatim: item.primarySense.example.translation["zh-Hant"] ?? "")
                    .foregroundStyle(.secondary)
            }
        }
        .padding(24)
    }

    private var cardTint: some ShapeStyle {
        LinearGradient(
            colors: [Color(.secondarySystemGroupedBackground), semanticTint.opacity(0.22)],
            startPoint: .top,
            endPoint: .bottomTrailing
        )
    }

    private var semanticTint: Color {
        if verticalProgress > horizontalProgress { return AppTheme.accent }
        if dragOffset.width < 0 { return AppTheme.wrongRed }
        if dragOffset.width > 0 { return AppTheme.correctGreen }
        return .clear
    }

    private var stampAlignment: Alignment {
        verticalProgress > horizontalProgress ? .top : dragOffset.width < 0 ? .topTrailing : .topLeading
    }

    @ViewBuilder
    private var stamp: some View {
        if max(horizontalProgress, verticalProgress) > 0.35 {
            Label(stampKey, systemImage: stampImage)
                .font(.headline.bold())
                .foregroundStyle(semanticTint)
                .padding(12)
                .background(.regularMaterial, in: Capsule())
                .padding()
                .rotationEffect(.degrees(dragOffset.width < 0 ? 10 : -10))
        }
    }

    private var stampKey: LocalizedStringKey {
        if verticalProgress > horizontalProgress { return "learn.grade.saved" }
        return dragOffset.width < 0 ? "learn.grade.unknown" : "learn.grade.known"
    }

    private var stampImage: String {
        if verticalProgress > horizontalProgress { return "star.fill" }
        return dragOffset.width < 0 ? "xmark" : "checkmark"
    }
}

private struct LearnRoundSummaryView: View {
    let knownCount: Int
    let savedCount: Int
    let unknownCount: Int
    let restart: () -> Void

    private var total: Int { knownCount + unknownCount }

    var body: some View {
        VStack(spacing: 24) {
            Gauge(value: Double(knownCount), in: 0...Double(max(total, 1))) {
                Text("learn.summary.rate")
            } currentValueLabel: {
                Text("\(Int(Double(knownCount) / Double(max(total, 1)) * 100))%")
                    .monospacedDigit()
            }
            .gaugeStyle(.accessoryCircularCapacity)
            .scaleEffect(1.8)
            .padding(40)

            HStack {
                summary("learn.grade.known", knownCount)
                summary("learn.grade.saved", savedCount)
                summary("learn.grade.unknown", unknownCount)
            }

            Button("learn.summary.again", action: restart)
                .buttonStyle(.borderedProminent)
        }
        .padding()
        .navigationTitle("learn.summary.title")
    }

    private func summary(_ key: LocalizedStringKey, _ value: Int) -> some View {
        VStack {
            Text("\(value)").font(.title2.bold()).monospacedDigit()
            Text(key).font(.footnote).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}
