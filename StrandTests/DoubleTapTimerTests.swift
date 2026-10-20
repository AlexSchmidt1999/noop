import XCTest
import Combine
@testable import Strand

@MainActor
final class DoubleTapTimerTests: XCTestCase {
    func testStartWarningAndFinishAreEachSentOnce() {
        var buzzes: [UInt8] = []
        let timer = DoubleTapTimer(buzz: { buzzes.append($0) })
        let now = ContinuousClock.now
        timer.start(minutes: 5, now: now)
        XCTAssertEqual(timer.remaining(now: now), 300)
        XCTAssertEqual(buzzes, [1])
        timer.advance(now: now.advanced(by: .seconds(269)))
        XCTAssertEqual(buzzes, [1])
        timer.advance(now: now.advanced(by: .seconds(270)))
        timer.advance(now: now.advanced(by: .seconds(271)))
        XCTAssertEqual(buzzes, [1, 1])
        timer.advance(now: now.advanced(by: .seconds(300)))
        timer.advance(now: now.advanced(by: .seconds(301)))
        XCTAssertEqual(buzzes, [1, 1, 2])
        XCTAssertEqual(timer.state, .finished)
        XCTAssertNil(timer.remaining(now: now))
    }

    func testRestartDiscardsOldDeadlinesAndRestoresFullDuration() {
        var buzzes: [UInt8] = []
        let timer = DoubleTapTimer(buzz: { buzzes.append($0) })
        let now = ContinuousClock.now
        timer.start(minutes: 5, now: now)
        timer.advance(now: now.advanced(by: .seconds(270)))
        let restart = now.advanced(by: .seconds(280))
        timer.start(minutes: 5, now: restart)
        XCTAssertEqual(timer.remaining(now: restart), 300)
        timer.advance(now: now.advanced(by: .seconds(300)))
        XCTAssertEqual(buzzes, [1, 1, 1])
        timer.advance(now: restart.advanced(by: .seconds(270)))
        timer.advance(now: restart.advanced(by: .seconds(300)))
        XCTAssertEqual(buzzes, [1, 1, 1, 1, 2])
    }

    func testStopAndDisconnectDiscardPendingCues() {
        for disconnected in [false, true] {
            var buzzes: [UInt8] = []
            let timer = DoubleTapTimer(buzz: { buzzes.append($0) })
            let now = ContinuousClock.now
            timer.start(minutes: 1, now: now)
            timer.stop(disconnected: disconnected)
            timer.advance(now: now.advanced(by: .seconds(30)))
            timer.advance(now: now.advanced(by: .seconds(60)))
            XCTAssertEqual(buzzes, [1])
            XCTAssertEqual(timer.state, disconnected ? .disconnected : .idle)
        }
    }

    func testLateWakeFinishesWithoutReplayingWarning() {
        var buzzes: [UInt8] = []
        let timer = DoubleTapTimer(buzz: { buzzes.append($0) })
        let now = ContinuousClock.now
        timer.start(minutes: 1, now: now)
        timer.advance(now: now.advanced(by: .seconds(90)))
        XCTAssertEqual(buzzes, [1, 2])
        XCTAssertEqual(timer.state, .finished)
    }

    func testScheduledDeadlineFinishesWithoutAViewOrBluetoothTick() {
        let finished = expectation(description: "Scheduled completion")
        var buzzes: [UInt8] = []
        let timer = DoubleTapTimer(buzz: {
            buzzes.append($0)
            if $0 == 2 { finished.fulfill() }
        })
        timer.start(minutes: 1, now: ContinuousClock.now.advanced(by: .seconds(-61)))
        wait(for: [finished], timeout: 5)
        XCTAssertEqual(buzzes, [1, 2])
        XCTAssertEqual(timer.state, .finished)
    }

    func testDurationBoundsAndFractionalSeconds() {
        for (minutes, expected) in [(Int.min, 60), (1, 60), (5, 300), (60, 3600), (Int.max, 3600)] {
            let timer = DoubleTapTimer(buzz: { _ in })
            let now = ContinuousClock.now
            timer.start(minutes: minutes, now: now)
            XCTAssertEqual(timer.remaining(now: now), expected)
            XCTAssertEqual(timer.remaining(now: now.advanced(by: .milliseconds(1))), expected)
            XCTAssertEqual(timer.remaining(now: now.advanced(by: .seconds(1))), expected - 1)
            timer.stop()
        }
    }

    func testBluetoothWakesDoNotPublishATickToEveryScreen() {
        let timer = DoubleTapTimer(buzz: { _ in })
        let now = ContinuousClock.now
        timer.start(minutes: 5, now: now)
        var changes = 0
        let subscription = timer.objectWillChange.sink { changes += 1 }
        for second in 1...299 {
            timer.advance(now: now.advanced(by: .seconds(second)))
        }
        XCTAssertEqual(changes, 0)
        timer.advance(now: now.advanced(by: .seconds(300)))
        XCTAssertEqual(changes, 1)
        subscription.cancel()
    }
}
