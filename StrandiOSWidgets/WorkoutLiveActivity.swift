import SwiftUI
import WidgetKit
import ActivityKit
import StrandDesign

struct WorkoutLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: WorkoutActivityAttributes.self) { context in
            WorkoutActivityView(training: context.state.training, labels: context.state.labels)
                .activityBackgroundTint(StrandPalette.surfaceBase)
                .activitySystemActionForegroundColor(StrandPalette.textPrimary)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Label(context.state.training.title, systemImage: context.state.training.pausedAt == nil ? "stopwatch.fill" : "pause.fill")
                        .font(StrandFont.caption.weight(.semibold)).lineLimit(1).foregroundStyle(StrandPalette.accent)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    TrainingClock(training: context.state.training).font(StrandFont.bodyNumber)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    TrainingControls(training: context.state.training, labels: context.state.labels)
                }
            } compactLeading: {
                Image(systemName: context.state.training.pausedAt == nil ? "stopwatch.fill" : "pause.fill")
                    .foregroundStyle(StrandPalette.accent)
            } compactTrailing: {
                Text(verbatim: "0:00:00").font(StrandFont.captionNumber).hidden()
                    .overlay(alignment: .trailing) {
                        TrainingClock(training: context.state.training).font(StrandFont.captionNumber)
                            .multilineTextAlignment(.trailing).lineLimit(1).minimumScaleFactor(0.8)
                    }
            } minimal: {
                Image(systemName: context.state.training.pausedAt == nil ? "stopwatch.fill" : "pause.fill").foregroundStyle(StrandPalette.accent)
            }
        }
    }
}

struct WorkoutActivityView: View {
    let training: TrainingDisplay
    let labels: [String: String]
    var body: some View {
        let focused = training.isConfirming() || training.error != nil
        return VStack(alignment: .leading, spacing: NoopMetrics.space3) {
            HStack(spacing: NoopMetrics.space3) {
                if !focused {
                    Image(systemName: training.pausedAt == nil ? "stopwatch.fill" : "pause.fill")
                        .font(StrandFont.title2)
                        .foregroundStyle(StrandPalette.accent)
                        .frame(width: NoopButtonMetrics.minHitTarget, height: NoopButtonMetrics.minHitTarget)
                        .background(StrandPalette.surfaceRaised, in: RoundedRectangle(cornerRadius: NoopButtonMetrics.cornerRadius))
                        .accessibilityHidden(true)
                }
                VStack(alignment: .leading, spacing: NoopMetrics.space1) {
                    Text(training.title).font(focused ? StrandFont.caption.weight(.semibold) : StrandFont.headline)
                        .foregroundStyle(StrandPalette.textPrimary).lineLimit(focused ? 1 : 2)
                    if !focused {
                        Text(labels[training.pausedAt == nil ? "running" : "paused"] ?? "")
                            .font(StrandFont.caption).foregroundStyle(training.pausedAt == nil ? StrandPalette.textSecondary : StrandPalette.metricAmber)
                    }
                }
                Spacer(minLength: 0)
                Text(verbatim: "0:00:00").font(focused ? StrandFont.bodyNumber : StrandFont.title1).hidden()
                    .overlay(alignment: .trailing) {
                        TrainingClock(training: training).font(focused ? StrandFont.bodyNumber : StrandFont.title1).multilineTextAlignment(.trailing)
                            .lineLimit(1).minimumScaleFactor(0.8)
                    }
            }
            TrainingControls(training: training, labels: labels)
        }
        .padding(NoopMetrics.space4)
    }
}
