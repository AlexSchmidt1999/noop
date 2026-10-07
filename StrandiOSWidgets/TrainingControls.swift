import SwiftUI
import StrandDesign

struct TrainingControls: View {
    let training: TrainingDisplay
    let labels: [String: String]
    private var completedOnly: String { label("completedOnly") }
    private func label(_ key: String) -> String { labels[key] ?? "" }
    var body: some View {
        VStack(alignment: .leading, spacing: NoopMetrics.space1) {
            if let error = training.error {
                Text(error).font(StrandFont.footnote).foregroundStyle(StrandPalette.metricAmber)
            }
            if training.isConfirming(), let token = training.confirmationToken {
                Text(label("confirm")).font(StrandFont.caption).foregroundStyle(StrandPalette.textPrimary)
                if training.kind == "lift" {
                    Text(completedOnly).font(StrandFont.footnote).foregroundStyle(StrandPalette.textSecondary)
                }
                HStack(spacing: NoopMetrics.rowSpacing) {
                    Button(intent: TrainingActionIntent(.confirmEnd, sessionID: training.id, token: token)) {
                        Text(label("yes"))
                    }
                    Button(intent: TrainingActionIntent(.cancelEnd, sessionID: training.id)) {
                        Text(label("cancel"))
                    }
                }
            } else {
                HStack(spacing: NoopMetrics.rowSpacing) {
                    Button(intent: TrainingActionIntent(training.pausedAt == nil ? .pause : .resume, sessionID: training.id)) {
                        Label(label(training.pausedAt == nil ? "pause" : "resume"), systemImage: training.pausedAt == nil ? "pause.fill" : "play.fill")
                    }
                    Button(intent: TrainingActionIntent(.requestEnd, sessionID: training.id)) {
                        Label(label("end"), systemImage: "stop.fill")
                    }
                }
            }
        }
        .font(StrandFont.caption)
        .lineLimit(1)
        .minimumScaleFactor(0.7)
        .tint(StrandPalette.accent)
    }
}

struct TrainingClock: View {
    let training: TrainingDisplay
    var body: some View {
        Text(timerInterval: training.clockStart...max(training.clockStart, training.pulseDeadline ?? training.clockStart.addingTimeInterval(7 * 86_400)),
             pauseTime: training.pausedAt, countsDown: false)
            .monospacedDigit()
            .foregroundStyle(StrandPalette.textPrimary)
    }
}
