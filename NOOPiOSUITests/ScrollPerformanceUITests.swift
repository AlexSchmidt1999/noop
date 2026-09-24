import XCTest

/// Replays the same touch path on a paired iPhone while Instruments records the app.
/// Each test keeps the existing on-device data and only navigates and scrolls.
final class ScrollPerformanceUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    func testTodayScroll() {
        let app = activate()
        app.tabBars.buttons["Today"].tap()
        scroll(app.scrollViews.firstMatch)
    }

    func testTrendsScroll() {
        let app = activate()
        app.tabBars.buttons["Trends"].tap()
        scroll(app.scrollViews.firstMatch)
    }

    func testInsightsScroll() {
        let app = activate()
        app.tabBars.buttons["More"].tap()
        let insights = app.buttons["Insights"].firstMatch
        XCTAssertTrue(insights.waitForExistence(timeout: 10))
        insights.tap()
        scroll(app.scrollViews.firstMatch)
    }

    private func activate() -> XCUIApplication {
        let app = XCUIApplication()
        // Keep the app process alive across repetitions so traces cover scrolling,
        // not three separate cold starts and their unrelated launch animations.
        app.activate()
        XCTAssertTrue(app.tabBars.buttons["Today"].waitForExistence(timeout: 30),
                      "Complete NOOP's first-run screens before profiling")
        return app
    }

    private func scroll(_ view: XCUIElement) {
        XCTAssertTrue(view.waitForExistence(timeout: 10))
        let low = view.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.88))
        let high = view.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.12))
        for _ in 0..<3 {
            // Cross several sections before returning. Alternating each gesture only
            // exercised the first card and never reached off-screen charts.
            for _ in 0..<3 { low.press(forDuration: 0.05, thenDragTo: high) }
            for _ in 0..<3 { high.press(forDuration: 0.05, thenDragTo: low) }
        }
    }
}
