# Apple HIG 對 iOS app 的規範研究(對照 Vocaby DESIGN.md)

- 研究日期:2026-10-09
- 範圍:Navigation / Tab bar、Typography / Dynamic Type、Color / Dark Mode、Layout / Safe area、觸控目標、Accessibility、Motion、Widgets、Notifications、Onboarding、Empty states、Settings、Localization、App icon、SF Symbols,另含 Gestures、Haptics、Permission(與專案直接相關)。
- 來源限制:僅採用 developer.apple.com 一手來源(HIG、SwiftUI / UserNotifications / WidgetKit / Xcode 官方文件、App Store Review Guidelines)。
- 取得方式:HIG 與官方文件皆以 `https://developer.apple.com/tutorials/data/design/human-interface-guidelines/<slug>.json` 與 `https://developer.apple.com/tutorials/data/documentation/<path>.json` 取回後解析文字;App Store Review Guidelines 取自其 HTML 頁面。條文為英文原文的轉述,非逐字引用。
- 連結慣例:`[slug](URL)` 的 URL 即為該頁面的公開網址(非 JSON 端點)。
- 注意:HIG 是設計指引(should / consider),不是硬性規則;唯一具審核效力的是 App Store Review Guidelines,文中會標明。

---

## 1. 摘要

1. DESIGN.md 的整體方向(原生 TabView、每個 tab 內 NavigationStack、系統字型與 text styles、系統色為主、Reduce Motion 替代、手勢要有等價按鈕、44 pt 觸控目標、通知文案不含敏感資訊)與 HIG 一致,沒有衝突。
2. **最需要處理的出入是對比**:`ProminentInk`(`#FFFFFF`)放在 `Accent` / `BrandTeal` 漸層上,以 WCAG 公式自行計算只有約 1.9–2.8:1,低於 HIG 轉引的 4.5:1(17 pt 以下)與 3:1(18 pt 以上或粗體)門檻。深色模式因底色變亮,比值更低(見第 4 節)。
3. DESIGN.md 的色彩 token 只有 light / dark 兩組;HIG 要求自訂色另外提供 Increase Contrast 變體。Widget 也未涵蓋 accented / vibrant 渲染模式。
4. 幾項「產品決策與 HIG 偏好不同」的地方值得再確認:onboarding 強制選等級與提醒設定、通知權限在 onboarding 內索取且附 skip、自訂 swipe 評分手勢、Learn tab 用系統 badge 顯示待複習數、無 haptics 開關、quiz 計時器。
5. DESIGN.md 完全沒涵蓋 App icon(Icon Composer、default / dark / tinted 變體)、launch screen、locale 格式化與隱私政策入口等項目。
6. HIG 沒有獨立的 Empty states 或 Localization 頁面;相關規範分散在 Writing、Inclusion、Right to left、以及 Xcode / SwiftUI 文件。

---

## 2. 各主題規範要點

### 2.1 Navigation 與 Tab bar

