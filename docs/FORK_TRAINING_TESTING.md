# iPhone training controls in the fork test build

The fork test build combines the AI compatibility fixes, Today/sync rendering changes,
and iPhone training controls. Upstream PRs wait for the owner's device testing.
Changes are kept in separate commits and stacked fork PRs.

## Behavior

- Three favorites in Settings can select a sport or an existing Lift Log program.
  Defaults are strength training, running and an unassigned third slot. Names are editable.
  On iPhone, open More → Settings → Training favorites (also reachable through Today's settings button).
  The widget's Configure tile opens this same editor directly as a More-tab submenu, including
  after a cold launch. Mandatory onboarding/terms and automatic launch sheets finish first.
- The Training widget starts favorites; the running session offers Pause, Resume and End.
  The Lock Screen widget selects a favorite in its configuration. Normal workouts have
  a new Live Activity; Lift Log reuses its existing one.
- End requires a second tap in the widget or expanded Live Activity within 30 seconds.
  The confirmation is bound to the session and a single token. Lift Log saves completed
  sets and leaves unfinished sets unperformed; external ending does not update templates.
- After a session receives its first accepted live pulse, ten minutes without a new
  accepted live sample pauses it. Equal bpm values in new packets count; history does not.
  Sensorless/GPS-only sessions remain available. Resume is explicit, including after reconnection.
- The existing coaching Live Sessions keep their original stale-signal auto-end behavior.
- Lift pause freezes its stage/rest clocks and suppresses rest warnings. Actual set
  timestamps remain intact; active duration excludes pauses using the existing workout field.
- Saves are awaited. A failed save leaves the paused session available; retries use stable IDs.
  Manual workout scoring uses an immutable snapshot away from the main actor.

The shared Swift app still compiles on macOS. New controls are iPhone-only. This fork
change covers Apple platforms only. Stored database schema and backup keys are unchanged.

## Background and permission behavior

Enable training reminders explicitly in Settings. Denied notification permission does not
prevent the pause guard. Existing Live Activity switches still apply; normal workouts get
their own switch. iOS may require authentication before accepting Lock Screen actions.

A suspended process cannot execute an exact ten-minute timer. Local notifications are
scheduled ahead of time, refreshed at most every 30 seconds, with a safety allowance.
The next app wake reconciles the saved deadline before accepting biometric data. A recovery
checkpoint has the same allowance to avoid an early pause after a crash; the effective
recovery deadline can be up to 30 seconds later than the last actual receipt plus ten minutes.
Focus and system scheduling can further delay notification delivery. No push service or
additional background mode is introduced.

## Device test checklist

1. Review the fork PRs and exact green security run. Install using the existing reviewed
   local signing workflow; retain the bundle ID so existing data stays available.
2. Configure all three favorites, including a Lift Log program. Enable reminders and add
   the Training widget and an accessory Lock Screen widget.
   Tap an unassigned slot's Configure link with NOOP closed and already open; both must open
   Training favorites directly. Configured slots must still start their assigned training.
3. Start each favorite from the widget with NOOP closed. Check the training/Live Activity
   and live heart rate; sensorless recording must also remain possible.
4. With a WHOOP session receiving pulse, lock the phone and remove the strap. Verify the
   ten-minute pause/reminder, no repeated prompts while paused, and explicit Resume.
5. Repeat during a Lift rest and a working set. Check frozen clocks, preserved inputs,
   suppressed rest buzzes and active duration after saving.
6. Cancel End once; then confirm End directly in the widget and expanded Live Activity.
   Repeat after the confirmation expires. Old controls must not end a new session.
7. Reopen NOOP after a background termination and a long pulse gap. Verify restoration
   and the pause before new pulse data is captured.
8. Use Today while syncing a long history, scroll charts, and record device/model/build
   and any visible hitch. Synthetic Mac traces do not establish iPhone frame smoothness.

Build/test evidence and actual device results should accompany each later upstream PR.

## Widget and Live Activity presentation

The Training widget uses three equal favorite tiles with centered icons and two-line labels
when idle, and compact favorite buttons below the elapsed time and session controls while
training. During confirmation or a save
error, that action gets the available space. Lock Screen controls use distinct pause/resume
and stop symbols with complete VoiceOver labels; the Lift completed-set warning remains in
the confirmation accessibility hint when the accessory cannot fit the full sentence.

Workout and Lift activities share the same controls and native date-driven clocks. Lift keeps
exercise, phase, repetitions/weight, next set and heart rate in a compact layout; confirmation
prioritizes the prompt and saved-set warning. Existing update throttles are unchanged.
Workout activities use the app's existing workout-type icon component, including its custom glyphs.
The raw sport travels separately from the localized title; older snapshots remain readable.
System workout glyphs fit inside the component's existing square size, preserving their proportions.

Build 437 was checked with rendered SwiftUI layouts for idle, active, paused and confirmation
states, including long German exercise names, standard iOS font sizes and small widget dimensions.
The rendered Live Activity states passed a 160-point height check. These local Mac layout renders
do not reproduce iOS vibrancy or system presentation; test light/dark, tinted widgets,
Always-On contrast and larger text on the phone. Verify both cancel and confirmed end in the
new layout, including during a Lift rest. The widget gallery is now confirmed visible by the
user on the phone.

## Today sync layout follow-up (build 438)

Classic Today no longer inserts a separate syncing/chunk note near its scores. Progress stays
in the existing header and Data Sources row; the Data Sources row remains present during sync.
Liquid Today's history row also remains present before the first completed sync. Both detailed
rows reuse the header's existing sync-end debounce and shared chunk copy. Progress text stays
on one line; classic sync errors retain their full readable explanation.

The local macOS app build and 20 targeted snapshot/sync tests passed. The iOS Release app,
widget and watch targets compiled; translation, doc-comment and source/binary security checks
passed. Local widget layout renders remain within the previous size limits. On iPhone, repeat
a long sync with Liquid Today enabled and disabled, while scrolling and switching tabs. These
checks do not establish that the owner's intermittent hitch has disappeared on hardware.

## Configure link follow-up (build 440)

Unassigned favorite tiles and empty training widgets use a native link to the existing
Training favorites editor. Configured slots retain their Start intents. The request waits
for launch gates, opens a single More-tab submenu, and leaves an active training session intact.
The macOS app and ten targeted snapshot/navigation tests passed; the iOS Release app,
widgets and watch targets compiled. Translation, source hygiene and source/binary policy
checks passed. Cold/warm widget taps and the visible editor still require iPhone verification.
