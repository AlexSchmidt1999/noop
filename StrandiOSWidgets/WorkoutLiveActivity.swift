import SwiftUI
import WidgetKit
import ActivityKit
import StrandDesign

struct WorkoutLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: WorkoutActivityAttributes.self) { context in
            VStack(alignment: .leading, spacing: NoopMetrics.rowSpacing) {
                HStack {
                    Label(context.state.training.title, systemImage: "figure.run")
                        .font(StrandFont.subhead).lineLimit(1)
                    Spacer(minLength: NoopMetrics.space1)
                    TrainingClock(training: context.state.training).font(StrandFont.bodyNumber)
                }
                Text(context.state.labels[context.state.training.pausedAt == nil ? "running" : "paused"] ?? "")
                    .font(StrandFont.footnote).foregroundStyle(StrandPalette.textSecondary)
                TrainingControls(training: context.state.training, labels: context.state.labels)
            }
            .padding(NoopMetrics.rowSpacing)
            .activityBackgroundTint(StrandPalette.surfaceBase)
            .activitySystemActionForegroundColor(StrandPalette.textPrimary)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Text(context.state.training.title).font(StrandFont.caption).lineLimit(1)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    TrainingClock(training: context.state.training).font(StrandFont.caption)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    TrainingControls(training: context.state.training, labels: context.state.labels)
                }
            } compactLeading: {
                Image(systemName: context.state.training.pausedAt == nil ? "figure.run" : "pause.fill")
                    .foregroundStyle(StrandPalette.accent)
            } compactTrailing: {
                TrainingClock(training: context.state.training).font(StrandFont.caption)
            } minimal: {
                Image(systemName: "figure.run").foregroundStyle(StrandPalette.accent)
            }
        }
    }
}
