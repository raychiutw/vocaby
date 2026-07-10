import Foundation
import XCTest

final class LocalizationCoverageTests: XCTestCase {
    func testAllStringsHaveEnglishAndTraditionalChineseTranslations() throws {
        let catalog = try loadCatalog()

        XCTAssertEqual(catalog.sourceLanguage, "en")

        for (key, value) in catalog.strings {
            let english = value.localizations["en"]?.stringUnit.value.trimmingCharacters(in: .whitespacesAndNewlines)
            let traditionalChinese = value.localizations["zh-Hant"]?.stringUnit.value.trimmingCharacters(in: .whitespacesAndNewlines)

            XCTAssertFalse(english?.isEmpty ?? true, "\(key) is missing an English translation")
            XCTAssertFalse(traditionalChinese?.isEmpty ?? true, "\(key) is missing a zh-Hant translation")
        }
    }

    func testHighRiskStringsStayWithinLayoutBudgets() throws {
        let catalog = try loadCatalog()
        let budgets: [String: StringBudget] = [
            "today.tab.title": .init(en: 8, zhHant: 4),
            "review.tab.title": .init(en: 8, zhHant: 4),
            "library.tab.title": .init(en: 8, zhHant: 4),
            "widget.configuration.name": .init(en: 16, zhHant: 16),
            "widget.configuration.description": .init(en: 48, zhHant: 24),
            "widget.title": .init(en: 16, zhHant: 16),
            "widget.today": .init(en: 24, zhHant: 8),
            "widget.empty": .init(en: 28, zhHant: 10),
            "notifications.daily.title": .init(en: 44, zhHant: 20),
            "notifications.daily.body": .init(en: 56, zhHant: 24),
            "onboarding.continue": .init(en: 24, zhHant: 12),
            "onboarding.level.continue": .init(en: 24, zhHant: 12),
            "onboarding.reminder.enable": .init(en: 24, zhHant: 12),
            "onboarding.reminder.skip": .init(en: 24, zhHant: 12),
            "today.start.button": .init(en: 24, zhHant: 12),
            "today.resume.button": .init(en: 24, zhHant: 12),
            "today.completed.button": .init(en: 24, zhHant: 12),
            "review.start.button": .init(en: 24, zhHant: 12),
            "practice.next": .init(en: 24, zhHant: 12),
            "settings.reminders.openSettings": .init(en: 24, zhHant: 12),
            "settings.language.label": .init(en: 24, zhHant: 12),
            "settings.language.openSettingsHint": .init(en: 44, zhHant: 20),
            "settings.level.label": .init(en: 24, zhHant: 12),
            "settings.reminders.toggle": .init(en: 24, zhHant: 12),
            "settings.reminders.time": .init(en: 24, zhHant: 12)
        ]

        for (key, budget) in budgets {
            let value = try XCTUnwrap(catalog.strings[key], "\(key) must stay covered by localization budget tests")
            let english = try XCTUnwrap(value.localizations["en"]?.stringUnit.value)
            let traditionalChinese = try XCTUnwrap(value.localizations["zh-Hant"]?.stringUnit.value)

            XCTAssertLessThanOrEqual(english.count, budget.en, "\(key) English text is too long for compact UI")
            XCTAssertLessThanOrEqual(traditionalChinese.count, budget.zhHant, "\(key) zh-Hant text is too long for compact UI")
        }
    }

    private func loadCatalog() throws -> StringCatalog {
        let testFile = URL(fileURLWithPath: #filePath)
        let projectRoot = testFile
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let catalogURL = projectRoot
            .appendingPathComponent("WordingDailyApp")
            .appendingPathComponent("Resources")
            .appendingPathComponent("Localizable.xcstrings")
        let data = try Data(contentsOf: catalogURL)
        return try JSONDecoder().decode(StringCatalog.self, from: data)
    }
}

private struct StringBudget {
    let en: Int
    let zhHant: Int
}

private struct StringCatalog: Decodable {
    let sourceLanguage: String
    let strings: [String: StringCatalogEntry]
}

private struct StringCatalogEntry: Decodable {
    let localizations: [String: StringLocalization]
}

private struct StringLocalization: Decodable {
    let stringUnit: StringUnit
}

private struct StringUnit: Decodable {
    let value: String
}
