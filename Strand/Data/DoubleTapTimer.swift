import Foundation
import Combine

/// Owned by the app, so dismissing its controls cannot cancel the strap's timer.
@MainActor
final class DoubleTapTimer: ObservableObject {
    static let minutesKey = "ios.doubleTapTimer.minutes"
    static let defaultMinutes = 5
    static let minutesRange = 1...60

    enum State: Equatable {
        case idle
        case running(until: ContinuousClock.Instant)
        case finished
        case disconnected
    }

    @Published private(set) var state: State = .idle
    private var warned = false
    private var cues: Task<Void, Never>?
    private let buzz: (UInt8) -> Void
    private let log: (String) -> Void

    init(buzz: @escaping (UInt8) -> Void, log: @escaping (String) -> Void = { _ in }) {
        self.buzz = buzz
        self.log = log
    }

    deinit { cues?.cancel() }

    func start(minutes: Int, now: ContinuousClock.Instant = .now) {
        cues?.cancel()
        let seconds = min(max(minutes, Self.minutesRange.lowerBound), Self.minutesRange.upperBound) * 60
        let end = now.advanced(by: .seconds(seconds))
        state = .running(until: end)
        warned = false
        buzz(1)
        log("Double-tap timer: started for \(seconds) s; start cue requested")
        // shortcut: iOS may suspend scheduled work; BLE notifications also advance the timer. Verify on a locked iPhone.
        cues = Task { [weak self] in
            do {
                for deadline in [end.advanced(by: .seconds(-30)), end] {
                    try await ContinuousClock().sleep(until: deadline)
                    try Task.checkCancellation()
                    self?.advance()
                }
            } catch { } // Cancellation discards the old timer's cues on restart or stop.
        }
    }

    /// Uses elapsed time, including device sleep, rather than counting callbacks or reading wall time.
    func remaining(now: ContinuousClock.Instant = .now) -> Int? {
        guard case .running(let end) = state else { return nil }
        let parts = now.duration(to: end).components
        return max(0, Int(parts.seconds) + (parts.attoseconds > 0 ? 1 : 0))
    }

    func advance(now: ContinuousClock.Instant = .now) {
        guard case .running(let end) = state else { return }
        if now >= end {
            state = .finished
            cues?.cancel()
            cues = nil
            buzz(2)
            log("Double-tap timer: elapsed; finish cue requested (late by \(end.duration(to: now)))")
        } else if !warned, now.duration(to: end) <= .seconds(30) {
            warned = true
            buzz(1)
            log("Double-tap timer: warning cue requested (\(remaining(now: now) ?? 0) s remaining)")
        }
    }

    func stop(disconnected: Bool = false) {
        cues?.cancel()
        cues = nil
        if case .running = state {
            log(disconnected ? "Double-tap timer: stopped after connection loss; pending cues discarded"
                             : "Double-tap timer: stopped; pending cues discarded")
            state = disconnected ? .disconnected : .idle
        }
    }
}
