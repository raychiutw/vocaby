// AUTO-GENERATED from gstack/ios-qa/templates/Bridges.swift.template
//
// Real UIKit-backed implementations of the three bridges StateServer
// declares: ScreenshotBridge (PNG capture), ElementsBridge (accessibility
// tree), MutationBridge (tap/swipe/type via accessibility actions + hit
// testing). Everything #if DEBUG && canImport(UIKit) so Release builds
// don't link UIKit or carry any of this code.
//
// Wire from the consuming app:
//
//   #if DEBUG && canImport(UIKit)
//   import DebugBridgeUI
//   DebugBridgeUIWiring.installAll()
//   #endif

#if DEBUG && canImport(UIKit)

import DebugBridgeCore
import DebugBridgeTouch
import Foundation
import SwiftUI
import UIKit

@MainActor
public enum DebugBridgeUIWiring {
    /// Install all three bridge resolvers. Idempotent — calling multiple
    /// times reinstalls the same closures. Must be called on @MainActor
    /// because every UIKit access requires the main actor.
    public static func installAll() {
        ScreenshotBridge.resolver = { ScreenshotBridgeImpl.capturePNG() }
        ElementsBridge.resolver = { ElementsBridgeImpl.snapshot() }
        MutationBridge.resolver = { op, payload in MutationBridgeImpl.dispatch(op: op, payload: payload) }
    }
}

// MARK: - ScreenshotBridge implementation

@MainActor
enum ScreenshotBridgeImpl {
    /// Capture a PNG of the active window. Uses UIGraphicsImageRenderer
    /// (modern API, replaces UIGraphicsBeginImageContext). Returns nil if
    /// no key window is available (e.g., app backgrounded).
    static func capturePNG() -> Data? {
        guard let scene = activeScene(), let window = activeKeyWindow(in: scene) else { return nil }
        let bounds = window.bounds
        let renderer = UIGraphicsImageRenderer(bounds: bounds)
        let image = renderer.image { _ in
            // drawHierarchy is the documented way to snapshot real UIKit
            // layers including layer-backed views. afterScreenUpdates: false
            // because we want the CURRENT visible state, not a forced layout.
            window.drawHierarchy(in: bounds, afterScreenUpdates: false)
        }
        return image.pngData()
    }

    private static func activeScene() -> UIWindowScene? {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }
            ?? (UIApplication.shared.connectedScenes.first as? UIWindowScene)
    }

    private static func activeKeyWindow(in scene: UIWindowScene) -> UIWindow? {
        scene.windows.first(where: { $0.isKeyWindow }) ?? scene.windows.first
    }
}

// MARK: - ElementsBridge implementation

@MainActor
enum ElementsBridgeImpl {
    private static let maxElementCount = 2_000

    /// Walk the UIKit view hierarchy + emit a flat list of accessible elements.
    /// Each entry has frame (in window coords), accessibility label,
    /// identifier, traits as a bitmask, and a parent path. Skips
    /// non-accessible / hidden views.
    static func snapshot() -> [JSONDict] {
        guard let scene = activeScene(), let window = activeKeyWindow(in: scene) else { return [] }
        var elements: [JSONDict] = []
        var visitedViews: Set<ObjectIdentifier> = []
        collect(
            view: window,
            parentPath: "",
            windowBounds: window.bounds,
            visitedViews: &visitedViews,
            into: &elements
        )
        return elements
    }

    private static func collect(
        view: UIView,
        parentPath: String,
        windowBounds: CGRect,
        visitedViews: inout Set<ObjectIdentifier>,
        into elements: inout [JSONDict]
    ) {
        guard elements.count < maxElementCount else { return }
        guard visitedViews.insert(ObjectIdentifier(view)).inserted else { return }

        // Skip hidden / zero-size / off-screen subtrees early.
        if view.isHidden || view.alpha < 0.01 { return }

        let frameInWindow = view.convert(view.bounds, to: nil)
        if !windowBounds.intersects(frameInWindow) { return }

        let isAccessible = view.isAccessibilityElement
        let label = view.accessibilityLabel ?? ""
        let identifier = view.accessibilityIdentifier ?? ""
        let traits = Int(view.accessibilityTraits.rawValue)
        let value = (view.accessibilityValue ?? "") as String
        let className = String(describing: type(of: view))
        let path = parentPath.isEmpty ? className : "\(parentPath) > \(className)"

        // Emit if any of:
        //   - Marked accessible (covers UIKit-native widgets)
        //   - Has explicit AX label / identifier
        //   - Is a known interactive type (UIControl, UITextField, UIScrollView)
        //   - Hosts a SwiftUI view (UIHostingController's view class)
        let isInteractive = view is UIControl || view is UIScrollView || view is UITextInput
        let isHosting = className.contains("Hosting") || className.contains("SwiftUI")
        if isAccessible || !label.isEmpty || !identifier.isEmpty || isInteractive || isHosting {
            elements.append([
                "path": path,
                "class": className,
                "label": label,
                "identifier": identifier,
                "value": value,
                "traits": traits,
                "frame": [
                    "x": Int(frameInWindow.origin.x),
                    "y": Int(frameInWindow.origin.y),
                    "w": Int(frameInWindow.size.width),
                    "h": Int(frameInWindow.size.height),
                ],
                "is_user_interaction_enabled": view.isUserInteractionEnabled,
            ])
        }

        // Read already-materialized synthetic children when available, but do
        // not force SwiftUI to create them with accessibilityElementCount().
        // That synchronous call can block the main thread while SwiftUI is
        // updating its accessibility tree.
        if let accessibilityElements = view.accessibilityElements {
            for case let element as NSObject in accessibilityElements {
                guard elements.count < maxElementCount else { break }
                if let childView = element as? UIView {
                    collect(
                        view: childView,
                        parentPath: path,
                        windowBounds: windowBounds,
                        visitedViews: &visitedViews,
                        into: &elements
                    )
                    continue
                }

                let frame = element.accessibilityFrame
                elements.append([
                    "path": "\(path) > <synthetic>",
                    "class": String(describing: type(of: element)),
                    "label": element.accessibilityLabel ?? "",
                    "identifier": (element as? UIAccessibilityIdentification)?.accessibilityIdentifier ?? "",
                    "value": element.accessibilityValue ?? "",
                    "traits": Int(element.accessibilityTraits.rawValue),
                    "frame": [
                        "x": Int(frame.origin.x),
                        "y": Int(frame.origin.y),
                        "w": Int(frame.size.width),
                        "h": Int(frame.size.height),
                    ],
                    "is_user_interaction_enabled": true,
                ])
            }
        }

        for sub in view.subviews {
            collect(
                view: sub,
                parentPath: path,
                windowBounds: windowBounds,
                visitedViews: &visitedViews,
                into: &elements
            )
        }
    }

