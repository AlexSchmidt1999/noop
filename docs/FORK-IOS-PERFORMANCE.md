# iPhone performance changes in this fork

This fork keeps NOOP's on-device data model and UI behavior while reducing work on
the iPhone Today screen. The changes are deliberately small and iOS-focused:

| Change | Why it helps |
|---|---|
| [Bound HealthKit observer deltas](../StrandiOS/Health/HealthKitBridge.swift) to the same 31-day window that can be re-aggregated. | A new anchor no longer decodes years of Apple Watch samples just to discard days outside that window. Recent changes still use the existing idempotent aggregate sync. |
| [Avoid idle Today invalidations](../Strand/Liquid/LiquidTodayView.swift). | Normal upward scrolling no longer writes the unchanged zero pull-indicator state on every offset report. The heart-rate trace stays static when it shows historical rather than live values. |
| Build both [Liquid Today](../Strand/Liquid/LiquidTodayView.swift) and [classic Today](../Strand/Screens/TodayView.swift) sections lazily. | Off-screen dashboard sections are created as they approach the viewport instead of all at once. |
| Use a [solid iOS panel surface](../Packages/StrandDesign/Sources/StrandDesign/NoopVisualStyle.swift). | Repeated card gradients, translucent overlays, and soft shadows caused many offscreen render passes during scrolling. iOS now draws one theme-aware fill and a thin border; macOS retains the original treatment. |

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

## Remaining work

The second capture still recorded 71 hitches; 53 were labeled as potentially
expensive app updates. Its time profile shows work in SwiftUI's view graph and in
the classic `TodayView`. The next useful experiment is a controlled capture of the
same visible sections while inspecting which state changes invalidate that view,
especially during a refresh. Slowing data refresh blindly would make the screen
less current without establishing the cause. Keep WHOOP and Apple Health ingestion
semantics separate from cosmetic rendering changes, and measure battery use over
a longer device session before claiming a battery improvement.
