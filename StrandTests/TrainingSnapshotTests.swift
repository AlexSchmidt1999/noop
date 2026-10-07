import XCTest

final class TrainingSnapshotTests: XCTestCase {
    func testEndConfirmationIsBoundToTheSessionTokenAndThirtySeconds() {
        let now = Date(timeIntervalSince1970: 1_000)
        let confirmation = TrainingEndConfirmation(sessionID: "first", now: now)
        XCTAssertTrue(confirmation.accepts(sessionID: "first", token: confirmation.token, now: now.addingTimeInterval(29)))
        XCTAssertFalse(confirmation.accepts(sessionID: "second", token: confirmation.token, now: now))
        XCTAssertFalse(confirmation.accepts(sessionID: "first", token: "old", now: now))
        XCTAssertFalse(confirmation.accepts(sessionID: "first", token: confirmation.token, now: now.addingTimeInterval(30)))
    }

    func testThreeFavoritesRoundTripAndRejectCorruptSlots() throws {
        let suite = "training-tests-\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        var favorites = TrainingFavorite.load(from: defaults)
        XCTAssertEqual(favorites.count, 3)
        XCTAssertEqual(favorites[0].sport, "Strength")
        XCTAssertEqual(favorites[1].sport, "Running")
        XCTAssertNil(favorites[2].sport)
        favorites[2] = .init(id: 2, name: "Upper A", programID: "p")
        TrainingFavorite.save(favorites, into: defaults)
        XCTAssertEqual(TrainingFavorite.load(from: defaults), favorites)
        TrainingFavorite.save(Array(favorites.prefix(2)), into: defaults)
        XCTAssertEqual(TrainingFavorite.load(from: defaults), favorites)
        defaults.set(Data("[{\"id\":999,\"name\":\"x\"}]".utf8), forKey: TrainingFavorite.storageKey)
        XCTAssertEqual(TrainingFavorite.load(from: defaults), TrainingFavorite.defaults)
    }
}
