# Troubleshooting / FAQ

---
## FAQ List:
- [Table shows 0/N activations](#table-shows-0n-activations)
- [Authentication errors](#authentication-errors)
- [API Key rejected / 401 Unauthorized](#api-key-rejected--401-unauthorized)
- [Window opens off-screen after a monitor change](#window-opens-off-screen-after-a-monitor-change)
- [Nothing happens when I press `Ctrl+N`](#nothing-happens-when-i-press-ctrln)
- [Violations column shows `—` or stale count](#violations-column-shows--or-stale-count)
- [Edit dialog shows OK but nothing changes on the server](#edit-dialog-shows-ok-but-nothing-changes-on-the-server-)
- [Refresh feels slow / licenses take a long time to load](#refresh-feels-slow--licenses-take-a-long-time-to-load)
- [Status bar error disappears too quickly](#status-bar-error-disappears-too-quickly-)
- [Privacy Mode didn't pixelate a field](#privacy-mode-didnt-pixelate-a-field-)
---
## Table shows 0/N activations:
The counts load in the background after the initial list.
Wait a few seconds for them to populate, or open the detail view for a specific license to update it immediately.

## Authentication errors:
Double-check your `API_KEY` value. It must be a creator-scoped key (starts with `cgls_`).
You only have to create this once; every product uses the same `API_KEY`.

## API Key rejected / 401 Unauthorized:
The key must be creator-scoped (`cgls_` prefix), not a product-scoped or admin key.
Regenerate from the CG Lounge Creator dashboard, then delete `creator_secret.config` (located next to `license_manager.py`) so the app re-prompts on next launch.

> **Note:** The app no longer uses `config.json`. Your API key is stored only in `creator_secret.config`. If you still have an old `config.json` from a previous version, it can be safely deleted — it is not read by the app.

## Window opens off-screen after a monitor change:
Snap Tabs resizes to fit columns, and window geometry is persisted via `Creator License Manager.ini`, etc.
If you need to reset window position, delete the settings file:
- **Windows:** `C:/Users/<YOUR_USERNAME>/AppData/Roaming/CGLounge/Creator License Manager.ini`
- **Linux:** `~/.config/CGLounge/Creator License Manager.conf`
- **macOS:** `~/Library/Preferences/com.cglounge.Creator License Manager.plist`

## Nothing happens when I press `Ctrl+N`:
The shortcut is context-aware: on the **Licenses** tab it creates a license; on the **Trial Codes** tab it creates a trial code.

## Violations column shows `—` or stale count:
Violation counts are fetched as part of the main `listLicenses` call and should populate immediately on every refresh.
If the column shows `—`, press `F5` to trigger a full refresh. You can also right-click any row and choose **Refresh License** to update that row individually, or open **View Details** to pull the latest data for that license.
> If it still doesn't update, please contact CG Lounge Admin, or open a bug report [HERE](https://github.com/Nightingale13/CGLCreatorLicenseManager/issues).

## Edit dialog shows OK but nothing changes on the server: 
The edit dialog only sends changed fields.
If you opened Edit, made no changes, and clicked OK, the app intentionally skips the API call.
Also note: `licenseType` is not a supported `updateLicense` field — changing Type in the UI will not persist to the server.

## Refresh feels slow / licenses take a long time to load:
Refresh runs one `listLicenses` call per product. If you have many products, these calls run sequentially and can take a few seconds in total. Activation and violation counts are included in the same response — no additional per-row calls are made.

## Status bar error disappears too quickly: 
Errors auto-clear after 8 seconds. Re-trigger the action to see the message again.
> If you are experiencing an issue, please open a bug report [HERE](https://github.com/Nightingale13/CGLCreatorLicenseManager/issues).

## Privacy Mode didn't pixelate a field: 
Privacy Mode only covers the columns/fields wired into the `PixelatedLabel` paths (key, email, productID, code).
If a newly added field leaks sensitive data, it needs to be added to the pixelation list in code.
> If that is the case, please open a bug report [HERE](https://github.com/Nightingale13/CGLCreatorLicenseManager/issues).
