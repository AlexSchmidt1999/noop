# iPhone performance checks

The iOS Test Centre can record an opt-in, local performance session for at most 30 minutes. Open **More → Test Centre → iPhone Performance**, start the capture, use the app, then stop and review the text report. The app also stops the capture at the time limit. Nothing is uploaded automatically. The share button acts only after the report has been opened for review.

The report contains frame-time summaries (including frames over 33 ms), peak process memory, screen changes, repository refresh and strap-sync transitions, iOS/build metadata, and counts of already loaded daily and sleep records. It contains no heart-rate values, health records, account identifiers, screenshots, or screen recordings. The capture does not run a full database census while measuring scroll performance. At most four reports are retained for 30 days; **Clear performance reports** deletes them sooner.

## Reproduce on a paired iPhone

1. Record the build commit, iOS version, Reduce Motion setting, phone temperature, charging state, brightness, and whether strap history is syncing. Keep those conditions the same for a before/after comparison.
2. Run `ScrollPerformanceUITests.testLocalPerformanceReport` once to check start, stop, and review. The UI test runner requires iPhone UI Automation. If the runner opens to a black screen, diagnose its launch/signing logs before trusting any trace.
3. Run `testTodayScroll`, `testTrendsScroll`, and `testInsightsScroll` for three identical passes each. `testEveryMenuScroll` visits the root tabs and every More destination, including Settings with Advanced expanded. `testSettingsScroll` records a focused local report for the same Settings gestures. The Settings tests flip Reduce Motion and Day-cycle background, then restore their prior values. The tests do not send strap commands or change health data.
4. Record Animation Hitches and SwiftUI/Time Profiler in separate Instruments sessions. Do not combine the traces: an earlier combined trace crashed during processing. Attribute a hitch to the app only when the trace identifies its work; the in-app 33 ms count alone cannot make that attribution.
5. Compare the same gesture path and data set before and after each fix. Prioritize the screens with repeatable hitches or long main-thread work. Inspect the transition when strap syncing ends separately from steady scrolling.

For chart diagnosis, compare the normal chart with a same-height placeholder in a local diagnostic build. Keep the underlying data and interactions intact. Simplify drawing only if the comparison shows a meaningful reduction in app-attributed hitches; verify zoom, selection, extrema, gaps, and VoiceOver afterward. The previous chart style and point-lookup improvements are already in the fork.

Do not infer iPhone battery savings from a frame trace. Compare longer screen-on and screen-off periods with the same radios, brightness, charging state, and workload, without the diagnostic capture running. A report intended for an upstream issue or PR should be reviewed locally and reduced to aggregate timing/counts before sharing. The public repository must never contain a personal report or device video.
