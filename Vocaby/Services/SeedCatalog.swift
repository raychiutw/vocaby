import Foundation

/// 內建詞庫的唯一入口。詞庫約 28 MB、18,000 多筆,解碼加驗證很貴,所以整個 process 只載入一次。
/// 載入失敗不快取,下次呼叫會重試;成功之後不再重做。
final class SeedCatalog {
    static let bundled = SeedCatalog { try SeedLoader().loadBundledSeed() }

    private let load: () throws -> [VocabularySeedItem]
    private let lock = NSLock()
    private var cached: [VocabularySeedItem]?

    init(load: @escaping () throws -> [VocabularySeedItem]) {
        self.load = load
    }

    func items() throws -> [VocabularySeedItem] {
        lock.lock()
        defer { lock.unlock() }

        if let cached { return cached }
        let loaded = try load()
        cached = loaded
        return loaded
    }
}
