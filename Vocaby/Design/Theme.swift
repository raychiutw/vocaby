import SwiftUI

enum AppTheme {
    static let accent = Color("Accent")
    static let prominentInk = Color("ProminentInk")
    static let accentSoft = Color("AccentSoft")
    static let focusInk = Color("FocusInk")
    static let mutedInk = Color("MutedInk")
    static let reviewAmber = Color("ReviewAmber")
    static let wrongRed = Color("WrongRed")
    static let correctGreen = Color("CorrectGreen")
    static let brandTeal = Color("BrandTeal")
    static let brandGradient = LinearGradient(
        colors: [accent, brandTeal],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
}
