# Manual workout sample processing

The local build-450 recording contains 105 seconds of foreground use during a normal
sport recording, including a 518 ms callback interval on Today. It measures delayed
display-link callbacks, without call stacks that would attribute those delays to a
particular function. Raw device logs remain in ignored local storage.

The baseline sample path calculated a mean, fingerprinted and scored the growing
pulse window, then JSON-encoded and stored the entire workout snapshot on the main
actor. The benchmark calls those production functions with synthetic samples.

## Reproducing the baseline

```sh
xcodegen generate
xcodebuild -project Strand.xcodeproj -scheme Strand -configuration Release \
  -destination 'platform=macOS,arch=arm64' -derivedDataPath build/training-macos-release \
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES ENABLE_TESTABILITY=YES \
  'OTHER_SWIFT_FLAGS=$(inherited) -D DEBUG' \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY= \
  -only-testing:StrandTests/WorkoutSampleBenchmarkTests test
```

The existing test bundle requires DEBUG-only test accessors. The command enables
those accessors while retaining Release optimization (`-O`); the measured capture,
scoring and encoding functions have no DEBUG alternative. Device builds use ordinary
Release settings. The benchmark skips unoptimized Debug builds.

Each size gets five warmups and 101 measured iterations. Nonempty scoring windows
have a different fingerprint on each iteration, so scoring includes a cache miss.
Scoring and encoding are timed separately. Baseline capture is the complete synchronous
`AppModel.captureWorkoutSample` call, including publisher callbacks and persistence.
Its input starts with the listed number of samples and accepts one additional sample.
Initialization, fixture creation and result assertions are outside the timed calls.

| Starting samples | Scoring median / p95 | Encoding median / p95 | Synchronous capture median / p95 |
| --- | --- | --- | --- |
| 0 | 0.0053 / 0.0065 ms | 0.0039 / 0.0065 ms | 0.1702 / 0.2253 ms |
| 600 | 0.0078 / 0.0099 ms | 0.3110 / 0.3394 ms | 0.4922 / 0.5579 ms |
| 3,600 | 0.0203 / 0.0215 ms | 1.8089 / 1.8705 ms | 2.1028 / 2.1775 ms |
| 7,200 | 0.0353 / 0.0395 ms | 3.6312 / 3.7570 ms | 4.1668 / 4.2842 ms |

Encoding accounts for most of this measured cost. Moving it off the main actor is
worth testing, but these numbers do not explain the full 518 ms device delay.

## After moving scoring and encoding off the main actor

The mean uses a single reduction without an intermediate array. A main-actor task
awaits one detached scoring-and-encoding job at a time, with one latest pending
snapshot. Samples stay in `activeWorkout`; coalescing replaces derived work, without
dropping readings. Higher peaks from duplicate seconds also replace pending work.
Results must match both session ID and revision. Start, pause, resume, discard and
background checkpoints invalidate older results. Persistence retains its key and
Codable shape, with no added checkpoint timer. Lifecycle checkpoints synchronously
bank the full window and its latest completed Effort estimate; final saving still
recomputes Effort using the existing resting-HR input.

The updated benchmark times capture and a valid result merge separately. The merge
includes publishing a changed Effort estimate and `UserDefaults.set` of encoded data.
Preparation and computation of that result are outside these main-actor timings.
The table sums capture and merge for each trial before taking its median and p95.
The production worker drains before the next trial. Actor scheduling and SwiftUI
rendering are outside these function timings. A 7,200-sample p95 above 2 ms fails the
opt-in Release benchmark.

| Starting samples | Capture median / p95 | Result merge median / p95 | Main-actor total median / p95 |
| --- | --- | --- | --- |
| 0 | 0.0145 / 0.0170 ms | 0.3911 / 0.4361 ms | 0.4064 / 0.4535 ms |
| 600 | 0.0150 / 0.0190 ms | 0.3911 / 0.4522 ms | 0.4051 / 0.4676 ms |
| 3,600 | 0.0175 / 0.0255 ms | 0.3996 / 0.4639 ms | 0.4177 / 0.4837 ms |
| 7,200 | 0.0218 / 0.0355 ms | 0.5859 / 0.6795 ms | 0.6102 / 0.7050 ms |

The same isolated scoring calls after the change measured median / p95 of
0.0219 / 0.0268, 0.0262 / 0.0332, 0.0393 / 0.0459 and 0.0551 / 0.0663 ms for the
four sizes. Encoding measured 0.0214 / 0.0259, 0.3445 / 0.3962, 1.8802 / 2.1310 and
3.8180 / 4.1372 ms. Those functions retain their algorithms and run off the main actor
in the sample path; this change targets main-actor occupancy rather than total CPU.

At 7,200 starting samples, measured main-actor p95 falls from 4.2842 to 0.7050 ms,
about 84%. The 35 focused macOS tests pass, covering numeric and snapshot equivalence,
unchanged pulse values, duplicate seconds and measurement gaps; obsolete results
after newer samples, pause, resume, replacement, checkpoint and finish; and a failed
database write followed by a successful retry with every sample retained.

No chart renderer, nightly analysis, global Today refresh, widget comparison or
ActivityKit throttle was changed. This is Apple app scheduling and encoding; the
shared numerical and storage contracts are unchanged. Android is outside this fork
change. An iPhone comparison after installation is still required before claiming
the recorded scrolling stalls are resolved.

These are local CPU costs on an Apple M4 Max with Xcode 27.0. They do not measure
iPhone scrolling, rendered frames, GPU work or physical disk durability. UserDefaults
writes retain the platform's existing persistence semantics.
