import XCTest

/// 外觀由 tools/capture_screenshots.sh 以 simctl 設定;這裡依 `VOCABY_APPEARANCE`(light / dark)命名並走完 onboarding 與各 tab,把每個畫面存成 PNG。
/// 輸出到 `VOCABY_SHOT_DIR`,由 tools/capture_screenshots.sh 負責設定並比對基準圖。
final class AppearanceScreenshotTests: XCTestCase {
    func testCaptureScreens() throws {
        continueAfterFailure = false
        let env = ProcessInfo.processInfo.environment
        let appearance = try XCTUnwrap(env["VOCABY_APPEARANCE"], "VOCABY_APPEARANCE is not set")
        XCTAssertTrue(["light", "dark"].contains(appearance), "VOCABY_APPEARANCE 必須是 light 或 dark")
        let directory = URL(fileURLWithPath: try XCTUnwrap(env["VOCABY_SHOT_DIR"], "VOCABY_SHOT_DIR is not set"))
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)

        let app = XCUIApplication()
        // 固定「現在」(AppClock 的 DEBUG 鉤子),讓含日期的畫面(Progress)每次都一樣;
        // 固定亂數 seed,讓 Practice 的題目與選項順序每次都一樣
        app.launchArguments = ["-AppleLanguages", "(zh-Hant)", "-AppleLocale", "zh_TW", "-VOCABY_FIXED_NOW", "2026-07-10T09:00:00+08:00", "-VOCABY_RANDOM_SEED", "1"]
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
            settle()
            try capture(step)
            next.tap()
        }

        for (name, title) in [("home", "首頁"), ("learn", "學習"), ("practice", "練習"), ("progress", "進度"), ("my", "我的")] {
            let tab = app.buttons[title].firstMatch  // iOS 26 的 tab bar 不一定以 tabBars 暴露
            XCTAssertTrue(tab.waitForExistence(timeout: 120), "找不到 tab「\(title)」")
            tab.tap()
            settle()
            try capture(name)
        }

        // 關鍵狀態:Learn 翻開答案、評分完成後的總結。
        // 這些狀態會改變進度資料,所以放在所有 tab 的初始畫面之後。
        app.buttons["學習"].firstMatch.tap()
        let reveal = app.staticTexts["點一下顯示答案"]
        XCTAssertTrue(reveal.waitForExistence(timeout: 30), "找不到 Learn 卡片")
        reveal.tap()
        settle()
        try capture("learn-revealed")

        // 以固定比例循環評分(認識 ×6、收藏 ×2、不認識 ×2),直到出現完成總結;一輪張數不寫死
        let pattern = Array(repeating: "認識", count: 6) + Array(repeating: "收藏", count: 2) + Array(repeating: "不認識", count: 2)
        let again = app.buttons["再來一組"]
        var graded = 0
        while !again.exists {
            XCTAssertLessThan(graded, 30, "評了 30 張仍沒有完成總結")
            let grade = pattern[graded % pattern.count]
            let button = app.buttons[grade]
            XCTAssertTrue(button.waitForExistence(timeout: 30), "找不到評分按鈕「\(grade)」")
            button.tap()
            graded += 1
            settle()
        }
        try capture("learn-complete")

        // Practice:選中文意思(其他題型有音訊或輸入框),作答後看對錯回饋。
        // 倒數計時用固定時鐘,畫面上的剩餘秒數不會變。
        app.buttons["練習"].firstMatch.tap()
        // Menu 式 Picker 的 label 帶著目前的值(「模式, 混合題型」),所以用前綴比對
        let modePicker = app.buttons.matching(NSPredicate(format: "label BEGINSWITH '模式'")).firstMatch
        XCTAssertTrue(modePicker.waitForExistence(timeout: 30), "找不到「模式」選單")
        modePicker.tap()
        XCTAssertTrue(app.buttons["選中文意思"].firstMatch.waitForExistence(timeout: 10), "找不到「選中文意思」")
        app.buttons["選中文意思"].firstMatch.tap()
        let start = app.buttons["開始練習"]
        XCTAssertTrue(start.waitForExistence(timeout: 30), "找不到「開始練習」")
        start.tap()
        let next = app.buttons["下一題"]
        // 固定 seed 下第一題與選項順序固定;選「我想。」(「I suppose」的答案),若出題改變會在此明確失敗
        let answer = app.buttons["我想。"]
        XCTAssertTrue(answer.waitForExistence(timeout: 30), "找不到練習選項「我想。」")
        settle()
        try capture("practice-question")
        answer.tap()
        XCTAssertTrue(next.waitForExistence(timeout: 30), "作答後沒有出現「下一題」")
        settle()
        try capture("practice-answered")
    }

    /// 等翻牌與換卡動畫結束,避免擷到動畫中途的畫面。
    private func settle() { Thread.sleep(forTimeInterval: 1.0) }
}
