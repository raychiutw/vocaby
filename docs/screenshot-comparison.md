# 深淺模式擷圖比對

對 onboarding 三步、五個 tab 的初始畫面,以及 Learn 的「翻開答案」「完成總結」兩個狀態,各擷取淺色與深色畫面(共 18 張,其中 Progress 不納入比對),與 `docs/screenshots/baseline` 比對。

## 執行

```sh
tools/capture_screenshots.sh            # 擷圖並比對基準圖,有差異時結束碼為 1
tools/capture_screenshots.sh --update   # 用本次擷圖取代基準圖
```

- 差異報告:`.build/screenshots/report/`,每張為「基準 | 目前 | 差異」並排圖。
- 腳本使用專用模擬器 `Vocaby-Shots`(iPhone 17,不存在時自動建立),每個外觀前都會 erase,
  所以不會動到其他專案的模擬器。
- 外觀以 `simctl ui appearance` 切換,狀態列固定為 9:41 / 滿電,避免時鐘造成假差異。
- 一輪約 3 分鐘:按下 onboarding 的「略過」後,app 會等通知中心回應,冷開機的模擬器上可能很慢。

## 解讀與限制

- 比對是像素差異加人工檢視,沒有自動通過門檻,也沒有接 CI。
- 基準圖受裝置與 OS 版本影響;換 Xcode 或模擬器 runtime 後要重新 `--update` 並人工確認。
- 目前只涵蓋各 tab 的初始畫面(全新安裝狀態)。每日選字不依日期,所以 Home、Learn、Practice、My 與 onboarding 是穩定的。
- **Progress 不納入比對**:圖表橫軸與 15 週格子含日期,每天都不同。它仍會被擷取(在 `.build/screenshots/current/`)供人檢視,但不進基準圖。
- My 的「已學習 0 / N」分母是詞庫總數,詞庫異動時基準圖會跟著變,屬預期。
- **Practice 的作答狀態不涵蓋**:題目與選項順序用 `SystemRandomNumberGenerator`、且有倒數計時,無法穩定比對;要涵蓋需先在 app 內注入 seed 與固定時鐘。
- Widget、通知、Increase Contrast 與 Dynamic Type 不在涵蓋範圍(Widget 請依 `docs/manual-verification.md`)。
- 修改視覺後的流程:執行比對 → 檢視報告確認差異符合預期 → `--update` 更新基準 → 一起 commit。
