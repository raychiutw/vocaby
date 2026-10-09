# 深淺模式擷圖比對

對 onboarding 三步與五個 tab,各擷取淺色與深色畫面(共 16 張),與 `docs/screenshots/baseline` 比對。

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
- 目前只涵蓋各 tab 的初始畫面。畫面內容取決於當天的每日單字,有內容的畫面日後可能因日期不同而差異。
- Widget、通知、Increase Contrast 與 Dynamic Type 不在涵蓋範圍(Widget 請依 `docs/manual-verification.md`)。
- 修改視覺後的流程:執行比對 → 檢視報告確認差異符合預期 → `--update` 更新基準 → 一起 commit。
