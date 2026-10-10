import XCTest
import WhoopStore
@testable import Strand

@MainActor
final class LiftSessionHistoryLoadingTests: XCTestCase {
    func testAddingAnExerciseLoadsItsPreviousSets() async throws {
        let store = try await WhoopStore(path: ":memory:")
        let repo = Repository(deviceId: "history-test", store: store)
        let controller = LiftSessionController(buzz: { _ in }, setStrapHandler: { _ in })
        defer { controller.discard() }
        let start = Int(Date().timeIntervalSince1970) - 3_600
        _ = try await store.upsertLiftSessions([
            .init(id: "previous", deviceId: repo.deviceId, startTs: start, endTs: start + 600,
                  sport: "Strength", programId: nil, programName: nil, sessionRpe: nil, note: nil)
        ])
        _ = try await store.upsertLiftSets([
            .init(id: "previous-fly", deviceId: repo.deviceId, sessionId: "previous", ord: 0,
                  exercise: "Cable fly", primaryMuscle: .chest, setIndex: 1, weightKg: 15, reps: 12,
                  rpe: nil, isWarmup: false, startTs: start, endTs: start + 30, restSec: 60, note: nil)
        ])
        controller.start(plan: [.init(exercise: "Bench press")], programId: nil, programName: nil)
        await controller.loadLastSession(repo: repo)
        XCTAssertTrue(controller.addExercise("Cable fly", primaryMuscle: .chest, secondaryMuscles: []))
        await controller.loadLastSession(repo: repo)
        XCTAssertEqual(controller.carry(for: .init(exerciseIndex: 1, setIndex: 1)),
                       LiftSetCarry(weightKg: 15, reps: 12))
    }
}
