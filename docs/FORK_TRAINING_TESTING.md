# iPhone training controls in the fork test build

The fork test build combines the AI compatibility fixes, Today/sync rendering changes,
and iPhone training controls. Upstream PRs wait for the owner's device testing.
Changes are kept in separate commits and stacked fork PRs.

## Behavior

- Three favorites in Settings can select a sport or an existing Lift Log program.
  Defaults are strength training, running and an unassigned third slot. Names are editable.
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

The Training widget uses three equal favorite tiles when idle and compact favorite buttons
below the elapsed time and session controls while training. During confirmation or a save
error, that action gets the available space. Lock Screen controls use distinct pause/resume
and stop symbols with complete VoiceOver labels; the Lift completed-set warning remains in
the confirmation accessibility hint when the accessory cannot fit the full sentence.

Workout and Lift activities share the same controls and native date-driven clocks. Lift keeps
exercise, phase, repetitions/weight, next set and heart rate in a compact layout; confirmation
prioritizes the prompt and saved-set warning. Existing update throttles are unchanged.

Build 437 was checked with rendered SwiftUI layouts for idle, active, paused and confirmation
states, including long German exercise names, standard iOS font sizes and small widget dimensions.
The rendered Live Activity states passed a 160-point height check. These local Mac layout renders
do not reproduce iOS vibrancy or system presentation; test light/dark, tinted widgets,
Always-On contrast and larger text on the phone. Verify both cancel and confirmed end in the
new layout, including during a Lift rest. The widget gallery is now confirmed visible by the
user on the phone.
