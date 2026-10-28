import SwiftUI
import StrandDesign

struct DoubleTapTimerControls: View {
    @EnvironmentObject private var model: AppModel
    @ObservedObject var timer: DoubleTapTimer
    // Link changes refresh this leaf; availability is resolved by the same gate that starts the timer.
    @ObservedObject var live: LiveState
    @AppStorage(DoubleTapTimer.minutesKey) private var minutes = DoubleTapTimer.defaultMinutes

    var body: some View {
        VStack(alignment: .leading, spacing: NoopMetrics.gap) {
            Stepper(value: $minutes, in: DoubleTapTimer.minutesRange) {
                HStack {
                    Text("Duration").font(StrandFont.body)
                    Spacer()
                    Text("\(minutes) min").font(StrandFont.bodyNumber)
                }
            }
            .foregroundStyle(StrandPalette.textPrimary)

            Text("One buzz on start, one with 30 seconds left, two at the end. Double-tap again to restart.")
                .font(StrandFont.footnote).foregroundStyle(StrandPalette.textSecondary)
            Text("Keep NOOP running in the background and WHOOP connected. Signals may be delayed if iOS suspends NOOP. This action takes priority over Lift Log.")
                .font(StrandFont.footnote).foregroundStyle(StrandPalette.textSecondary)

            if !model.canStartDoubleTapTimer {
                Text("Connect and fully pair a WHOOP 5.0 to use this timer.")
                    .font(StrandFont.footnote).foregroundStyle(StrandPalette.statusWarning)
            }

            switch timer.state {
            case .running:
                TimelineView(.periodic(from: .now, by: 1)) { _ in
                    let seconds = timer.remaining() ?? 0
                    Text(Duration.seconds(seconds).formatted(.time(pattern: .minuteSecond(padMinuteToLength: 2))))
                        .font(StrandFont.bodyNumber)
                        .foregroundStyle(StrandPalette.textPrimary)
                        .accessibilityLabel(Text("Remaining"))
                        .accessibilityValue(Duration.seconds(seconds).formatted(.units(allowed: [.minutes, .seconds], width: .wide)))
                }
            case .idle:
                Text("Double-tap your WHOOP to start.")
                    .font(StrandFont.body).foregroundStyle(StrandPalette.textSecondary)
            case .finished:
                Text("Timer finished")
                    .font(StrandFont.body).foregroundStyle(StrandPalette.textPrimary)
            case .disconnected:
                Text("Timer stopped: WHOOP disconnected.")
                    .font(StrandFont.body).foregroundStyle(StrandPalette.statusWarning)
            }

            HStack(spacing: NoopMetrics.gap) {
                Button("Start timer") { model.runMacAction(.countdownTimer, shortcut: "") }
                    .disabled(!model.canStartDoubleTapTimer)
                Button("Stop") { timer.stop() }
                    .disabled(timer.remaining() == nil)
            }
            .buttonStyle(.bordered).tint(StrandPalette.accent)
        }
        .onAppear {
            minutes = min(max(minutes, DoubleTapTimer.minutesRange.lowerBound), DoubleTapTimer.minutesRange.upperBound)
        }
    }
}
