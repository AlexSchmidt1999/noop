# iPhone UI contributions included in NOOP 12

Nine contributions from this fork are included in upstream NOOP 12.0.0.
NOOP 12.0.0 remains the base. The fork test branches additionally keep the sync indicator
expanded throughout a transfer, construct Today cards lazily, and isolate header-width state.
The earlier upstream lazy-dashboard proposal, PR #2638, remains a separate review.
The fork retains its reviewed security and local signing pipeline; new upstream PRs wait
for device testing. See [fork training testing](FORK_TRAINING_TESTING.md).

| Location | Problem and correction |
|---|---|
| `LiquidTodayView.handlePull` | Ordinary upward scrolling repeatedly reports a negative offset that clamps to zero. Assigning that unchanged state invalidates the dashboard. Write only when the clamped offset changes; refresh arming and release handling still run. |
| `LiquidLiveHR` | Historical fallback buckets need no decorative animation clock. Run the trace animation only for live HR; retain the same historical points and gap segments. |
| `NoopPanelSurface` | Layered translucent gradients and blurred shadows repeat across every scrolling card. iOS uses a solid theme-aware fill and thin tinted border; other platforms retain their previous surfaces. Card geometry and design tokens remain the same. |
| `TrendsView.ResolvedCache` | Repository status updates can redraw the screen without changing historical data. Cache the five metric windows by repository identity, refresh generation, selected range, Rest-series revision, local day, and locale. This avoids repeated history filtering while keeping readings and captions current. |
| Today Effort loading | Fingerprinting and scoring a day's HR samples on the main actor can delay touch handling during refresh. Snapshot the same inputs and await the existing scorer in a detached utility task; publish its result back on the view's actor. Upstream's personal HRmax setting is retained. |
| `TrendChart`, `OverviewHRChart` | Chart-wide gradient styles were rebuilt per mark, and cursor selection scanned the entire series per event. Reuse styles per chart update and binary-search date-sorted, full-resolution readings. Selection retains the earlier-point tie rule. Existing drawing budgets, gaps, zoom, workout axes, and VoiceOver summaries are retained. |
| `CountUpText`, `staggeredAppear`, `PipBar` | Checking only system Reduce Motion ignored NOOP's own preference and Low Power Mode. Use the existing shared quiet-motion gate so data arrivals and lazy entrances respect all of those settings. |
| `HealthKitBridge.fetchTouchedDayWindow` | A fresh observer anchor could decode years of samples before selecting a maximum 31-day aggregate window. Apply that window in the query itself. Explicit historical imports retain their own windows; anchors are still committed after successful ingestion. |

The chart package includes a comparison against the previous linear selection rule
across readings, gaps, boundaries, and ties. Shared views require both iOS and macOS
app builds; package tests alone do not compile them. Device scrolling and HealthKit
observer behavior require a separate check on hardware after installing the build.

This document describes the code and its intended effect. It contains no personal
measurements, recordings, or reports, and makes no claim of zero hitches or measured
iPhone battery savings. Those records remain local.
