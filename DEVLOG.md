# Damai Android Rush Demo - Development Log

## Current Status
- **Version**: V0.1
- **Positioning**: Minimal Android UIAutomator2 purchase-flow example.
- **Completed**: Android-only core, rehearsal/formal Windows launchers, public configuration templates, setup and operational docs.
- **Open**: App UI identifiers and card ordering must be verified against each event before a formal run.

---

## Version History

### V0.1 - 2026-07-28
**Design Decisions**:
- Reduced the published copy to the Android UIAutomator2 entry path and explicit JSONC configuration.
- Kept one Android fast path with a single confirmation-page branch: rehearsal stops, formal submits.

**Progress**:
- [x] Created a sanitised public project structure.
- [x] Added setup, parameter and pre-sale documentation.
- [x] Added one-click and VS Code launch entries for rehearsal and formal modes.