- Tab bar 用來切換 app 的各區塊,不是放動作;對 current view 的動作應放 toolbar。來源:[tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)
- 瀏覽各區塊時 tab bar 應保持可見,隱藏會讓人忘記自己在哪;唯一例外是 modal 覆蓋時。來源:[tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)
- 避免 overflow tabs(iPhone 空間不足時末位 tab 會變成 More);tab 數量越少越容易導覽。來源:[tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)
- 不要 disable 或隱藏 tab bar 按鈕,即使內容暫時不可用;區塊為空時應說明原因。來源:[tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)
- Tab 要有 label,盡量用單一詞;建議用 SF Symbols,且偏好 filled 版本。來源:[tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)
- Badge(紅色橢圓)只保留給「值得注意的關鍵資訊」,避免稀釋意義。來源:[tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)
- 避免讓 tab label 顏色與 content layer 背景相近;若內容很鮮豔,tab bar 偏好單色外觀或與內容有足夠區隔的 accent。來源:[tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)、[color](https://developer.apple.com/design/human-interface-guidelines/color)
- iOS 的 tab bar 浮在內容上方(Liquid Glass)。有 accessory(如 Music 的 MiniPlayer)時才「可選擇」在捲動時 minimize;使用者點 tab 或捲到頂可還原。來源:[tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)
- `tabBarMinimizeBehavior(_:)` 與 `TabBarMinimizeBehavior.never`(「Never minimize the tab bar」)皆標示 iOS 26.0+。來源:[TabBarMinimizeBehavior](https://developer.apple.com/documentation/swiftui/tabbarminimizebehavior)、[never](https://developer.apple.com/documentation/swiftui/tabbarminimizebehavior/never)、[tabBarMinimizeBehavior(_:)](https://developer.apple.com/documentation/swiftui/view/tabbarminimizebehavior(_:))
- Toolbar:包含 title、導覽控制、動作;title 建議簡短(原文為少於 15 字元);使用標準 Back / Close 符號,不要用文字寫「Back」「Close」;降低 toolbar 背景與 tinted 控制項的使用。來源:[toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars)
- Sheet:一次只顯示一個;若放 Done 按鈕,要搭配 Cancel 或 Back;不要三者並存;複雜或冗長流程考慮 full-screen modal。來源:[sheets](https://developer.apple.com/design/human-interface-guidelines/sheets)
- Modal 要有明顯的關閉方式,內容保持簡短單純,不要做成「app 中的 app」。來源:[modality](https://developer.apple.com/design/human-interface-guidelines/modality)

### 2.2 Typography 與 Dynamic Type

- iOS / iPadOS 預設 17 pt,最小 11 pt;避免 Ultralight / Thin / Light 字重。來源:[typography](https://developer.apple.com/design/human-interface-guidelines/typography)
- 優先用內建 text styles,即可自動支援 Dynamic Type 與 Larger Accessibility Sizes;不要內嵌系統字型,用 `Font.Design` 取用。來源:[typography](https://developer.apple.com/design/human-interface-guidelines/typography)
- iOS 預設(Large)尺寸:Large Title 34、Title 2 22、Title 3 20、Headline / Body 17、Subhead 15、Footnote 13、Caption 1 12、Caption 2 11 pt。來源:[typography](https://developer.apple.com/design/human-interface-guidelines/typography)(Dynamic Type sizes 表)
- 文字放大時要讓版面適應:橫向並排改為垂直堆疊、減少欄數、列高可成長;盡量減少 truncation,捲動區域內除非能開啟詳細頁否則避免截斷。來源:[typography](https://developer.apple.com/design/human-interface-guidelines/typography)、[layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- 放大文字時要「優先」放大重要內容,例如放大字級時使用者不預期 tab 標題跟著變大。來源:[typography](https://developer.apple.com/design/human-interface-guidelines/typography)
- 有意義的介面圖示要隨字級放大;SF Symbols 會自動隨 Dynamic Type 縮放。來源:[typography](https://developer.apple.com/design/human-interface-guidelines/typography)
- 至少提供 200% 的文字放大能力(可透過 Dynamic Type)。來源:[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- 保持一致的資訊層級:字級再大,主要元素仍應留在畫面上方。來源:[typography](https://developer.apple.com/design/human-interface-guidelines/typography)
- 測試方式:設定 > 輔助使用 > 顯示與文字大小 > 更大的文字,開啟 Larger Accessibility Sizes。來源:[typography](https://developer.apple.com/design/human-interface-guidelines/typography)

### 2.3 Color 與 Dark Mode

- 自訂色必須提供 light 與 dark 變體,並為每個變體提供 Increase Contrast 選項;即使 app 只發佈單一外觀,也要同時提供 light / dark 色以配合 Liquid Glass 的適應行為。來源:[color](https://developer.apple.com/design/human-interface-guidelines/color)
- 避免硬編系統色數值(實際值會隨版本變動);不要重新定義 dynamic system colors 的語意(例如把 `separator` 當文字色、把 `secondaryLabel` 當背景色)。來源:[color](https://developer.apple.com/design/human-interface-guidelines/color)
- 避免用同一個顏色代表不同意義;顏色要一致地傳達狀態或可互動性。來源:[color](https://developer.apple.com/design/human-interface-guidelines/color)
- 不要只靠顏色傳達資訊,需要文字標籤或形狀輔助。來源:[color](https://developer.apple.com/design/human-interface-guidelines/color)、[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- iOS 背景色分 system 與 grouped 兩組(各有 primary / secondary / tertiary);有 grouped table view 時用 grouped 組,否則用 system 組。來源:[color](https://developer.apple.com/design/human-interface-guidelines/color)
- Liquid Glass 上的色彩要節制:強調主要動作時把色彩套在背景而非符號 / 文字上,且不要在多個控制項背景上加色。來源:[color](https://developer.apple.com/design/human-interface-guidelines/color)
- 文化差異:顏色在不同地區有不同含意,需確認各 locale 的色彩訊息一致。來源:[color](https://developer.apple.com/design/human-interface-guidelines/color)、[inclusion](https://developer.apple.com/design/human-interface-guidelines/inclusion)
- Dark Mode:避免提供 app 專屬的外觀設定;須在 Auto 外觀切換、Increase Contrast、Reduce Transparency 下測試。來源:[dark-mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)
- Dark Mode 不是單純反相;自訂色用 Color Set asset 指定亮 / 暗變體。來源:[dark-mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)
- 對比:最低 4.5:1,自訂前景 / 背景(尤其小字)力求 7:1。來源:[dark-mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)
- iOS 優先使用系統背景色,因為系統會在 popover / modal sheet 等前景介面自動換成 elevated 背景;自訂背景色會削弱此層次感。來源:[dark-mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)
- SwiftUI 可讀取 `colorSchemeContrast`(standard / increased);若只需不同顏色或圖片,建議放在 Asset Catalog 處理。來源:[colorSchemeContrast](https://developer.apple.com/documentation/swiftui/environmentvalues/colorschemecontrast)

### 2.4 Layout、Safe area 與觸控目標

- 尊重 safe area、系統 margins 與 layout guides;Dynamic Island 等硬體特徵不得遮擋內容。來源:[layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- 版面決策應依 size classes(compact / regular),而非裝置類型或方向;並要考慮所有 size class 組合(例如 iPad 縮窗、iPhone Mirroring)。來源:[layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- 系統 layout guides 提供標準邊界,並限制文字寬度以維持可讀性。來源:[layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- 不要依空間改變功能,只改變可見功能量;空間夠大時可由 tab bar 轉為 sidebar。來源:[layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- 以多種 size classes、localizations、text sizes 預覽;先測最大與最小版面。來源:[layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- 控制項尺寸:iOS 預設 44x44 pt,最小 28x28 pt;間距與尺寸同等重要——有 bezel 的元素周圍約 12 pt,無 bezel 約 24 pt。來源:[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- Button 的 hit region 一般至少 44x44 pt。來源:[buttons](https://developer.apple.com/design/human-interface-guidelines/buttons)
- 每個畫面的 prominent button 以一到兩個為限;用「樣式」而非「大小」區分主要選項;主要動作偏好滿版寬度。來源:[buttons](https://developer.apple.com/design/human-interface-guidelines/buttons)

### 2.5 Accessibility(VoiceOver、對比、Reduce Motion)

- 對比下限(Accessibility Inspector 採 WCAG AA):17 pt 以下 4.5:1;18 pt 3:1;任何大小的 Bold 3:1。若預設達不到,至少在 Increase Contrast 開啟時提供更高對比配色;light / dark 都要檢查。來源:[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- VoiceOver:為所有關鍵介面元素與自訂元素提供描述性 label;圖表要提供簡明描述;純裝飾圖片排除於 VoiceOver 之外。來源:[voiceover](https://developer.apple.com/design/human-interface-guidelines/voiceover)
- 以標題與 heading 建立導覽階層;描述元素的分組、順序;**可見內容或版面變動時要通知 VoiceOver**;可行時支援 rotor。來源:[voiceover](https://developer.apple.com/design/human-interface-guidelines/voiceover)
- SwiftUI `accessibilityLabel`:label 不要重複已知資訊(例如不要寫「Play button」,因為 button trait 已說明)。來源:[accessibilityLabel(_:)](https://developer.apple.com/documentation/swiftui/view/accessibilitylabel(_:))
- 手勢:常用互動用最簡單的手勢;**核心功能要有手勢以外的替代方式**(原文例:swipe 關閉時也提供按鈕)。來源:[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)、[gestures](https://developer.apple.com/design/human-interface-guidelines/gestures)
- 認知:盡量少用「限時」介面元素(例如會自動消失者),偏好用明確動作關閉。來源:[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- Reduce Motion 開啟時:減少自動與重複動畫(縮放、zoom、周邊動態);作法包含收緊 spring 以減少彈跳、讓動畫直接追蹤手勢、避免 z 軸深度動畫、**以 fade 取代 x / y / z 軸轉場**、避免進出 blur。來源:[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- SwiftUI `accessibilityReduceMotion`:為 true 時 UI 應避免大幅動畫,特別是模擬第三維度者。來源:[accessibilityReduceMotion](https://developer.apple.com/documentation/swiftui/environmentvalues/accessibilityreducemotion)
- SwiftUI `accessibilityDifferentiateWithoutColor`:為 true 時,UI 應以形狀或 glyph 取代單靠顏色傳達資訊。來源:[accessibilityDifferentiateWithoutColor](https://developer.apple.com/documentation/swiftui/environmentvalues/accessibilitydifferentiatewithoutcolor)
- 另需支援 Voice Control(元素 label 正確)、Switch Control、Full Keyboard Access;並可在 App Store Connect 標示 Accessibility Nutrition Labels。來源:[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)
- Charts:Swift Charts 預設提供 Audio Graphs 與每個 mark 的 accessibility element;建議補上圖表標題與摘要;label 描述「資料代表什麼」而非「長什麼樣子」(不要描述顏色)。來源:[charts](https://developer.apple.com/design/human-interface-guidelines/charts)
- 圖表不應只靠顏色區分資料,需有其他輔助方式。來源:[charts](https://developer.apple.com/design/human-interface-guidelines/charts)

### 2.6 Motion 與 Haptics

- 動態要有目的,不為動而動;不要讓動態成為傳達重要資訊的唯一管道,可搭配 haptics 與音訊補充。來源:[motion](https://developer.apple.com/design/human-interface-guidelines/motion)
- 回饋動畫要簡短精確;一般 app 中避免對「高頻互動」加入動態;**讓使用者能取消動態,不必等動畫跑完才能操作**。來源:[motion](https://developer.apple.com/design/human-interface-guidelines/motion)
- Haptics:依文件化的語意使用系統模式;全 app 一致、與動畫強度對應;避免過度使用;多數 app 用短促、對應離散事件的 haptic;**haptics 要可關閉,關閉後 app 仍應好用**。來源:[playing-haptics](https://developer.apple.com/design/human-interface-guidelines/playing-haptics)
- SwiftUI 提供 `sensoryFeedback(_:trigger:)`(iOS 17.0+),在 trigger 值改變時播放回饋。來源:[sensoryFeedback(_:trigger:)](https://developer.apple.com/documentation/swiftui/view/sensoryfeedback(_:trigger:))

### 2.7 Gestures

- 提供不只一種互動方式,不要假設使用者能做特定手勢。來源:[gestures](https://developer.apple.com/design/human-interface-guidelines/gestures)
- 避免把 tap / swipe 這類熟悉手勢用於 app 獨有的動作;自訂手勢只在必要時加入,並須 discoverable、易執行、與其他手勢可區分、**不是執行重要動作的唯一方式**;要提供學習時機。來源:[gestures](https://developer.apple.com/design/human-interface-guidelines/gestures)
- 手勢無法使用時要明確告知原因。來源:[gestures](https://developer.apple.com/design/human-interface-guidelines/gestures)

### 2.8 Widgets

- Widget 應 glanceable、反映 app 主要用途;偏好會隨時間變化的資訊;不要只複製 app icon 的價值。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- 多尺寸只在有價值時提供;不要把小尺寸內容單純放大填滿大尺寸。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- 避免在 app 內做出外觀像 widget 卻行為不同的元素。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- Widget 可以含按鈕與 toggle,非按鈕區域的互動會開啟 app,且應 deep link 到相關位置;是否互動屬產品選擇。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- 標準邊界:多數 widget 為 16 pt,緊湊分組可用 11 pt。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- 文字:偏好系統字型與 text styles;避免小於 11 pt;不要把文字點陣化;iOS widget 的 Dynamic Type 支援 Large 到 AX5。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- 色彩:不要仰賴特定顏色傳達意義(widget 可能是單色 / tinted);全彩圖片要謹慎使用(tinted / clear 外觀預設會去飽和)。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- 外觀與渲染模式:Home Screen 有 light、dark、clear、tinted;Full-color 要支援 light / dark;Accented 模式下系統移除背景並把內容分為 accent / primary 兩組(`widgetAccentable`);Lock Screen、StandBy 低光源為 vibrant。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)、[WidgetRenderingMode](https://developer.apple.com/documentation/widgetkit/widgetrenderingmode)
- 更新:widget 不支援即時更新;不要用 placeholder 蓋掉過期資料;若使用者查看頻率高於更新頻率,可顯示資料更新時間;日期時間用系統機制更新以節省更新額度。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- WidgetKit 以每 24 小時的預算分配 reload;常被查看的 widget 通常為 40 至 70 次;系統外觀 / locale 變更不必由 app 要求 reload。來源:[Keeping a widget up to date](https://developer.apple.com/documentation/widgetkit/keeping-a-widget-up-to-date)
- 需設計 widget gallery 預覽與 placeholder;描述以動詞開頭,多尺寸共用單一描述。來源:[widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)
- 審核:widgets、extensions、notifications 應與 app 的內容與功能相關(App Store Review Guideline 2.5.16)。來源:[App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

### 2.9 Notifications

- 發送前必須取得使用者同意。來源:[notifications](https://developer.apple.com/design/human-interface-guidelines/notifications)
- 內容簡潔、有資訊量;避免對同一件事重複通知(即使使用者沒回應);避免敏感、個人或機密資訊;錯誤訊息用 alert 而非 notification。來源:[notifications](https://developer.apple.com/design/human-interface-guidelines/notifications)
- 避免通知內容要求使用者在 app 內做特定任務(除非用 notification actions 提供);不要在內容中放 app 名稱或 icon(系統已顯示)。來源:[notifications](https://developer.apple.com/design/human-interface-guidelines/notifications)
- 內文使用完整句子、sentence case、正確標點;標題用 title-style 且無結尾標點。來源:[notifications](https://developer.apple.com/design/human-interface-guidelines/notifications)
- 預覽被隱藏時,系統只顯示 app icon 與預設標題;建議提供通用描述文字(如「Reminder」)。開發端對應 `hiddenPreviewsBodyPlaceholder`。來源:[notifications](https://developer.apple.com/design/human-interface-guidelines/notifications)
- 通知進入 foreground 時不顯示橫幅;應以不干擾的方式在 app 內呈現資訊。來源:[notifications](https://developer.apple.com/design/human-interface-guidelines/notifications)
- Badge 只用於未讀通知數,不可用於其他數值資訊;不可作為傳達重要資訊的唯一管道。來源:[notifications](https://developer.apple.com/design/human-interface-guidelines/notifications)
- Interruption level 有 Passive、Active(預設)、Time Sensitive、Critical 四級;Time Sensitive 僅限當下或一小時內的事件;行銷內容永不使用 Time Sensitive。來源:[managing-notifications](https://developer.apple.com/design/human-interface-guidelines/managing-notifications)
- 行銷 / 推廣通知需使用者明確同意;且 app 內須提供可變更通知選擇的設定頁。來源:[managing-notifications](https://developer.apple.com/design/human-interface-guidelines/managing-notifications)
- 授權時機:官方文件建議「在能讓人理解用途的情境中」請求授權,優於首次啟動就請求;可用 provisional authorization 先試送靜默通知;排程本地通知前一律先檢查授權狀態。來源:[Asking permission to use notifications](https://developer.apple.com/documentation/usernotifications/asking-permission-to-use-notifications)
- 權限一般準則:只在 app 明確需要時請求,避免在啟動時請求(除非是 app 運作必需);若需要預先說明畫面,該畫面只放一個按鈕、標示為「Continue」「Next」之類而非「Allow」,且不要提供離開 / 取消的選項。此規範的適用範圍原文列舉為 camera、microphone、location、contact、calendar、tracking 等,是否涵蓋 notifications 見第 5 節。來源:[privacy](https://developer.apple.com/design/human-interface-guidelines/privacy)
- 審核:Push Notifications 不得是 app 運作的必要條件,不應用於傳送敏感個人資訊,且行銷用途須明確 opt-in 並提供 opt-out(App Store Review Guideline 4.5.4);使用者拒絕權限時,應盡可能提供替代方案(5.1.1(iv))。來源:[App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

### 2.10 Onboarding 與 Launching

- Onboarding 應快速、有趣、可選擇略過;若提供教學且使用者略過,之後不再強迫顯示,但要容易再找到。來源:[onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding)
- 偏好透過互動式體驗教學,或用情境化提示(TipKit)取代單一流程。來源:[onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding)
- **延後非必要的設定與客製化步驟,提供合理預設值**,讓多數人能立刻使用。來源:[onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding)
- 若 app 必須取得私人資料才能運作,可將權限請求整合進 onboarding;否則在使用者第一次用到相關功能時再請求。來源:[onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding)
- 先讓使用者體驗 app,再要求評分或購買。來源:[onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding)
- Launch screen:要與第一個畫面幾乎一致;不要含文字(不會被本地化)、不要放廣告或品牌宣傳;還原上次的狀態。來源:[launching](https://developer.apple.com/design/human-interface-guidelines/launching)

### 2.11 Empty states 與文案

- HIG 沒有獨立 Empty states 頁面;規範在 Writing:空白畫面要提供明確的下一步,盡可能附按鈕或連結;empty state 通常是暫時的,不要放之後會消失的關鍵資訊。來源:[writing](https://developer.apple.com/design/human-interface-guidelines/writing)
- 按鈕與連結標籤幾乎都以動詞開頭,避免過度俏皮;多步驟流程中對「下一步」的用語要一致(Continue / Next 擇一),完成用 Done。來源:[writing](https://developer.apple.com/design/human-interface-guidelines/writing)
- 少用所有格代名詞(my / your),若用要全 app 一致;避免用 we。錯誤訊息避免責怪並說明如何修正,不必用「oops」。來源:[writing](https://developer.apple.com/design/human-interface-guidelines/writing)
- 設定項目的描述只需說明「開啟時會做什麼」;需引導到系統設定時,提供直接連結或按鈕而非描述位置。來源:[writing](https://developer.apple.com/design/human-interface-guidelines/writing)
- Loading:盡快顯示內容,可用 placeholder,並能在等待時做其他事。來源:[loading](https://developer.apple.com/design/human-interface-guidelines/loading)

### 2.12 Settings

- 預設值應對最多人最好;盡量減少設定項目。來源:[settings](https://developer.apple.com/design/human-interface-guidelines/settings)
- 自訂設定頁放「一般、不常更改」的選項;與特定任務有關的選項(篩選、重排、顯示 / 隱藏)應放在該任務畫面內。來源:[settings](https://developer.apple.com/design/human-interface-guidelines/settings)
- 避免提供與系統設定重複的選項(如輔助使用、外觀),以免使用者誤以為系統設定不適用於 app。來源:[settings](https://developer.apple.com/design/human-interface-guidelines/settings)
- 若放進系統「設定」app 的 app 設定,只放最少更改的選項,並可提供按鈕直接開啟。來源:[settings](https://developer.apple.com/design/human-interface-guidelines/settings)
- 審核:所有 app 必須在 App Store Connect 與 app 內以易於存取的方式提供隱私政策連結(App Store Review Guideline 5.1.1(i))。來源:[App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

### 2.13 Localization

- HIG 無獨立 Localization 頁面。Inclusion 頁:使用者可自選語言與地區(日期、時間、金額格式);先做 internationalization,再提供翻譯;用 SF Symbols 有助簡化本地化;色彩的文化意涵須逐一檢視。來源:[inclusion](https://developer.apple.com/design/human-interface-guidelines/inclusion)
- Writing:用簡單明確的語言,把無障礙與本地化納入考量。來源:[writing](https://developer.apple.com/design/human-interface-guidelines/writing)
- Layout:版面要處理 locale 相關差異(LTR / RTL、日期 / 時間 / 數字格式、字型變化、文字長度)。來源:[layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- Right to left:不支援 RTL 語言時可略過,但優先使用系統元件有助日後擴充。來源:[right-to-left](https://developer.apple.com/design/human-interface-guidelines/right-to-left)
- 通知 action 按鈕與 tooltip 的文字要考慮本地化造成的長度變化;App icon 與 launch screen 內的文字不支援本地化,應避免。來源:[notifications](https://developer.apple.com/design/human-interface-guidelines/notifications)、[app-icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)、[launching](https://developer.apple.com/design/human-interface-guidelines/launching)
- Xcode 本地化流程:使用可本地化 API 處理格式化與翻譯;string catalog 管理語言與註解;在 Xcode previews 與實機測試各語言;請母語者透過 TestFlight 檢視;**同時在 App Store Connect 本地化 App Store 資訊**。來源:[Localization (Xcode)](https://developer.apple.com/documentation/xcode/localization)
- SwiftUI:`Text` 的 `comment` 參數可為譯者加註;字串字面量會被視為 `LocalizedStringKey`。來源:[Preparing views for localization](https://developer.apple.com/documentation/swiftui/preparing-views-for-localization)

### 2.14 App icon

- 以圖層設計(background + foreground layers),用 Icon Composer(隨 Xcode)匯入,系統會套用 Liquid Glass 效果;提供 default、dark、mono / tinted 變體;提供方形、不預先遮罩的圖層,由系統套圓角。來源:[app-icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)
- 設計力求簡潔、中心元素明確;避免文字(除非對品牌必要)、照片與重製 UI 元件;不要自行加入高光、陰影、模糊等系統已負責的效果。來源:[app-icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)
- 使用者可選擇 default、dark、clear、tinted 外觀;各外觀的核心視覺特徵應一致;dark icon 以 light icon 為基礎,避免過亮。來源:[app-icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)
- 前景圖層的邊緣應清楚,避免柔邊 / 羽化;背景若為漸層要能與系統光影配合。來源:[app-icons](https://developer.apple.com/design/human-interface-guidelines/app-icons)

### 2.15 SF Symbols

- Symbols 有 monochrome、hierarchical、palette、multicolor 四種渲染模式;使用系統色可自動適應無障礙設定與外觀模式。來源:[sf-symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)
- 九種字重對應 SF 字型,有 small / medium / large 三種 scale,可與相鄰文字精準對齊。來源:[sf-symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)
- SF Symbols 7+ 支援由單一色彩產生線性漸層的 gradient 渲染,在較大尺寸效果較佳。來源:[sf-symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)
- 符號動畫要節制、有明確用途並符合 app 調性;自訂 symbols 要提供替代文字標籤(accessibility description)。來源:[sf-symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)
- 不可將 SF Symbols(或相似圖像)用於 app icon、logo 或其他商標用途。來源:[sf-symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols)

---

## 3. 與 DESIGN.md 的對照(只列有出入或值得確認處)

標記:**[出入]** = 與 HIG 文字有明確落差,建議修正;**[確認]** = 屬產品決策或 HIG 未明講,建議團隊決定;**[缺漏]** = DESIGN.md 未涵蓋。

### 3.1 [出入] `ProminentInk` 與 Accent 漸層的對比不足

以 WCAG 相對亮度公式自行計算(非 Apple 提供數值):

| 前景 / 背景 | 對比值 |
|---|---|
| `#FFFFFF` on Accent light `#0EA5E9` | 2.77:1 |
| `#FFFFFF` on BrandTeal light `#14B8A6` | 2.49:1 |
| `#FFFFFF` on Accent dark `#38BDF8` | 2.14:1 |
| `#FFFFFF` on BrandTeal dark `#2DD4BF` | 1.86:1 |
| Accent light 當文字 on 白底 | 2.77:1 |
| Accent light on `AccentSoft` `#E0F2FE` | 2.42:1 |

- HIG 門檻:17 pt 以下 4.5:1、18 pt 或 Bold 3:1([accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility));Dark Mode 頁建議最低 4.5:1、小字力求 7:1([dark-mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode))。
- DESIGN.md 第 Accessibility 節宣稱「All body text contrast must meet WCAG AA」,但白字按鈕與 Accent 當文字(如 selected 狀態 / 連結式次要按鈕)未必符合。主要按鈕標籤字級為 17 pt 以內時需要 4.5:1。
- 注意 `ProminentInk` 在 dark 也是 `#FFFFFF`,而 dark 的 Accent / Teal 更亮,比值反而更低。
- 其餘 token 以假設的系統底色(白 `#FFFFFF`、`#F2F2F7`、黑 `#000000`、`#1C1C1E`;這些底色值非本研究的 HIG 來源提供,僅為估算假設)計算:`MutedInk` light 在白底 5.16、在 `#F2F2F7` 4.62(邊界);`ReviewAmber` light 在白底 4.63(邊界);其餘 token 皆明顯高於 4.5。實作時應以 Accessibility Inspector 在真實背景驗證。

### 3.2 [出入] 色彩 token 缺少 Increase Contrast 變體

- DESIGN.md「Color」節只定義 Light / Dark 兩組。HIG 要求自訂色除 light / dark 外,每組再提供 Increase Contrast 選項([color](https://developer.apple.com/design/human-interface-guidelines/color));SwiftUI 也提供 `colorSchemeContrast`,簡單情況可在 Asset Catalog 設定([colorSchemeContrast](https://developer.apple.com/documentation/swiftui/environmentvalues/colorschemecontrast))。
- 另可補上 `accessibilityDifferentiateWithoutColor` 的行為規格(DESIGN.md 已要求不單靠顏色,但未指明偵測此設定)。

### 3.3 [確認] Tab badge 與 tab bar 色彩

- DESIGN.md 在 Learn tab 以系統 badge 顯示待複習數。HIG:badge 只保留給「關鍵資訊」以免稀釋([tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars))。待複習數是否算關鍵、是否常駐顯示,建議確認;DESIGN.md 另一方面「不要有 guilt / 壓力」的語氣,紅色數字 badge 與之略有張力。
- HIG 建議避免 tab label 色與 content layer 背景相近([tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars))。Home 的漸層圓形進度與 selected tab 同為 Accent 色系,需在實機確認是否影響辨識。
- HIG 偏好 filled 的 tab 符號([tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)),DESIGN.md 列的是 outline 名稱(`house` 等)。SwiftUI TabView 是否自動為選取態套用 fill 變體,本研究未從官方文件確認,見第 5 節。
- 與 HIG 一致處:5 個 tab、單字 label、`.tabBarMinimizeBehavior(.never)`(HIG 僅把 minimize 描述為「有 accessory 時可選用」,不啟用不衝突)、不把動作放進 tab bar、tab 內用獨立 NavigationStack。

### 3.4 [確認] 自訂 swipe 評分手勢

- DESIGN.md 的右滑 / 左滑 / 上滑評分是 app 專屬的自訂手勢,且 tap 翻轉卡片。HIG 建議避免把 tap / swipe 這類熟悉手勢用於 app 獨有動作,若採用須 discoverable、並提供學習時機([gestures](https://developer.apple.com/design/human-interface-guidelines/gestures))。
- 已符合處:DESIGN.md 規定有等價 xmark / star / checkmark 按鈕,滿足「不是唯一方式」([gestures](https://developer.apple.com/design/human-interface-guidelines/gestures)、[accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility))。
- 建議補充:首次使用的手勢提示(HIG 建議情境式提示,見 [onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding));「翻面」也需要 VoiceOver / 非手勢的等價操作,DESIGN.md 目前只列了評分按鈕;卡片翻面與換卡時需通知 VoiceOver 內容已變([voiceover](https://developer.apple.com/design/human-interface-guidelines/voiceover))。

### 3.5 [確認] Quiz 計時器

- HIG 建議盡量少用限時介面元素([accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility))。該句針對自動消失的 view,quiz 計時嚴格說不同,但對使用 VoiceOver / Switch Control 的人仍有負擔。
- DESIGN.md 已把「unlimited」列為選項且逾時不自動前進(符合精神)。建議明訂**預設為 unlimited**,並確認 VoiceOver / Switch Control 使用者的作答時間設計。

### 3.6 [確認] Onboarding 流程

- HIG:onboarding 應快速且可略過;延後非必要設定、提供合理預設([onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding))。DESIGN.md 要求「主要動作在選擇等級前保持 disabled」,且導覽圖含「Level and daily-goal choice」,但畫面清單只描述了等級選擇。建議確認(a)是否可預設一個等級(如 Basic)讓使用者直接開始、(b)每日目標是否放在此處或延後到 Settings、(c)文件內導覽圖與畫面清單對 daily goal 的描述不一致。
- 權限時機:HIG 與 UserNotifications 文件都偏好在情境中請求授權,並提到「若 app 需要才可在 onboarding 整合」([onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding)、[Asking permission](https://developer.apple.com/documentation/usernotifications/asking-permission-to-use-notifications))。提醒不是 Vocaby 運作必需(DESIGN.md 已寫明「practice still works」),所以放在 onboarding 第 3 步屬可接受但非首選;可考慮在使用者完成第一次學習後再詢問。此亦與審核 4.5.4 / 5.1.1(iv) 的精神一致([guidelines](https://developer.apple.com/app-store/review/guidelines/))。
- Pre-alert 畫面:privacy 頁規定自訂前置畫面只放一個按鈕、不要用「Allow」、不要提供離開選項([privacy](https://developer.apple.com/design/human-interface-guidelines/privacy))。DESIGN.md 的 Reminder setup 有「time picker + 啟用提醒主要按鈕 + skip」,按鈕名稱「enable reminders」語意接近 Allow。該規範列舉的資源不含 notifications,因此是否適用待確認;若嚴格適用,應改為單一 Continue / Next 按鈕。
- 其他:Welcome 螢幕屬於 splash 性質,HIG 要求「簡短」([onboarding](https://developer.apple.com/design/human-interface-guidelines/onboarding));整個 onboarding 目前沒有「略過全部」入口。

### 3.7 [確認] Haptics 與動態

- DESIGN.md 規範了 haptics 的使用情境,但未提供**關閉 haptics 的設定**;HIG 要求 haptics 可被關閉([playing-haptics](https://developer.apple.com/design/human-interface-guidelines/playing-haptics))。系統層級關閉震動是否即足夠,HIG 未明說,建議確認並在 Settings 評估。
- 動態:每張卡片都有 3D flip + swipe tilt + 離場動畫,屬於高頻互動。HIG:一般 app 避免對高頻互動加動態,且不應讓使用者等動畫結束才能操作([motion](https://developer.apple.com/design/human-interface-guidelines/motion))。建議規定翻面 / 換卡期間可立即接受下一個輸入(中斷動畫);confetti 1.5 秒不得阻擋操作。
- Reduce Motion 規範(以短 opacity 變化取代)與 HIG 一致([accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)、[accessibilityReduceMotion](https://developer.apple.com/documentation/swiftui/environmentvalues/accessibilityreducemotion))。

### 3.8 [缺漏] Widget 渲染模式與背景

- DESIGN.md 的 Widget 節僅描述尺寸與文案。HIG 要求考慮 full-color、accented(tinted / clear)、vibrant 的渲染模式,並在 accented 模式用 `widgetAccentable` 分組([widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)、[WidgetRenderingMode](https://developer.apple.com/documentation/widgetkit/widgetrenderingmode))。Vocaby 的品牌漸層在 tinted / clear 下會被系統去飽和或移除背景,進度資訊需要不靠顏色也能成立。
- 未提及 Lock Screen(accessory)與 StandBy;若 v1 刻意只做 Home Screen 的 small / medium,建議在 DESIGN.md 明寫。
- 「今天」的日期邊界:widget 更新有預算(常用 widget 每日約 40–70 次)([Keeping a widget up to date](https://developer.apple.com/documentation/widgetkit/keeping-a-widget-up-to-date)),「app 為唯一寫入者」的設計下,跨日(例如過午夜)時的 timeline entry 需明確規劃,否則會顯示昨天的進度。HIG 同時要求「不要用 placeholder 掩蓋過期資料」([widgets](https://developer.apple.com/design/human-interface-guidelines/widgets)),與 DESIGN.md「stale 狀態要看起來刻意」的方向一致。
- HIG:避免在 app 內放外觀像 widget 但行為不同的元件([widgets](https://developer.apple.com/design/human-interface-guidelines/widgets))。Home 的進度圈與 small widget 外觀相近,需注意不要被誤認為可 pin 或可互動。
- 一致處:16 pt 標準邊界、系統字型、短文案、無按鈕僅 deep link(HIG 允許但不要求互動)、不揭露敏感資料。

### 3.9 [確認] 通知細節

- 與 HIG 一致:文案簡短、不含敏感資訊、點擊開啟 Today、非內疚語氣、不另開行銷用途。
- DESIGN.md 未提及:(a)預覽隱藏時的通用文字 placeholder([notifications](https://developer.apple.com/design/human-interface-guidelines/notifications));(b)interruption level——Vocaby 屬 Active 或 Passive 皆合理,不應使用 Time Sensitive([managing-notifications](https://developer.apple.com/design/human-interface-guidelines/managing-notifications));(c)app 在 foreground 時的處理;(d)排程前檢查授權狀態([Asking permission](https://developer.apple.com/documentation/usernotifications/asking-permission-to-use-notifications));(e)不要對同一件事重複提醒([notifications](https://developer.apple.com/design/human-interface-guidelines/notifications))。
- DESIGN.md 範例英文「Today's 10 expression upgrades are ready.」有句號、為完整句,符合 HIG 的 sentence case 與標點建議;zh-Hant 範例省略句號,中文標點慣例不在 HIG 範圍。

### 3.10 [確認] Layout 數值與 size classes

- DESIGN.md 寫「16 pt compact、24 pt regular」「iPad 最大 640 pt 置中」。HIG 建議依 size classes 而非裝置類型 / 方向做決策,並使用系統提供的 margins / layout guides([layout](https://developer.apple.com/design/human-interface-guidelines/layout))。建議:實作時以系統 margins 與 readable content width 為準,640 pt 以 size class 判斷而非 `userInterfaceIdiom`。
- 間距:HIG 建議有 bezel 的元素周圍約 12 pt、無 bezel 約 24 pt([accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility))。DESIGN.md 的 spacing scale 含 12 / 24 但未對應此準則;quiz option 之間的間距、相鄰小按鈕(如發音 / 收藏)值得檢查。
- 44 pt 觸控目標:DESIGN.md 的「至少 44x44」比 HIG 的最小值(28x28)嚴格,與預設值(44x44)一致([accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)、[buttons](https://developer.apple.com/design/human-interface-guidelines/buttons)),無問題。
- 圓角:DESIGN.md 固定 8 / 12 / 16 pt。HIG 對 bar 上的自訂元件要求與 bar 圓角同心([toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars)),一般內容區的卡片圓角則沒有硬性規範。

### 3.11 [確認] Settings、Sheet 與 toolbar

- DESIGN.md 在 Home 與 My 各有 Settings 入口,並以 sheet 呈現。HIG:sheet 若有 Done 要搭配 Cancel 或 Back([sheets](https://developer.apple.com/design/human-interface-guidelines/sheets))——Settings sheet 的按鈕組合需對照。
- HIG 建議使用標準 Back / Close 符號([toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars)),且 toolbar title 簡短(原文約 15 字元以內);「Home」「Learn」等符合。
- Settings 內容:HIG 建議把任務專屬選項(如 quiz 題型 / 計時)放在任務畫面內而非全域設定([settings](https://developer.apple.com/design/human-interface-guidelines/settings))——DESIGN.md 已把 Quiz configuration 放在 Practice,方向一致。
- 一致處:沒有 app 專屬的外觀(Dark Mode)選項,對應 [dark-mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode) 的「避免」;通知被拒時顯示導向系統設定的路徑,對應 [settings](https://developer.apple.com/design/human-interface-guidelines/settings) 與 [writing](https://developer.apple.com/design/human-interface-guidelines/writing)。
- [缺漏] 隱私政策連結:審核 5.1.1(i) 要求 app 內以易於存取的方式提供([guidelines](https://developer.apple.com/app-store/review/guidelines/)),DESIGN.md 的 Settings 規格未列出。

### 3.12 [確認] Empty states

- DESIGN.md 要求 empty state「有下一步或有用的說明」(二選一),HIG 傾向「給出明確下一步,盡可能附按鈕或連結」([writing](https://developer.apple.com/design/human-interface-guidelines/writing))。「今天完成了」搭配「subtle next-review hint」屬說明,可評估補上動作(例如進入 Practice)。
- 與 HIG 一致處:tab 內容為空時保留 tab 並說明原因([tab-bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars))。

### 3.13 [確認] 圖表無障礙

- DESIGN.md 已要求等價文字摘要。HIG 進一步建議圖表有標題與摘要、並考慮 Audio Graphs,label 描述資料意義而非顏色([charts](https://developer.apple.com/design/human-interface-guidelines/charts)、[voiceover](https://developer.apple.com/design/human-interface-guidelines/voiceover))。15 週 heatmap 的五個等級若僅靠色階差異,色盲使用者難以分辨,需有數字 / 文字替代。

### 3.14 [缺漏] App icon、Launch screen 與 Localization 細項

- App icon:DESIGN.md 完全沒有規範。依 HIG 需準備 default / dark / tinted 變體、圖層化、避免文字([app-icons](https://developer.apple.com/design/human-interface-guidelines/app-icons))。品牌漸層 Accent→BrandTeal 作為 icon 背景時需通過系統光影測試。
- Launch screen:不含文字、與首屏近似([launching](https://developer.apple.com/design/human-interface-guidelines/launching));並應還原上次畫面狀態。
- Localization:DESIGN.md 已涵蓋 pseudo-long string QA、zh-Hant / English 與內容語言分離,與 HIG 方向一致。未涵蓋:日期 / 數字 / 時間格式依 locale 與 region([inclusion](https://developer.apple.com/design/human-interface-guidelines/inclusion))、string catalog 與給譯者的 comment([Preparing views for localization](https://developer.apple.com/documentation/swiftui/preparing-views-for-localization))、App Store Connect 的中繼資料本地化([Localization](https://developer.apple.com/documentation/xcode/localization))、以及「紅 / 綠」答題色在不同文化的語意([color](https://developer.apple.com/design/human-interface-guidelines/color))——DESIGN.md 已用 icon / 文字輔助,風險低。
- SF Symbols:使用方式與 HIG 一致;若品牌漸層要套在 symbol 上,SF Symbols 7+ 有原生 gradient 渲染可評估([sf-symbols](https://developer.apple.com/design/human-interface-guidelines/sf-symbols))。

### 3.15 一致、無需動作的項目(快速對照)

- 原生 TabView + 各 tab 獨立 NavigationStack;toolbar 放動作。
- 系統字型 / text styles / 不內嵌字型 / 避免固定字級 / 避免截斷。
- 系統背景與 label 色、不另設 app 外觀開關、dark mode 以系統色優先。
- 不單靠顏色(答題狀態含 icon / 文字)。
- 觸控目標 44x44、手勢有等價按鈕、Reduce Motion 以 fade 取代。
- 通知 / widget 文案不含敏感資訊;SF Symbols 用於 toolbar / tab icon。
- 權限被拒時仍可使用 app 並提供去系統設定的路徑(對應審核 5.1.1(iv))。

---

## 4. 備註:對比計算方法

使用 WCAG 2.x 相對亮度公式,sRGB 線性化後以 (L1+0.05)/(L2+0.05) 計算,L1 為較亮者。此為研究者自行計算,不是 Apple 官方數值。HIG 的 Accessibility 頁指出 Accessibility Inspector 以 WCAG AA 數值作為判斷依據,故門檻值可對應,但最終應以 Accessibility Inspector 於實機畫面測得為準。

---

## 5. 未能確認的事項

1. **iOS 導覽列(Navigation bar / large title)細則**:`navigation-bars` 頁面的 JSON 端點回傳 404,`navigation-and-search` 頁僅為主題索引、沒有正文。因此 NavigationStack 的 large title 行為、導覽列規範未能從 HIG 直接確認(toolbar 頁面內有導覽與標題的段落,已引用)。
2. **Empty states 與 Localization 專頁**:HIG 目錄中查無獨立頁面,上文所述皆來自 Writing / Inclusion / Right to left 與 Xcode 文件的相關段落,而非專頁。
3. **Notifications 權限前置畫面的規範範圍**:privacy 頁的「單一按鈕、不可取消、不用 Allow」規範,原文列舉的資源類型為 camera、microphone、location、contact、calendar、tracking;是否涵蓋本地通知權限,本研究無法從原文確認。
4. **SwiftUI TabView 是否自動為選取態套用 filled 符號變體**:HIG 說偏好 filled,但未從官方文件取得 SwiftUI 的具體行為,需在實機或透過 `symbolVariant` 文件確認。
5. **`tabBarMinimizeBehavior` 的行為細節**:官方頁面僅給出摘要(「Never minimize the tab bar」),沒有說明在無 accessory 時系統預設是否 minimize;DESIGN.md 明確設為 `.never` 屬保守作法,不影響結論。
6. **HIG Haptics 頁的 iOS 專屬段落、Widgets 頁的 Specifications(各機型 widget 尺寸表)**:僅讀取了通則與標準邊界,未逐一核對各尺寸點數;`dynamic type` 的 AX 尺寸表與 xSmall–xxxLarge 之外的資料也未引用。
7. **Alerts、Search fields、Lists and tables、Progress indicators 等頁**:已下載,但僅作為輔助檢索(例如 progress indicators 偏好 determinate),本文沒有逐條列入;DESIGN.md 未涉及 alert 規範,若後續要做刪除 / 重設進度的確認流程,需另行閱讀 [alerts](https://developer.apple.com/design/human-interface-guidelines/alerts)。
8. **Accessibility Nutrition Labels 的具體要求**:HIG 僅提及並連到 App Store Connect 說明頁,該頁未納入本次研究。
9. **App Store Review Guidelines 的適用性判斷**:4.5.4 條文針對「Push Notifications」;Vocaby 使用本地通知,是否同樣受此條約束,條文未明講,文中只引用其精神。
10. **觸控目標在 SwiftUI 的實作細節**(例如 `contentShape`、最小高度):本研究僅涵蓋 HIG 數值,未讀取相關 SwiftUI 文件。
