# iPhone performance changes in this fork

This fork keeps NOOP's on-device data model and UI behavior while reducing work on
the iPhone Today, Trends, and Insights screens. The changes are deliberately small:

| Change | Why it helps |
|---|---|
| [Bound HealthKit observer deltas](../StrandiOS/Health/HealthKitBridge.swift) to the same 31-day window that can be re-aggregated. | A new anchor no longer decodes years of Apple Watch samples just to discard days outside that window. Recent changes still use the existing idempotent aggregate sync. |
| [Avoid idle Today invalidations](../Strand/Liquid/LiquidTodayView.swift). | Normal upward scrolling no longer writes the unchanged zero pull-indicator state on every offset report. The heart-rate trace stays static when it shows historical rather than live values. |
| Build both [Liquid Today](../Strand/Liquid/LiquidTodayView.swift) and [classic Today](../Strand/Screens/TodayView.swift) sections lazily. | Off-screen dashboard sections are created as they approach the viewport instead of all at once. |
| Use a [solid iOS panel surface](../Packages/StrandDesign/Sources/StrandDesign/NoopVisualStyle.swift). | Repeated card gradients, translucent overlays, and soft shadows caused many offscreen render passes during scrolling. iOS now draws one theme-aware fill and a thin border; macOS retains the original treatment. |
| Build [Trends](../Strand/Screens/TrendsView.swift) and [Insights](../Strand/Screens/InsightsView.swift) sections lazily. | Their former inner `VStack` made the outer lazy scaffold treat the entire screen as one child. Each section now enters the view tree near the viewport, at the same spacing and in the same order. The separate [Insights hub](../Strand/Screens/InsightsHubView.swift) uses the same layout rule. |
| Reuse the five resolved [Trends](../Strand/Screens/TrendsView.swift) metric windows while the data and selected range stay the same. | An unrelated Repository publication no longer filters the full history five times during a SwiftUI body update. Data, range, Rest-series, day, and language changes invalidate the cache. |
| Compute the live Effort score away from the main actor in [Liquid Today](../Strand/Liquid/LiquidTodayView.swift) and [classic Today](../Strand/Screens/TodayView.swift). | The scorer fingerprints and integrates up to a full day of HR samples. Its result and refresh cadence stay the same, but this pure work cannot block touch handling while a refresh finishes. This change has not been isolated in a device hitch comparison. |

## Device evidence

Two approximately 21-second Instruments **Animation Hitches** captures were made
on an iPhone 17 Pro Max running iOS 27.0 while manually scrolling Today. The first
used the fork before the solid panel change; the second used commit `a96ea9fc`.
Both already included the HealthKit, idle-update, and lazy-section changes above.
The owner confirmed that **Reduce motion in NOOP was already enabled** in the first
capture, so the looping sky and liquid-gauge animations do not explain its hitches.

| Metric | Before solid panels | After solid panels |
|---|---:|---:|
| Animation hitches | 347 | 71 |
| Worst hitch | 75.0 ms | 25.0 ms |
| Median offscreen passes per rendered frame | 74 | 28 |
| 95th-percentile render duration | 13.4 ms | 10.1 ms |
| 95th-percentile app update duration | 27.2 ms | 11.0 ms |

The captures support the user's report that scrolling feels better. Manual scroll
speed and visible content were not controlled, so these figures describe two device
sessions rather than a repeatable benchmark or a guarantee on other iPhones. A third
capture with Reduce Motion still enabled recorded 16 hitches but a different
offscreen-pass distribution. This warns against treating one scroll as a controlled
comparison. The raw traces are not committed because they may contain personal
device and app data.

## Repeatable device scrolls

[`ScrollPerformanceUITests`](../NOOPiOSUITests/ScrollPerformanceUITests.swift) runs the same
up/down gesture path three times on each of Today, Trends, and Insights. It activates the
existing app process, avoiding an unrelated cold-start animation in the scroll measurement.
Keep the visible data, appearance settings, device,
and build configuration the same between variants. Record Animation Hitches and a separate
Time Profiler or SwiftUI trace; combining the instruments crashed during one local attempt.

The earlier solid-panel captures did not isolate the HR chart. Its symbols accounted for a
small fraction of main-thread samples in the post-panel Time Profiler trace, while SwiftUI
view-graph work was more prominent. This is a lead for testing, not proof that chart drawing
is free. Chart points, gaps, zoom, and source values remain unchanged in this pass.

An earlier, shorter UI scroll path ran three times on each screen on the paired iPhone.
The longer gesture path above was added afterward and has not completed a controlled
before/after comparison. A subsequent extended run lost the device accessibility server
(`kAXErrorServerNotFound`) and showed a black screen. The test runner was removed from the
phone at the owner's request. The long mixed Instruments trace was not used as a performance
data point, and this pass does **not** claim zero remaining animation hitches or a measured
iPhone battery improvement.

## Remaining work

The second manual capture still recorded 71 hitches; 53 were labeled as potentially
expensive app updates. Its time profile shows work in SwiftUI's view graph and in
the classic `TodayView`. When device automation is available again, compare three
identical scroll paths before and after this pass on each screen, then record a
separate Time Profiler capture if app hitches remain. Test a same-height chart-free
diagnostic build before changing chart marks or point density; preserve zoom, peaks,
gaps, readouts, and VoiceOver. Measure battery use over a longer device session
before attributing any improvement to these rendering changes.