    private static func activeScene() -> UIWindowScene? {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }
            ?? (UIApplication.shared.connectedScenes.first as? UIWindowScene)
    }

    private static func activeKeyWindow(in scene: UIWindowScene) -> UIWindow? {
        scene.windows.first(where: { $0.isKeyWindow }) ?? scene.windows.first
    }
}

// MARK: - MutationBridge implementation

@MainActor
enum MutationBridgeImpl {
    /// Route a mutation op to the right handler. Returns true on success,
    /// false on failure (which the StateServer surfaces as 400 to the agent).
    static func dispatch(op: String, payload: JSONDict) -> Bool {
        switch op {
        case "tap":     return handleTap(payload)
        case "type":    return handleType(payload)
        case "swipe":   return handleSwipe(payload)
        default:        return false
        }
    }

    /// Tap at (x, y) in window coordinates. Delegates to DebugBridgeTouch
    /// (KIF-derived in-process touch synthesis). The Obj-C target builds a
    /// real UITouch + IOHIDEvent + UIEvent and dispatches via
    /// `UIApplication.sendEvent`, which is what UIKit uses for real touches.
    /// This works for UIControl, SwiftUI Button (via iOS 18+
    /// `_UIHitTestContext`), gesture recognizers, and anything else that
    /// listens to the real event-dispatch path.
    private static func handleTap(_ payload: JSONDict) -> Bool {
        guard let x = payload["x"] as? NSNumber,
              let y = payload["y"] as? NSNumber else { return false }
        let point = CGPoint(x: x.doubleValue, y: y.doubleValue)
        guard let scene = activeScene(), let window = activeKeyWindow(in: scene) else { return false }
        return DebugBridgeTouch.sendTap(at: point, in: window)
    }

    /// Set text on the first responder if it's a UITextField or UITextView.
    private static func handleType(_ payload: JSONDict) -> Bool {
        guard let text = payload["text"] as? String else { return false }
        guard let scene = activeScene(), let window = activeKeyWindow(in: scene) else { return false }
        guard let responder = findFirstResponder(in: window) else { return false }
        if let field = responder as? UITextField {
            field.text = text
            field.sendActions(for: .editingChanged)
            return true
        }
        if let view = responder as? UITextView {
            view.text = text
            view.delegate?.textViewDidChange?(view)
            return true
        }
        return false
    }

    /// Swipe via UIScrollView programmatic scroll OR via setContentOffset on
    /// the deepest UIScrollView in the hit-tested ancestor chain. Less
    /// faithful than synthesized touches but covers common scroll scenarios.
    private static func handleSwipe(_ payload: JSONDict) -> Bool {
        guard let fx = payload["from_x"] as? NSNumber,
              let fy = payload["from_y"] as? NSNumber,
              let tx = payload["to_x"] as? NSNumber,
              let ty = payload["to_y"] as? NSNumber else { return false }
        let from = CGPoint(x: fx.doubleValue, y: fy.doubleValue)
        let to = CGPoint(x: tx.doubleValue, y: ty.doubleValue)

        guard let scene = activeScene(), let window = activeKeyWindow(in: scene) else { return false }
        guard let hit = window.hitTest(from, with: nil) else { return false }

        // Find the nearest enclosing UIScrollView.
        var node: UIView? = hit
        while let cur = node {
            if let scroll = cur as? UIScrollView {
                let dx = from.x - to.x
                let dy = from.y - to.y
                var off = scroll.contentOffset
                off.x = max(0, min(scroll.contentSize.width - scroll.bounds.width, off.x + dx))
                off.y = max(0, min(scroll.contentSize.height - scroll.bounds.height, off.y + dy))
                scroll.setContentOffset(off, animated: true)
                return true
            }
            node = cur.superview
        }
        return false
    }

    // MARK: helpers

    private static func walkUp(_ view: UIView) -> UIView? {
        var node: UIView? = view
        while let cur = node {
            if cur is UIControl { return cur }
            node = cur.superview
        }
        return view
    }

    private static func findFirstResponder(in view: UIView) -> UIResponder? {
        if view.isFirstResponder { return view }
        for sub in view.subviews {
            if let found = findFirstResponder(in: sub) { return found }
        }
        return nil
    }

    private static func activeScene() -> UIWindowScene? {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }
            ?? (UIApplication.shared.connectedScenes.first as? UIWindowScene)
    }

    private static func activeKeyWindow(in scene: UIWindowScene) -> UIWindow? {
        scene.windows.first(where: { $0.isKeyWindow }) ?? scene.windows.first
    }
}

#endif // DEBUG && canImport(UIKit)
