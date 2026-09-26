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
        let section = app.buttons["Insights"].firstMatch
        reveal(section, in: app.scrollViews.firstMatch)
        if (section.value as? String) == "Collapsed" { section.tap() }
        let insights = app.buttons.matching(identifier: "Insights").element(boundBy: 1)
        XCTAssertTrue(insights.waitForExistence(timeout: 10))
        reveal(insights, in: app.scrollViews.firstMatch)
        insights.tap()
        scroll(app.scrollViews.firstMatch)
    }

    func testChartScreensCapture() {
        let app = activate()
        openTestCentre(app, selectMore: true)
        let record = app.buttons["Record 30 minutes"]
        reveal(record, in: app.scrollViews.firstMatch)
        XCTAssertTrue(record.isEnabled)
        record.tap()
        backToMore(app)

        app.tabBars.buttons["Today"].tap()
        scroll(app.scrollViews.firstMatch)
        app.tabBars.buttons["Trends"].tap()
        scroll(app.scrollViews.firstMatch)
        app.tabBars.buttons["More"].tap()
        let section = app.buttons["Insights"].firstMatch
        reveal(section, in: app.scrollViews.firstMatch)
        if (section.value as? String) == "Collapsed" { section.tap() }
        let insights = app.buttons.matching(identifier: "Insights").element(boundBy: 1)
        reveal(insights, in: app.scrollViews.firstMatch)
        insights.tap()
        scroll(app.scrollViews.firstMatch)
        backToMore(app)

        openTestCentre(app, selectMore: false)
        let stop = app.buttons["Stop recording"]
        reveal(stop, in: app.scrollViews.firstMatch)
        stop.tap()
        XCTAssertTrue(app.buttons["Review performance report"].waitForExistence(timeout: 5))
    }

    func testSettingsScroll() {
        let app = activate()
        openTestCentre(app, selectMore: true)
        let record = app.buttons["Record 30 minutes"]
        reveal(record, in: app.scrollViews.firstMatch)
        XCTAssertTrue(record.isEnabled)
        record.tap()
        backToMore(app)
        app.tabBars.buttons["More"].tap()
        let section = app.buttons["App"]
        reveal(section, in: app.scrollViews.firstMatch)
        let settings = app.buttons["Settings"]
        if !settings.exists { section.tap() }
        reveal(settings, in: app.scrollViews.firstMatch)
        settings.tap()
        inspectSettings(app)
        backToMore(app)
        openTestCentre(app, selectMore: false)
        let stop = app.buttons["Stop recording"]
        reveal(stop, in: app.scrollViews.firstMatch)
        stop.tap()
    }

    func testLocalPerformanceReport() throws {
        let app = activate()
        openTestCentre(app, selectMore: true)

        let record = app.buttons["Record 30 minutes"]
        reveal(record, in: app.scrollViews.firstMatch)
        if !record.isEnabled { throw XCTSkip("Turn off Display & Performance test mode first") }
        record.tap()
        let stop = app.buttons["Stop recording"]
        XCTAssertTrue(stop.waitForExistence(timeout: 5))
        stop.tap()
        let review = app.buttons["Review performance report"]
        XCTAssertTrue(review.waitForExistence(timeout: 5))
        review.tap()
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", "session_start")).firstMatch
            .waitForExistence(timeout: 5))
        app.buttons["Done"].tap()
    }

    func testStopPerformanceReport() throws {
        let app = activate()
        openTestCentre(app, selectMore: true)
        let stop = app.buttons["Stop recording"]
        if !stop.exists { throw XCTSkip("No performance capture is running") }
        reveal(stop, in: app.scrollViews.firstMatch)
        stop.tap()
        XCTAssertTrue(app.buttons["Review performance report"].waitForExistence(timeout: 5))
    }

    /// Read-only sweep of every iPhone More destination, including the full Settings page.
    /// The Test Centre's optional local capture can remain active throughout this test.
    func testEveryMenuScroll() {
        let app = activate()
        openTestCentre(app, selectMore: true)
        let record = app.buttons["Record 30 minutes"]
        reveal(record, in: app.scrollViews.firstMatch)
        XCTAssertTrue(record.isEnabled, "Turn off Display & Performance test mode first")
        record.tap()
        backToMore(app)

        for tab in ["Today", "Trends", "Sleep", "Coach"] where app.tabBars.buttons[tab].exists {
            XCTContext.runActivity(named: "Tab: \(tab)") { _ in
                app.tabBars.buttons[tab].tap()
                sweep(app.scrollViews.firstMatch, gestures: 2)
            }
        }
        app.tabBars.buttons["More"].tap()
        let sections: [(String, [String])] = [
            ("Insights", ["What Moves You", "Intelligence", "Insights", "Explore", "Compare"]),
            ("Body", ["Live", "Workouts", "Lift Log", "Health", "Lab Book", "Stress", "Breathe", "Intervals", "Rhythm"]),
            ("Data", ["Your Data, Fused", "Apple Health", "Mi Band", "Data Sources", "Backup & Sync", "Shortcuts Export", "NOOP Limitations"]),
            ("App", ["Alarms", "Automations", "Test Centre", "Siri & Shortcuts", "Power saving", "Settings"])
        ]
        for (sectionName, routes) in sections {
            let moreScroll = app.scrollViews.firstMatch
            let header = app.buttons[sectionName].firstMatch
            reveal(header, in: moreScroll)
            let firstRow = app.buttons[routes[0]].firstMatch
            if !firstRow.exists { header.tap() }
            for route in routes {
                XCTContext.runActivity(named: "Menu: \(route)") { _ in
                    let row = route == "Insights" ? app.buttons.matching(identifier: route).element(boundBy: 1) : app.buttons[route].firstMatch
                    reveal(row, in: moreScroll)
                    row.tap()
                    if route == "Settings" {
                        inspectSettings(app)
                    } else {
                        sweep(app.scrollViews.firstMatch, gestures: 2)
                    }
                    backToMore(app)
                }
            }
        }
        openTestCentre(app, selectMore: false)
        let stop = app.buttons["Stop recording"]
        reveal(stop, in: app.scrollViews.firstMatch)
        stop.tap()
        XCTAssertTrue(app.buttons["Review performance report"].waitForExistence(timeout: 5))
    }

    private func openTestCentre(_ app: XCUIApplication, selectMore: Bool) {
        if selectMore { app.tabBars.buttons["More"].tap() }
        let moreScroll = app.scrollViews.firstMatch
        let section = app.buttons["App"]
        reveal(section, in: moreScroll)
        let row = app.buttons["Test Centre"]
        if !row.exists { section.tap() }
        reveal(row, in: moreScroll)
        row.tap()
    }

    private func backToMore(_ app: XCUIApplication) {
        let back = app.buttons["BackButton"]
        XCTAssertTrue(back.waitForExistence(timeout: 10), "No back button in More destination")
        back.tap()
    }

    private func reveal(_ element: XCUIElement, in scrollView: XCUIElement) {
        for _ in 0..<12 where !element.isHittable { scrollView.swipeUp() }
        for _ in 0..<12 where !element.isHittable { scrollView.swipeDown() }
        XCTAssertTrue(element.isHittable, "Could not reach \(element.label)")
    }

    private func inspectSettings(_ app: XCUIApplication) {
        let scroll = app.scrollViews.firstMatch
        for label in ["Reduce motion in NOOP", "Day-cycle background"] {
            let toggle = app.switches[label]
            reveal(toggle, in: scroll)
            guard let original = toggle.value as? String else { XCTFail("No state for \(label)"); continue }
            toggle.tap()
            let changed = toggle.value as? String
            if changed != original { toggle.tap() }
            XCTAssertNotEqual(changed, original, "\(label) did not respond")
            XCTAssertEqual(toggle.value as? String, original, "\(label) was not restored")
        }
        sweep(scroll, gestures: 8)
        let advanced = app.buttons["Advanced"]
        reveal(advanced, in: scroll)
        let wasCollapsed = (advanced.value as? String) == "Collapsed"
        if wasCollapsed { advanced.tap() }
        sweep(scroll, gestures: 12)
        if wasCollapsed {
            for _ in 0..<12 where !advanced.isHittable { scroll.swipeDown() }
            XCTAssertTrue(advanced.isHittable)
            advanced.tap()
        }
    }

    private func sweep(_ view: XCUIElement, gestures: Int) {
        guard view.waitForExistence(timeout: 5) else { return }
        for _ in 0..<gestures { view.swipeUp() }
        for _ in 0..<gestures { view.swipeDown() }
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
