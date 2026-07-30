# Project Notes

## Core Rules
- The public repository contains templates only. Device serials, attendee names, event identifiers and result logs remain local.
- `price_index` and `session_index` are verified by a rehearsal before a formal run.
- `if_commit_order=true` only submits an order. Payment remains a manual user action.
- Two public paths are supported: `preselected_sku=true` for direct rapid taps after reservation, and `preselected_sku=false` for index-based session/ticket-tier selection.
- User-facing indexes are one-based and counted left-to-right across the visible cards; they must be confirmed by rehearsal. Price text is not used on the sale-critical path.
- Default templates assume the user is already on the detail page; event metadata is optional unless `auto_navigate=true`.

## Release Check
- No real `config/*.jsonc` files are tracked.
- No `logs/`, `.venv/`, or test artifacts are tracked.
- Documentation describes Android UIAutomator2 only.
- Documentation names the four user-facing flows: extra-selection rehearsal/formal and preselected rehearsal/formal.
