# Project Notes

## Core Rules
- The public repository contains templates only. Device serials, attendee names, event identifiers and result logs remain local.
- `price_index` and `session_index` are verified by a rehearsal before a formal run.
- `if_commit_order=true` only submits an order. Payment remains a manual user action.
- Two public paths are supported: `preselected_sku=true` for direct rapid taps after reservation, and `preselected_sku=false` for index-based session/ticket-tier selection.
- User-facing indexes are one-based and counted left-to-right across the visible cards; they must be confirmed by rehearsal. Price text is not used on the sale-critical path.
- Default templates assume the user is already on the detail page; event metadata is optional unless `auto_navigate=true`.
- The recommended entry is `start-console.bat`: it generates ignored local config files and starts known BAT files without accepting arbitrary commands.
- Formal controls stay separate from rehearsal controls and require an explicit no-payment confirmation.
- The status area should answer the next user decision: show “演练是否就绪” with “可以开始 / 进行中 / 等待环境”, not only an internal process state.

## Release Check
- No real `config/*.jsonc` files are tracked.
- No `logs/`, `.venv/`, or test artifacts are tracked.
- Documentation describes Android UIAutomator2 only.
- Documentation names the four user-facing flows: extra-selection rehearsal/formal and preselected rehearsal/formal.
- The console binds only to `127.0.0.1` and displays environment, device, config and process status.
- The run handler must declare the shared process handle as global; otherwise saving succeeds but every launch fails before starting the BAT file.
- The beginner guide should follow the console's visible labels and decisions, not expose internal JSON fields unless the user chooses the direct BAT path.
- README is the low-friction public entry page: keep it to the console workflow, capabilities and boundaries; put implementation details in a separate technical note.
