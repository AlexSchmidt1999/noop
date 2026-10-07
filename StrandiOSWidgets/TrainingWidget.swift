import SwiftUI
import WidgetKit
import StrandDesign

struct TrainingEntry: TimelineEntry {
    var date: Date
    var snapshot: TrainingSnapshot
    var favorite: Int
}
struct TrainingWidgetProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> TrainingEntry { .init(date: .now, snapshot: .unavailable, favorite: 0) }
    func snapshot(for configuration: TrainingWidgetConfiguration, in context: Context) async -> TrainingEntry {
        .init(date: .now, snapshot: .load(), favorite: configuration.favorite.rawValue)
    }
    func timeline(for configuration: TrainingWidgetConfiguration, in context: Context) async -> Timeline<TrainingEntry> {
        let entry = await snapshot(for: configuration, in: context)
        let confirmationEnd = entry.snapshot.sessions.compactMap(\.confirmationUntil).filter { $0 > Date() }.min()
        let next = confirmationEnd ?? Date().addingTimeInterval(900)
        return Timeline(entries: [entry], policy: .after(next))
    }
}
struct TrainingWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: "NOOPTrainingWidget", intent: TrainingWidgetConfiguration.self, provider: TrainingWidgetProvider()) { entry in
            TrainingWidgetView(entry: entry)
                .containerBackground(StrandPalette.surfaceBase, for: .widget)
        }
        .configurationDisplayName("Training")
        .description("Start a favorite or control your running training.")
        .supportedFamilies([.systemMedium, .accessoryRectangular])
    }
}
private struct TrainingWidgetView: View {
    let entry: TrainingEntry
    @Environment(\.widgetFamily) private var family
    var body: some View {
        VStack(alignment: .leading, spacing: NoopMetrics.rowSpacing) {
            if family == .systemMedium {
                HStack(spacing: NoopMetrics.rowSpacing) {
                    ForEach(entry.snapshot.favorites) { favorite in
                        Button(intent: TrainingActionIntent(.start, favorite: favorite.id)) {
                            Label(favorite.name, systemImage: favorite.programID == nil ? "play.fill" : "dumbbell.fill")
                                .lineLimit(1)
                        }
                        .disabled(favorite.sport == nil && favorite.programID == nil)
                    }
                }
            }
            // A widget addresses one session. Each simultaneous session retains its own Live Activity.
            if let training = selectedSession {
                if family != .accessoryRectangular || !training.isConfirming() {
                    HStack {
                        Text(training.title).lineLimit(1)
                        Spacer(minLength: NoopMetrics.space1)
                        TrainingClock(training: training)
                    }
                    .font(StrandFont.caption)
                }
                TrainingControls(training: training, labels: entry.snapshot.labels)
            } else if family == .accessoryRectangular, let favorite = selectedFavorite {
                Button(intent: TrainingActionIntent(.start, favorite: favorite.id)) {
                    Label(favorite.name, systemImage: "play.fill").lineLimit(2)
                }
                .disabled(favorite.sport == nil && favorite.programID == nil)
            } else if entry.snapshot.favorites.isEmpty {
                Text("Open NOOP to configure training").font(StrandFont.footnote)
            }
        }
        .foregroundStyle(StrandPalette.textPrimary)
        .tint(StrandPalette.accent)
    }
    private var selectedFavorite: TrainingFavorite? { entry.snapshot.favorites.first { $0.id == entry.favorite } }
    private var selectedSession: TrainingDisplay? {
        let kind = selectedFavorite?.programID == nil ? "workout" : "lift"
        return entry.snapshot.sessions.first { $0.kind == kind } ?? entry.snapshot.sessions.first
    }
}
