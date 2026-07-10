import Foundation

enum StreakRelationship: Equatable {
    case firstDay
    case sameDay
    case continues
    case missed
    case backwardDate
    case invalidDate
}

struct DayKeyService {
    private let calendar: Calendar

    init(calendar: Calendar = .autoupdatingCurrent) {
        self.calendar = calendar
    }

    func dayKey(for date: Date) -> String {
        let components = calendar.dateComponents([.year, .month, .day], from: date)
        return String(
            format: "%04d-%02d-%02d",
            components.year ?? 0,
            components.month ?? 0,
            components.day ?? 0
        )
    }

    func date(for dayKey: String) -> Date? {
        let parts = dayKey.split(separator: "-")
        guard parts.count == 3,
              let year = Int(parts[0]),
              let month = Int(parts[1]),
              let day = Int(parts[2]) else {
            return nil
        }

        var components = DateComponents()
        components.calendar = calendar
        components.timeZone = calendar.timeZone
        components.year = year
        components.month = month
        components.day = day
        return calendar.date(from: components)
    }

    func daysBetween(previousDayKey: String, currentDayKey: String) -> Int? {
        guard let previousDate = date(for: previousDayKey),
              let currentDate = date(for: currentDayKey) else {
            return nil
        }

        let previousStart = calendar.startOfDay(for: previousDate)
        let currentStart = calendar.startOfDay(for: currentDate)
        return calendar.dateComponents([.day], from: previousStart, to: currentStart).day
    }

    func streakRelationship(previousCompletedDayKey: String?, currentDayKey: String) -> StreakRelationship {
        guard let previousCompletedDayKey else {
            return .firstDay
        }

        guard let distance = daysBetween(previousDayKey: previousCompletedDayKey, currentDayKey: currentDayKey) else {
            return .invalidDate
        }

        switch distance {
        case ..<0:
            return .backwardDate
        case 0:
            return .sameDay
        case 1:
            return .continues
        default:
            return .missed
        }
    }
}
