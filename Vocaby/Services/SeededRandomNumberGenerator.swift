import Foundation
import SwiftUI

/// 可重現的亂數(SplitMix64)。UI test 用固定 seed 讓 Practice 的題目與選項順序每次都一樣。
struct SeededRandomNumberGenerator: RandomNumberGenerator {
    let seed: UInt64
    private var state: UInt64

    init(seed: UInt64) {
        self.seed = seed
        state = seed
    }

    /// 解析 launch 參數。值缺少或不是數字時回傳 nil。
    init?(fromLaunchValue value: String?) {
        guard let value, let seed = UInt64(value) else { return nil }
        self.init(seed: seed)
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }
}

private struct AppRandomSeedKey: EnvironmentKey {
    static let defaultValue: UInt64? = nil
}

extension EnvironmentValues {
    /// 有值時 Practice 用此 seed 出題;production 為 nil(系統亂數)。
    var appRandomSeed: UInt64? {
        get { self[AppRandomSeedKey.self] }
        set { self[AppRandomSeedKey.self] = newValue }
    }
}
