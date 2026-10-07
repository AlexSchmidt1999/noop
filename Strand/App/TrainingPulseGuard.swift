import Foundation

/// Freshness of accepted live samples, independent of the displayed heart-rate value.
struct TrainingPulseGuard: Codable, Equatable {
    static let timeoutSeconds = 600
    static let checkpointSeconds = 30
    var lastSampleSec: Int?
    var recoveryAllowance = 0

    var deadline: Int? {
        let allowance = min(Self.checkpointSeconds, max(0, recoveryAllowance))
        guard let lastSampleSec, lastSampleSec > 0,
              lastSampleSec <= Int.max - Self.timeoutSeconds - allowance - Self.checkpointSeconds else { return nil }
        return lastSampleSec + Self.timeoutSeconds + allowance
    }
    func isDue(at now: Int) -> Bool { deadline.map { now >= $0 } ?? false }
    mutating func receive(at now: Int) { lastSampleSec = now; recoveryAllowance = 0 }
    mutating func resume(at now: Int) { if lastSampleSec != nil { receive(at: now) } }
    // A checkpoint can lag receipt by 30 seconds. Never pause early after a process restart.
    var checkpoint: Self { var copy = self; copy.recoveryAllowance = Self.checkpointSeconds; return copy }
}
