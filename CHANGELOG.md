# Change Log
All notable changes to this project will be documented below.

## [1.0.0] - 2026-04-27
First public release. Baseline feature set of the CG Lounge Creator License Manager.

### Core License Management
- List, create, edit, revoke, suspend, and reinstate licenses against the CG Lounge License Server.
- Reset machine activations on a selected license.
- Multi-select support on the Licenses table — action buttons and context menu operate on all selected rows at once.
- Confirmation dialogs for every destructive action (Revoke, Suspend, Reset Activations, Delete).
- **Edit License** dialog with variant/tier change, max machines (pulled from the variant/tier default), status change, and optional expiration. Only changed fields are sent to the server. Orange border highlights any field that differs from its original value.
- Confirmation prompt when overriding the variant's default Max Machines value.
- **License Detail** dialog with three tabs: Overview, Activations, and Violations. Resolve false-positive violations directly from the dialog.

### Trial Codes
- Full CRUD for trial redemption codes on a dedicated **Trial Codes** tab.
- **Create Trial Code** dialog with product selection, configurable trial duration (days), optional expiration date, and a random code generator.
- **Edit Code** dialog for toggling active state, max uses, and expiry. Orange border highlights any field that differs from its original value.
- Delete, enable/disable, copy, and multi-select actions mirrored from the Licenses tab.

### Products & Filtering
- Products fetched dynamically at launch and on every refresh via `POST /listProducts` (`live`, `unlisted`, and `archived` included).
- Product-name and product-status filter dropdowns in the toolbar, colour-coded (🟢 Active / 🟠 Unlisted / 🟡 Archived).
- Free-text search bar over license key, email, country, and code.
- Per-tab filter checkboxes: **Hide Trials**, **Hide Disabled**, **Hide Expired** on Licenses; **Hide Disabled** and **Hide Expired** on Trial Codes.
- Sortable tables with sort order persisted across launches via `QSettings`.

### Activation & Violation Tracking
- Activation counts (`machinesUsed`) and unresolved violation counts (`unresolvedViolationsCount`) are returned directly by `listLicenses` — both columns populate immediately on every load with zero extra server calls.
- 60-second auto-refresh timer re-runs `listLicenses` to keep both activation and violation counts current automatically.
- Violation and activation counts are also refreshed per-row via **View Details**, **Refresh License** (right-click), or **Reset Activations**.
- Violation counts > 0 render in red.
- Status bar shows a live countdown to the next auto-refresh.
- Opening **View Details** for a license fetches its full activation list and live violation details, and updates that row's counts immediately.
- **Activations** tab inside the detail dialog has a live hostname/country filter and an **Only active sessions** toggle (relevant for `floating` licenseType only).

### UI / UX
- Tabbed interface (Licenses / Trial Codes) with active tab persisted across launches.
- CG Lounge theme applied app-wide.
- **Privacy Mode** toolbar toggle that pixelates sensitive columns and dialog fields (license key, email, productID, code).
- **Snap Tabs** toolbar toggle that auto-resizes the window to fit the current tab's column widths and re-snaps on tab switch or refresh.
- **Snap Centre** toolbar toggle (enabled only when Snap Tabs is on) that re-centers the window on the current screen after each snap.
- Last table column auto-sized to its widest content via `QHeaderView.ResizeToContents`.
- Context menus on both tables mirroring the bottom action buttons.
- Thin purple **loading bar** below the table during any in-flight server request, with a wait cursor. All API calls run on a background `QThread` so the UI stays responsive.
- Documentation button (**?**) in the toolbar opens this README in the browser.
- Bug report button (**🐛**) in the toolbar opens the GitHub Issues page for filing reports.
- Result counter label showing visible / total licenses.

### Keyboard Shortcuts
- `F5` — refresh all (products, licenses, trial codes).
- `Ctrl+N` — context-aware: creates a license on the Licenses tab, a trial code on the Trial Codes tab.

### Anti-Piracy Integration
- **Threat lvl** column (0–4) colour-coded with full-description tooltips, driven by the CG Lounge anti-piracy system.
- License statuses (Active / Degraded / Suspended / Revoked / Expired) colour-coded via a custom `StatusDelegate`.
- Product-status indicators pulled live from CG Lounge and shown per row.
- **Resolve Selected** action on the Violations tab to clear false positives.

### Configuration & Security
- First-launch password-masked prompt for a creator-scoped API key (`cgls_…`), written to `creator_secret.config` next to `license_manager.py`.
- Optional `SERVER_URL` override in the config file.
- API key stored only locally; delete the config file to force a re-prompt.
- Single creator-scoped key reused across all products on the creator account.

## [1.0.0-beta] - 2026-04-10
- Initial private beta for internal testing.