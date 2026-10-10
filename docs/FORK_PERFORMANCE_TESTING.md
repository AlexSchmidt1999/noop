# Local Apple performance capture

Build 444 reuses Display & Performance in **More → Test Centre** for a longer iPhone
test. Enable that mode once, then use Today, Trends and the other tabs normally.
The existing switch persists across app launches. Turn it off there when the test ends.
Android is outside this fork change's requested scope.

The app owns the iPhone monitor instead of the Test Centre screen. Capture stops
when the app becomes inactive and resumes when it is active again, if the mode or
Log Everything remains enabled. It uses one display link and normally writes one
summary per five seconds, plus a partial summary when changing tabs or stopping.
No background execution task or network export is added.

Each summary records callback mean/p95/worst interval, the existing 33 ms counter,
late callbacks relative to the display link's actual cadence, the primary tab,
elapsed capture time, whole-process CPU use, memory footprint, thermal state and
Low Power Mode and current history-sync state. CPU at 100% means one fully occupied CPU core. Refresh-rate
transitions use the slower adjacent cadence to avoid counting a deliberate rate
change as a stall. Nearest-rank p95 now uses the correct zero-based index.

These callback measurements are diagnostic indicators, not measured rendered FPS
or GPU hitch attribution. Native Instruments is still needed to identify expensive
call stacks and render work. The existing data-volume probe runs once on start;
no health measurements, workout names or device identifiers are added to the
performance summaries.

The existing redactor and rotating `StrapLogArchive` are reused. A separate local
performance archive has the same 2 MiB bound, so verbose strap sync cannot evict
all performance evidence. Old segments rotate when the bound is reached; this is
not unlimited retention. Display and Log Everything reports include
`performance.txt` through the existing redaction, size cap and review-before-share
flow. Reports can also include other existing attachments, including screenshots;
only reviewed aggregate timing statistics should be copied to a public PR.

## Initial Instruments captures

Source: `8065b48e`, installed Release build 443, iOS 27.0.1. The owner operated the
iPhone over USB with the SwiftUI Instruments template. Attaching to the running
process failed; launching the installed app through Instruments succeeded.
Recordings and exports remain in ignored local `build/performance/heart-scroll/`.

| Scenario | Recorded limit | Hitch events | Events after 10 seconds | Worst hitch after 10 seconds |
| --- | --- | --- | --- | --- |
| Today, vertical scrolling across Heart Rate | 40 s | 39 | 22 | 62.51 ms |
| Trends, scrolling the diagrams | 45 s | 77 | 47 | 216.69 ms |

Hitch durations are extra deadline delay reported by Instruments, not full frame
times. The first ten seconds are excluded in the latter columns to reduce launch
effects. These are two interactive recordings with profiler overhead, not a
controlled benchmark or evidence that a particular function caused each hitch.

## Device checks

1. Enable Display & Performance, leave Test Centre, and spend time in Today and Trends.
2. Lock the phone, reopen NOOP, and force-quit/relaunch once; capture should resume
   only while foreground-active and keep the selected mode.
3. Use a long WHOOP sync and both short/long Trends ranges. The summaries should
   identify the tab and preserve older performance sessions independently of sync logs.
4. Disable the mode and Log Everything; no further frame callbacks or summaries
   should be generated. Existing captures remain available for a reviewed export.
5. Share a Display report and inspect `performance.txt`; keep raw traces and other
   attachments local until their contents have been reviewed.

The detailed Instruments captures establish the reported hitch counts. The longer
capture and its measurement overhead still need validation during ordinary device use.

## Dashboard follow-up (build 447)

A local archive read contained 527 frame-summary windows across the primary tabs,
including 461 Today windows (about 37.5 sampled minutes) and 54 Trends windows
(about 4.3 sampled minutes). Today recorded 2,026 callback intervals over 33 ms,
with a worst interval of 163.3 ms; Trends recorded 170, with a worst of 163.2 ms.
The median window p95 was 16.7 ms for both. These are mixed ordinary-use captures
from earlier test builds, not controlled scrolling runs or rendered-frame measurements.
They confirm intermittent stalls without identifying their exact cause.

Today and Trends previously supplied one eager inner VStack to a lazy scaffold.
That eagerly laid out the entire inner card column. Both inner columns now use the
native LazyVStack with their existing spacing, order and content. A reduced native
macOS probe of this nesting built 14 card bodies initially with the eager column,
versus 3 with the lazy column; scrolling materialized the next cards. This verifies
that work is deferred, not an iPhone hitch reduction.

Trends' existing resolved-data cache now retains the calendar's parsed dates under
the same repository-generation/range/day/locale invalidation. Calendar day and week
identities come from their dates instead of new UUIDs, so unchanged columns retain
identity across redraws. The layout and scores are unchanged. This follows Apple's
[identity and update guidance](https://developer.apple.com/videos/play/wwdc2023/10160/).
The separate native chart-rendering change is described in FORK_CHART_PERFORMANCE.md.

Each new capture start includes the app version and build, allowing future summaries
to be separated by installed version. There is no new switch, watcher, background
execution or export. The existing foreground-only capture remains opt-in.

A new iPhone Today/Trends scroll comparison remains required after installing the
combined build. Raw archives and probes stay in ignored local build directories.

## Follow-up with the 12.1.0 prerelease (build 449)

The archive read on October 10 still contained no build-448 summaries. Its latest
versioned samples were build 447: Today had 77 windows, about 5.65 sampled minutes,
2.09% late callbacks and a worst callback interval of 674 ms; Trends had 10 windows,
about 31 sampled seconds, 1.54% late callbacks and a worst interval of 144.4 ms.
Both worst windows were beyond the first ten seconds, with nominal thermal state,
Low Power Mode off and sync inactive. These observations establish remaining stalls;
they cannot attribute the long interval to a particular function.

The older Instruments capture contains substantial SwiftUI graph and layout work
near hitches. The follow-up removes specific sources of unnecessary updates:

- Today gathers history-wide results locally and commits them without suspension,
  preserving the selected day's Rest spark and strap-over-Apple steps precedence.
  A reduced native SwiftUI probe with twelve staggered async reads evaluated its
  root body 13 times before batching and twice after, including initial layout.
  This measures update coalescing, not an iPhone scroll-rate improvement.
- Heart-rate workout annotations retain content-derived identity, including sport
  and source so coincident records remain distinct. Vertical iPhone drags do not
  mutate the chart pan state. Pinch zoom, horizontal pan and hold-to-scrub remain.
- Trends cards appear directly when materialized by the lazy stack instead of
  scheduling delayed rise/fade animations while scrolling.

The classic Today sync cue occupies a fixed gray icon slot beside the date (the
macOS toolbar uses the same cue). The Effort overlay and temporary long Rest caption
are removed; chunk transitions do not change those layouts. Existing sync debounce,
recording status and detailed Data Sources progress remain.

No additional capture, data export, dependency or background watcher is introduced.
An interactive device comparison is still needed to quantify this build's hitch
reduction. Raw traces and preference copies remain local and must not be attached
to a public PR; only the reviewed aggregate statistics above are suitable to share.
