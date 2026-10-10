import Foundation
import SwiftUI

/// App 取得「現在」的唯一 seam。production 用系統時鐘;測試與 UI test 用固定時鐘。
struct AppClock {
    let now: () -> Date

    static let system = AppClock(now: { Date() })

    static func fixed(_ instant: Date) -> AppClock {
        AppClock(now: { instant })
    }

    /// 解析 launch 參數(ISO 8601)。值缺少或格式不對時回傳 nil,由呼叫端退回系統時鐘。
    static func fixed(fromLaunchValue value: String?) -> AppClock? {
        guard let value, let instant = ISO8601DateFormatter().date(from: value) else { return nil }
        return .fixed(instant)
    }
}

private struct AppClockKey: EnvironmentKey {
    static let defaultValue = AppClock.system
}

extension EnvironmentValues {
    var appClock: AppClock {
        get { self[AppClockKey.self] }
        set { self[AppClockKey.self] = newValue }
    }
}
