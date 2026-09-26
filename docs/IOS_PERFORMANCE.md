# iPhone performance checks

The iOS Test Centre can record an opt-in, local performance session for at most 30 minutes. Open **More → Test Centre → iPhone Performance**, start the capture, use the app, then stop and review the text report. The app also stops the capture at the time limit. Nothing is uploaded automatically. The share button acts only after the report has been opened for review.

The report contains frame-time summaries (including frames over 33 ms), peak process memory, screen changes, repository refresh and strap-sync transitions, iOS/build metadata, and counts of already loaded daily and sleep records. It contains no heart-rate values, health records, account identifiers, screenshots, or screen recordings. The capture does not run a full database census while measuring scroll performance. At most four reports are retained for 30 days; **Clear performance reports** deletes them sooner.

## Reproduce on a paired iPhone

1. Record the build commit, iOS version, Reduce Motion setting, phone temperature, charging state, brightness, and whether strap history is syncing. Keep those conditions the same for a before/after comparison.
2. Run `ScrollPerformanceUITests.testLocalPerformanceReport` once to check start, stop, and review. The UI test runner requires iPhone UI Automation. If the runner opens to a black screen, diagnose its launch/signing logs before trusting any trace.
3. Run `testTodayScroll`, `testTrendsScroll`, and `testInsightsScroll` for three identical passes each. `testChartScreensCapture` records all three paths in one local report. `testEveryMenuScroll` visits the root tabs and every More destination, including Settings with Advanced expanded. `testSettingsScroll` records a focused local report for the same Settings gestures. The Settings tests flip Reduce Motion and Day-cycle background, then restore their prior values. The tests do not send strap commands or change health data.
4. Record Animation Hitches and SwiftUI/Time Profiler in separate Instruments sessions. Do not combine the traces: an earlier combined trace crashed during processing. Attribute a hitch to the app only when the trace identifies its work; the in-app 33 ms count alone cannot make that attribution.
5. Compare the same gesture path and data set before and after each fix. Prioritize the screens with repeatable hitches or long main-thread work. Inspect the transition when strap syncing ends separately from steady scrolling.

For chart diagnosis, compare the normal chart with a same-height placeholder in a local diagnostic build. Keep the underlying data and interactions intact. Simplify drawing only if the comparison shows a meaningful reduction in app-attributed hitches; verify zoom, selection, extrema, gaps, and VoiceOver afterward. The previous chart style and point-lookup improvements are already in the fork.

Do not infer iPhone battery savings from a frame trace. Compare longer screen-on and screen-off periods with the same radios, brightness, charging state, and workload, without the diagnostic capture running. A report intended for an upstream issue or PR should be reviewed locally and reduced to aggregate timing/counts before sharing. The public repository must never contain a personal report or device video.

## Initial device findings (2026-09-26)

On an iPhone 17 Pro Max running iOS 27.0, the UI runner completed the full More-menu sweep, focused Settings test, and three Today/Trends/Insights captures. Each chart-screen capture repeats the same scroll path three times per screen. The share of display frames over 33 ms was:

| Screen | Run 1 | Run 2 | Run 3 |
|---|---:|---:|---:|
| Today | 114/3,600 (3.2%) | 123/3,660 (3.4%) | 109/3,600 (3.0%) |
| Trends | 109/2,580 (4.2%) | 105/2,460 (4.3%) | 108/2,580 (4.2%) |
| Insights | 133/2,640 (5.0%) | 109/2,700 (4.0%) | 114/2,760 (4.1%) |

There were no dropped capture events. These are display-frame counts, **not** app-attributed Animation Hitches. Reaching the top of Today triggered pull-to-refresh six or seven times per run, so that path should be measured separately from ordinary scrolling.

The focused Settings baseline recorded 318/8,220 frames over 33 ms (3.9%). Replacing its inner stack with a lazy stack in a temporary build produced 302/8,220 (3.7%) on one run and 337/8,160 (4.1%) during profiling. That experiment was reverted because the measurements do not show a repeatable benefit. A focused Trends Time Profiler trace showed no main-thread pause over 250 ms; Charts appeared in about 6% of main-thread sample stacks during the test window. This does not establish that chart drawing causes the remaining stutters, so the capture change does not alter chart rendering. The separate Animation Hitches command-line trace failed to finish processing and supplies no attribution. Battery impact has not been measured.
