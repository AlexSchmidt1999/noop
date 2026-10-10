# Manual workout sample processing

The local build-450 recording contains 105 seconds of foreground use during a normal
sport recording, including a 518 ms callback interval on Today. It measures delayed
display-link callbacks, without call stacks that would attribute those delays to a
particular function. Raw device logs remain in ignored local storage.

The synchronous sample path currently calculates a mean, fingerprints and scores the
growing pulse window, then JSON-encodes and stores the entire workout snapshot on the
main actor. The benchmark calls those production functions with synthetic samples.

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
Scoring and encoding are timed separately. Capture is the complete synchronous
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

These are local CPU costs on an Apple M4 Max with Xcode 27.0. They do not measure
iPhone scrolling, rendered frames, GPU work or physical disk durability. UserDefaults
writes retain the platform's existing persistence semantics.
