import XCTest

/// 外觀由 tools/capture_screenshots.sh 以 simctl 設定;這裡依 `VOCABY_APPEARANCE`(light / dark)命名並走完 onboarding 與各 tab,把每個畫面存成 PNG。
/// 輸出到 `VOCABY_SHOT_DIR`,由 tools/capture_screenshots.sh 負責設定並比對基準圖。
final class AppearanceScreenshotTests: XCTestCase {
    func testCaptureScreens() throws {
        let env = ProcessInfo.processInfo.environment
        let appearance = try XCTUnwrap(env["VOCABY_APPEARANCE"], "VOCABY_APPEARANCE is not set")
        XCTAssertTrue(["light", "dark"].contains(appearance), "VOCABY_APPEARANCE 必須是 light 或 dark")
        let directory = URL(fileURLWithPath: try XCTUnwrap(env["VOCABY_SHOT_DIR"], "VOCABY_SHOT_DIR is not set"))
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)

        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(zh-Hant)", "-AppleLocale", "zh_TW"]
        app.launch()

        func capture(_ name: String) throws {
            let png = XCUIScreen.main.screenshot().pngRepresentation
            try png.write(to: directory.appendingPathComponent("\(name)-\(appearance).png"))
        }

        // Onboarding:歡迎 → 等級(需先選一個才能繼續)→ 提醒(略過,避免通知權限對話框)
        for (step, select, button) in [
            ("onboarding-welcome", nil, "繼續"),
            ("onboarding-level", "基礎", "繼續"),
            ("onboarding-reminder", nil, "略過"),
        ] as [(String, String?, String)] {
            let next = app.buttons[button]
            XCTAssertTrue(next.waitForExistence(timeout: 10), "\(step) 找不到「\(button)」")
            if let select { app.buttons[select].tap() }
            try capture(step)
            next.tap()
        }

        for (name, title) in [("home", "首頁"), ("learn", "學習"), ("practice", "練習"), ("progress", "進度"), ("my", "我的")] {
            let tab = app.buttons[title].firstMatch  // iOS 26 的 tab bar 不一定以 tabBars 暴露
            XCTAssertTrue(tab.waitForExistence(timeout: 120), "找不到 tab「\(title)」")
            tab.tap()
            try capture(name)
        }

        // 關鍵狀態:Learn 翻開答案、評分完成後的總結。
        // Practice 的題目與選項順序用 SystemRandomNumberGenerator 且有倒數計時,無法穩定比對,不在此涵蓋。
        // 這些狀態會改變進度資料,所以放在所有 tab 的初始畫面之後。
        app.buttons["學習"].firstMatch.tap()
        let reveal = app.staticTexts["點一下顯示答案"]
        XCTAssertTrue(reveal.waitForExistence(timeout: 30), "找不到 Learn 卡片")
        reveal.tap()
        settle()
        try capture("learn-revealed")

        let grades = Array(repeating: "認識", count: 6) + Array(repeating: "收藏", count: 2) + Array(repeating: "不認識", count: 2)
        let again = app.buttons["再來一組"]
        for grade in grades {
            let button = app.buttons[grade]
            XCTAssertTrue(button.waitForExistence(timeout: 30), "找不到評分按鈕「\(grade)」")
            button.tap()
            settle()
        }
        XCTAssertTrue(again.waitForExistence(timeout: 30), "評分 \(grades.count) 張後沒有出現完成總結")
        try capture("learn-complete")
    }

    /// 等翻牌與換卡動畫結束,避免擷到動畫中途的畫面。
    private func settle() { Thread.sleep(forTimeInterval: 1.0) }
}
