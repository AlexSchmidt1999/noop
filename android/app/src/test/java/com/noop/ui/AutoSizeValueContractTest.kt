package com.noop.ui

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Pins the overflow signal that drives [AutoSizeValue]'s shrink loop (#2171).
 *
 * Compose can constrain an ellipsized paragraph to the Text's assigned width, leaving
 * `didOverflowWidth` false even though the rendered line ends in an ellipsis. The layout result exposes
 * that state separately through `isLineEllipsized(0)`. This source-level contract is intentional: the
 * composable cannot be laid out by the plain-JVM unit suite, while an instrumentation-only regression
 * would not run in the repository's normal Android CI job.
 */
class AutoSizeValueContractTest {

    /** Locate Components.kt from Gradle, IDE, or repository-root test working directories. */
    private fun componentsSource(): String {
        var root = File(System.getProperty("user.dir") ?: ".").canonicalFile
        repeat(4) {
            val candidate = File(root, "android/app/src/main/java/com/noop/ui/Components.kt")
            if (candidate.isFile) return candidate.readText()
            root = root.parentFile ?: root
        }
        error("Components.kt not found - this test must not pass by default")
    }

    @Test
    fun ellipsizedValuesKeepShrinkingUntilTheyFitOrReachTheFloor() {
        val source = componentsSource()
        val start = source.indexOf("internal fun AutoSizeValue(")
        val end = source.indexOf("\n@Composable\nfun StatTile(", start)
        assertTrue("AutoSizeValue was not found", start >= 0 && end > start)
        val autoSizeValue = source.substring(start, end)

        assertTrue(
            "an ellipsized line must drive the shrink loop even when didOverflowWidth is false",
            autoSizeValue.contains("result.isLineEllipsized(0)"),
        )
        assertTrue(
            "the shrink loop must retain its minimum-scale floor",
            autoSizeValue.contains("scale > minScale"),
        )
    }
}
