#if os(iOS)
import Combine
import Foundation
import UIKit

/// A bounded, local iPhone performance session. It never sends data or reads health values.
@MainActor
final class PerformanceCapture: ObservableObject {
    static let shared = PerformanceCapture()
    static let duration: TimeInterval = 30 * 60
    private static let prefix = "noop-performance-"
    // A 120 Hz display produces about 3,600 frame summaries in 30 minutes.
    private static let maxLines = 6_000

    @Published private(set) var isRecording = false
    @Published private(set) var reportURL: URL?

    private var startedAt = Date.distantPast
    private var startedUptime: TimeInterval = 0
    private var lines: [String] = []
    private var droppedLines = 0
    private var expiration: Task<Void, Never>?
    private var syncObserver: AnyCancellable?
    private var refreshObserver: AnyCancellable?
    private var foreground = true

    private init() {}

    func start(model: AppModel) {
        guard !isRecording, !TestCentre.active(.display) else { return }
        startedAt = Date()
        startedUptime = ProcessInfo.processInfo.systemUptime
        lines = []
        droppedLines = 0
        foreground = UIApplication.shared.applicationState == .active
        isRecording = true
        reportURL = nil
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "unknown"
        note("session_start build=\(build) "
             + "ios=\(ProcessInfo.processInfo.operatingSystemVersionString) device=\(UIDevice.current.model)")

        syncObserver = model.live.$backfilling.removeDuplicates().dropFirst().sink { [weak self] syncing in
            self?.note(syncing ? "sync_start" : "sync_end")
        }
        note(model.live.backfilling ? "sync_already_running" : "sync_idle")
        note("data_volume days=\(model.repo.days.count) sleeps=\(model.repo.sleeps.count)")
        refreshObserver = model.repo.$refreshSeq.dropFirst().sink { [weak self, weak model] seq in
            self?.note("repo_publish seq=\(seq) days=\(model?.repo.days.count ?? 0) sleeps=\(model?.repo.sleeps.count ?? 0)")
        }
        DisplayPerformanceMonitor.shared.emit = { [weak self] line in self?.note(line) }
        // Count the already-loaded view data. A full-store census would itself load a large
        // history during the performance test and distort the first seconds of the trace.
        DisplayPerformanceMonitor.shared.dataVolumeProvider = nil
        if foreground { DisplayPerformanceMonitor.shared.start() }
        expiration = Task { [weak self] in
            do { try await Task.sleep(for: .seconds(Self.duration)) } catch { return }
            self?.stop(reason: "limit")
        }
    }

    func note(_ event: String) {
        guard isRecording else { return }
        guard lines.count < Self.maxLines else { droppedLines += 1; return }
        let elapsedMs = Int((ProcessInfo.processInfo.systemUptime - startedUptime) * 1_000)
        lines.append("+\(elapsedMs)ms \(event)")
    }

    func sceneChanged(active: Bool) {
        guard isRecording else { return }
        if Date().timeIntervalSince(startedAt) >= Self.duration { stop(); return }
        foreground = active
        note(active ? "scene_active" : "scene_inactive")
        if active {
            DisplayPerformanceMonitor.shared.start()
        } else {
            DisplayPerformanceMonitor.shared.stop()
            saveSnapshot()
        }
    }

    func stop(reason: String = "user") {
        guard isRecording else { return }
        DisplayPerformanceMonitor.shared.stop()
        note("session_end reason=\(reason)")
        isRecording = false
        expiration?.cancel()
        expiration = nil
        syncObserver = nil
        refreshObserver = nil
        DisplayPerformanceMonitor.shared.emit = nil
        DisplayPerformanceMonitor.shared.dataVolumeProvider = nil
        saveSnapshot()
    }

    func reloadLatest() {
        guard !isRecording else { return }
        reportURL = Self.savedReports().last
    }

    func clearReports() {
        guard !isRecording else { return }
        for url in Self.savedReports() { try? FileManager.default.removeItem(at: url) }
        reportURL = nil
    }

    private func saveSnapshot() {
        guard let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first else { return }
        let name = Self.prefix + ISO8601DateFormatter().string(from: startedAt).replacingOccurrences(of: ":", with: "-") + ".txt"
        let url = directory.appendingPathComponent(name)
        let header = ["NOOP local performance capture; no health values or screenshots",
                      "started_at=\(ISO8601DateFormatter().string(from: startedAt))",
                      "dropped_events=\(droppedLines)", ""]
        let text = (header + lines).joined(separator: "\n") + "\n"
        guard (try? text.write(to: url, atomically: true, encoding: .utf8)) != nil else { return }
        reportURL = url
        Self.pruneReports()
    }

    private static func savedReports() -> [URL] {
        guard let directory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first,
              let files = try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
        else { return [] }
        return files.filter { $0.lastPathComponent.hasPrefix(prefix) && $0.pathExtension == "txt" }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    private static func pruneReports() {
        let reports = savedReports()
        let cutoff = Date().addingTimeInterval(-30 * 86_400)
        let keep = Set(reports.suffix(4))
        for url in reports {
            let created = try? url.resourceValues(forKeys: [.creationDateKey]).creationDate
            if !keep.contains(url) || (created.map { $0 < cutoff } ?? false) {
                try? FileManager.default.removeItem(at: url)
            }
        }
    }
}
#endif
