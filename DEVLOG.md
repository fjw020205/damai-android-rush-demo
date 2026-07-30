# Damai Android Rush Demo - Development Log

## Current Status
- **Version**: V0.2
- **Positioning**: Minimal Android UIAutomator2 example with two practical purchase paths.
- **Completed**: Android-only core, one-based left-to-right session/ticket-tier path, reservation-ready direct-tap path, T0/T0+10ms/T0+20ms rehearsal launchers, public templates and operational docs.
- **Open**: App UI identifiers, reservation state and card ordering must be verified against each event before a formal run.

---

## Version History

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
