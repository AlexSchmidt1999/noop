# Apple chart rendering

The local Today and Trends traces show hitches and substantial SwiftUI update work.
`TrendChart` and `OverviewHRChart` now use Apple's vectorized `LinePlot` / `AreaPlot`
on iOS 18+ and macOS 15+. Older systems retain the mark-based path. The existing
samples, segment keys, drawing budgets, axes, gradients, selection, zoom bindings,
annotations and accessibility remain in place; bar rendering is unchanged.

This follows Apple's [vectorized-plot guidance](https://developer.apple.com/videos/play/wwdc2024/10155/):
process a homogeneously styled collection together rather than create a mark per point.
It adds no dependency or custom renderer.

## Local verification

An ignored native macOS probe compares the previous production chart implementations
at `b1db8606` with the new implementations, using synthetic data. It warms up four
renders and takes the median of eight subsequent renders through `ImageRenderer`.
The measurements include constructing and rasterizing the chart, not on-screen scrolling.

| Production chart | Previous median | New median |
| --- | --- | --- |
| Trends, 288 points | 6.39 ms | 4.85 ms |
| Trends, 365 points | 7.59 ms | 5.68 ms |
| Trends, 288 points with separate segments | 6.88 ms | 5.08 ms |
| Overview HR, 288 points | 6.38 ms | 4.67 ms |
| Overview HR with sleep, workout and recovery annotations | 8.86 ms | 6.83 ms |

Eleven render comparisons cover empty, single-point, sparse and dense series,
separate segments, no area fill, bars, and annotated HR. Ten pairs are pixel-identical;
the annotated HR pair differs by less than 0.0001 per channel on the 0–255 scale.
The probe and generated images remain under ignored `build/performance/chart-plots/`.

Both Apple app targets compile. The design-package suite passes 133 tests with the
pre-existing English-only `testRecoveryStateWords` excluded: that test reports five
localized-word assertion failures on a German host. The rendering changes do not
modify those words or expectations.

These results establish a smaller local rendering cost, not an iPhone frame-rate
improvement. A repeat of the device scroll captures is required before claiming the
reported Today and Trends hitches are resolved. No raw device logs or traces are
included in this change. Android is outside the requested fork scope.
