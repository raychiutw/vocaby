import SwiftUI
import WidgetKit

struct WordingDailyWidgetEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot
}

struct WordingDailyWidgetProvider: TimelineProvider {
    func placeholder(in context: Context) -> WordingDailyWidgetEntry {
        WordingDailyWidgetEntry(date: Date(), snapshot: .fallback(dayKey: Self.dayKey()))
    }

    func getSnapshot(in context: Context, completion: @escaping (WordingDailyWidgetEntry) -> Void) {
        completion(entry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<WordingDailyWidgetEntry>) -> Void) {
        let currentEntry = entry()
        let refreshDate = Calendar.current.date(byAdding: .minute, value: 30, to: currentEntry.date) ?? currentEntry.date
        completion(Timeline(entries: [currentEntry], policy: .after(refreshDate)))
    }

    private func entry() -> WordingDailyWidgetEntry {
        let date = Date()
        let dayKey = Self.dayKey(for: date)
        let snapshot = WidgetSnapshotWriter
            .appGroupWriter()?
            .snapshotOrFallback(dayKey: dayKey, generatedAt: date) ?? .fallback(dayKey: dayKey, generatedAt: date)

        return WordingDailyWidgetEntry(date: date, snapshot: snapshot)
    }

    private static func dayKey(for date: Date = Date()) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = .current
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
}

struct WordingDailyWidgetView: View {
    @Environment(\.widgetFamily) private var widgetFamily

    let entry: WordingDailyWidgetEntry

    var body: some View {
        switch widgetFamily {
        case .systemMedium:
            mediumLayout
        default:
            smallLayout
        }
    }

    private var smallLayout: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("widget.title")
                .font(.headline)
            Spacer()
            Text(progressText)
                .font(.title.monospacedDigit().weight(.semibold))
            Text("widget.today")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .containerBackground(.background, for: .widget)
        .widgetURL(URL(string: "wordingdaily://today"))
    }

    private var mediumLayout: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("widget.title")
                    .font(.headline)
                Spacer()
                Text(progressText)
                    .font(.headline.monospacedDigit())
                    .foregroundStyle(.secondary)
            }

            Spacer()

            if let expression = entry.snapshot.displayExpression {
                Text(expression.upgradedExpression)
                    .font(.title3.weight(.semibold))
                    .lineLimit(2)
                Text(expression.plainExpression)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            } else if entry.snapshot.progressTotal > 0,
                      entry.snapshot.progressCompleted >= entry.snapshot.progressTotal {
                Text("widget.completed")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                Text("widget.empty")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .containerBackground(.background, for: .widget)
        .widgetURL(URL(string: "wordingdaily://today"))
    }

    private var progressText: String {
        "\(entry.snapshot.progressCompleted)/\(entry.snapshot.progressTotal)"
    }
}

struct WordingDailyWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: WidgetSnapshotWriter.widgetKind, provider: WordingDailyWidgetProvider()) { entry in
            WordingDailyWidgetView(entry: entry)
        }
        .configurationDisplayName("widget.configuration.name")
        .description("widget.configuration.description")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

@main
struct WordingDailyWidgetBundle: WidgetBundle {
    var body: some Widget {
        WordingDailyWidget()
    }
}
