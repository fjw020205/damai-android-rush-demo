# Damai Android Rush Demo - Development Log

## Current Status
- **Version**: V0.3
- **Positioning**: Minimal Android UIAutomator2 example with two practical purchase paths.
- **Completed**: Android-only core, one-based left-to-right session/ticket-tier path, reservation-ready direct-tap path, T0/T0+10ms/T0+20ms rehearsal launchers, minimal templates, USB debugging guide, operational docs and a local control console.
- **Open**: App UI identifiers, reservation state and card ordering must be verified against each event before a formal run.

---

## Version History

### V0.8 - 2026-07-31
**Design Decisions**:
- Make the local console the primary user story in the beginner documentation; configuration files and direct BAT entry points move to an optional advanced section.

**Progress**:
- [x] Reworked `docs/user-guide.md` around the visible console states, fields and buttons.
- [x] Added an explicit “you do not need to copy files or edit variables” path before any technical explanation.

### V0.9 - 2026-07-31
**Design Decisions**:
- Keep README as a short product entry page and move implementation details into `docs/technical-notes.md`.
- Explain USB file-transfer mode as an optional troubleshooting switch, while treating ADB authorization and `device` status as the actual readiness signal.

**Progress**:
- [x] Rewrote README around the local console and reduced exposed filenames and configuration vocabulary.
- [x] Added a separate technical note covering modes, timing, formal readiness and USB/ADB boundaries.

### V0.7 - 2026-07-31
**Design Decisions**:
- Keep the README as a concise project overview and move the full beginner workflow into a standalone user guide organized around the local console.

**Progress**:
- [x] Added `docs/user-guide.md` with mode selection, status meanings, field explanations, rehearsal, formal launch and troubleshooting.
- [x] Linked the guide from the README and quick-start document.

### V0.6 - 2026-07-31
**Design Decisions**:
- Expose formal-task readiness separately from rehearsal process state. A formal task is ready only while the selected formal BAT process is running; a configured future sale time without that process is shown as not ready.

**Progress**:
- [x] Added the fifth status row “正式任务状态” with green, amber and red states.
- [x] Prefer the most recently updated formal config when both formal templates exist locally.

### V0.5 - 2026-07-31
**Design Decisions**:
- Keep process ownership in the console module global so the save-and-run endpoint can update the same status object used by polling.
- Treat missing Python dependencies as an environment issue and fall back to system `adb` for device discovery when possible.

**Progress**:
- [x] Fixed the rehearsal launch error caused by a missing `global _process` declaration.
- [x] Installed the project environment dependencies and confirmed the connected Xiaomi device is visible to the console.

### V0.4 - 2026-07-30
**Design Decisions**:
- Keep the existing BAT and mobile hot paths unchanged; add a Python standard-library local console for environment checks, minimal form input, config generation and launch.
- Bind the console to `127.0.0.1`; formal submission requires an explicit confirmation and never automates payment.

**Progress**:
- [x] Added `start-console.bat`, `console_server.py` and `console/index.html`.
- [x] Validate generated configurations through the existing `Config.load_config` before writing them.
- [x] Updated the README to make the console the default path while retaining direct BAT entry points.

### V0.3 - 2026-07-30
**Design Decisions**:
- Default configuration assumes manual detail-page preparation and keeps event metadata out of the normal user workflow.
- Empty attendee lists are accepted when the app has already preselected attendees; users only add names when they explicitly disable that skip.

**Progress**:
- [x] Added the Android USB debugging guide with a Xiaomi HyperOS example.
- [x] Reduced the documented configuration to sale time, optional card numbers and exceptional device/attendee fields.
- [ ] Verify minimal templates on a clean device.

### V0.2 - 2026-07-30
**Design Decisions**:
- Documented two user-facing modes: extra selection by one-based left-to-right card numbers and direct taps after reservation has locked the SKU.
- Kept the direct-tap timing variants as rehearsal-only probes; formal mode reads the chosen `cta_first_tap_delay_ms` from its private config.

**Progress**:
- [x] Published the preselected-SKU code path, templates and Windows launchers.
- [x] Reworked README and operational docs around download, configuration, rehearsal and formal launch.
- [ ] Verify the public setup and a no-submit rehearsal in a clean environment.

### V0.1 - 2026-07-28
**Design Decisions**:
- Reduced the published copy to the Android UIAutomator2 entry path and explicit JSONC configuration.
- Kept one Android fast path with a single confirmation-page branch: rehearsal stops, formal submits.

**Progress**:
- [x] Created a sanitised public project structure.
- [x] Added setup, parameter and pre-sale documentation.
- [x] Added one-click and VS Code launch entries for rehearsal and formal modes.
