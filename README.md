# CG Lounge - Creator License Manager

An admin interface for Creators to manage their Product Licenses and Discount/Trial codes hosted on CG Lounge.
Built with Python and PySide6.

![License Manager UI](license_manager/icon.png)

---

> [!CAUTION]
> **The `master` branch is under active development**  
> It is **not stable** and may contain breaking changes, bugs, and unfinished features at any time.
>
> **✅ For stable, production-ready code, please use the latest release instead:**
>
> **[⬇️ Download Latest Stable Release](https://github.com/Nightingale13/CGLCreatorLicenseManager/releases/latest)**

---
## Table of Contents
- [Requirements](#requirements)
- [Setup](#setup)
  - [Run](#1-run)
  - [Config (Optional)](#2-config-optional)
- [Interface Overview](#interface-overview)
  - [Toolbar](#toolbar-top)
  - [License Table](#license-table-center)
  - [Action Buttons](#action-buttons-bottom)
  - [Right Click Menu](#right-click-context-menu)
  - [Loading Bar](#loading-bar)
  - [Status Bar](#status-bar)
- [Status Colours](#status-colours)
- [Threat Levels](#threat-levels)
- [Edit License Dialog](#edit-license)
- [License Detail Dialog](#license-detail)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Activation Counts](#activation-counts)
- [Troubleshooting](#troubleshooting)
- [Change Log](#change-log)
- [Contributing](#Contruibutions)
---

## Requirements
- [Python 3.9](https://www.python.org/downloads/release/python-390/) or newer
- [PySide6](https://pypi.org/project/PySide6/)
```bash
pip install PySide6
```
---

## Setup
### 1. Run
```bash
python license_manager.py
```
> A popup will appear asking for your Creator API Key. "cgls_.....".
Once entered, the app will pull your poducts, licenses, trials and discount codes.
### 2. Config (Optional)
After you enter your API Key, the app creates a `creator_secret.config` in the same location as `license_manager.py`.
This is the only location your API Key is stored - the app keeps no memery of it.
Deleting the `creator_secret.config` file will make the app prompt for a new API Key on launch.
#### creator_secret.config:
```config
API_KEY=cgls_..............................................................
SERVER_URL=
```
| Field        | Required | Description                                                                                                                                                                |
|--------------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `API_KEY`    | Yes      | Your creator-scoped API key from the CG Lounge License Server dashboard.<br/><i>(Remember, you only need one for your Creator Account. All products use the same API Key.) |
| `SERVER_URL` | No       | Override the default server URL.                                                                                                                                           |
---

## Interface Overview
![License Overview](_readme_images/LicenseManager.jpg)
### Toolbar (top)
| Control             | Description                                                                                                    |
|---------------------|----------------------------------------------------------------------------------------------------------------|
| **Product Status**  | Filter the table by product status, pulled from CG Lounge:<br/>🟢 **Active**, 🟠 **Unlisted**, 🟡 **Archived** |
| **Product**         | Filter the table by product name.                                                                              |
| **Search Bar**      | Filter table by `license key`, `email`, `country`, `trial/discount` `code` etc.                                | |
| **Privacy Mode** ☑️ | Pixelates sensitive columns (key, email, productID, code, etc) in fields in dialogs.                           |
| **Result counter**  | Shows how many licenses are currently visible/loaded.                                                          |
| **? button**        | Opens this documentation in your browser.                                                                      |
### Licenses Tab (center)
The Licenses Tab shows all licenses for the selected product(s).
#### Filters:
| Checkbox             | Description                                    |
|----------------------|------------------------------------------------|
| **Hide Trials** ☑️   | Toggle to hide trial-variant licenses          |
| **Hide Disabled** ☑️ | Toggle to hide revoked and suspended licenses  |
| **Hide Expired** ☑️  | Toggle to hide licenses past their expiry date |
#### Licenses:
| Column             | Description                                                                                         |
|--------------------|-----------------------------------------------------------------------------------------------------|
| **Status**         | Colour-coded depending on the licenses current status, (see [License Statuses](#license-statuses)). |
| **Product Status** | Displays the product status under which each key is assigned.                                       |
| **License Key**    | Truncated key — hover to see the full value.                                                        |
| **Email**          | Customer email address.                                                                             |
| **Tier**           | License variant (e.g. indie, studio).                                                               |
| **Type**           | `per-machine`, `floating`, or `site`.                                                               |
| **Sale Date**      | Purchase/Creation date.                                                                             |
| **Expires In**     | Time remaining, or "Perpetual".                                                                     |
| **Activations**    | Active machine count / max (updates automatically every 60 seconds).                                |
| **Refunded**       | Yes if a refund or chargeback was processed.                                                        |
| **Disabled**       | Yes if the license is revoked or suspended.                                                         |
| **Expired**        | Yes if the license has passed its expiry date.                                                      |
| **Threat lvl**     | Anti-piracy threat level 0–4 (hover for description), (see [Threat Levels](#threat-levels))         |
| **Product**        | Product name from CG Lounge.                                                                        |
Double-click any row to open the [License Detail](#license-detail) dialog.
### Action Buttons (bottom)
| Button                | Description                                                                             |
|-----------------------|-----------------------------------------------------------------------------------------|
| **Refresh**           | Reload all licenses from the server (also `F5`)                                         |
| **+ Create License**  | Open the create dialog (also `Ctrl+N`)                                                  |
| **Edit Selected**     | Edit the selected license — variant, license type, max machines, status, and expiration |
| **View Details**      | Open the full detail view for the selected license                                      |
| **Revoke License**    | Permanently revoke the selected license(s)                                              |
| **Suspend License**   | Temporarily suspend the selected license(s)                                             |
| **Reinstate License** | Re-enable a revoked or suspended license                                                |
| **Reset Activations** | Delete all machine activations for the selected license(s), allowing fresh activations  |
| **Copy Key**          | Copy the license key(s) to clipboard                                                    |
> All destructive actions (Revoke, Suspend, Reset Activations) show a confirmation dialog before proceeding.
You can select multiple rows and act on them all at once.

### Right-Click Context Menu

Right-clicking any row shows a context menu with the same actions as the bottom buttons.

### Loading Bar

A thin purple progress bar appears below the table whenever a server request is in flight.
The cursor also changes to a wait cursor during this time. All API calls run on a background thread so the UI stays responsive.

### Status Bar

![Status Bar](_readme_images/StatusBar.jpg)

The status bar at the bottom of the window shows the result of the last action (e.g. "Loaded 42 licenses", "License updated.").
Errors appear in red with an 8-second timeout. The right side of the status bar shows a live countdown to the next automatic activation count refresh.
---

## License Statuses
The **License Status** column is updated automatically by the CG Lounge License Server's anti-piracy system.
However, you have full control to update any status in the License Manager by using the [Edit Dialog](#edit-license) or the [Action Buttons](#action-buttons-bottom) when a license is selected.

| Colour        | Status        | Description                                               |
|---------------|---------------|-----------------------------------------------------------|
| 🟢 **Green**  | **Active**    | License is valid and available for use.                   |
| 🟡 **Yellow** | **Degraded**  | Violations detected; still works but user sees a warning. |
| 🟠 **Orange** | **Suspended** | Temporarily blocked; access resumes after reinstatement.  |
| 🔴 **Red**    | **Revoked**   | Permanently disabled.                                     |
| ⚫ **Grey**    | **Expired**   | Past the expiry date.                                     |
---

## Threat Levels

The **Threat lvl** column is updated automatically by the CG Lounge License Server's anti-piracy system.
Hover over any cell to see the full description.

| Level    | Meaning                                                       |
|----------|---------------------------------------------------------------|
| 🟢 **0** | Clean — no violations.                                        |
| 🟡 **1** | Warning — minor suspicious activity, license still active.    |
| 🟠 **2** | Degraded — significant violations, nag message shown to user. |
| 🟠 **3** | Suspended — serious abuse, access blocked after 72 hours.     |
| 🔴 **4** | Revoked — chargeback or confirmed fraud, immediate block.     |
---

## Edit License

Select a row and click **Edit Selected** (or right-click → **Edit License**) to open the edit dialog.

![Edit License](_readme_images/EditLicense.jpg)

The top section shows read-only license info for reference:

| Field       | Description                                      |
|-------------|--------------------------------------------------|
| **Key**     | Full license key (selectable)                    |
| **Email**   | Customer email address                           |
| **Product** | Product ID from your config                      |
| **Status**  | Current status at the time the dialog was opened |
| **Created** | Creation date                                    |

The editable fields section allows the following changes:

| Field                                                        | Description                                                                                                                                         |
|--------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| **Variant**                                                  | Change the license tier (loaded from the server for the product)                                                                                    |
| ![License Variants](_readme_images/EditLicenseVaraiants.jpg) | This is useful for licensing versions of a product. (You will need to hookup version validation in your custom licensing setup for your plugin.)    |
| **License Type**                                             | Switch between `per-machine`, `floating`, and `site`                                                                                                |
| **Max Machines**                                             | Maximum concurrent activations (`-1` = unlimited). Automatically set to `1` when switching to per-machine, `5` for floating, and unlimited for site |
| **Status**                                                   | Manually set to `active`, `degraded`, `suspended`, or `revoked`                                                                                     |
| **Expires**                                                  | Enable the checkbox to set an expiration date and time                                                                                              |

> Only fields that were actually changed are sent to the server. Clicking **OK** with no changes will do nothing.
---

## License Detail

Double-click a row (or click **View Details**) to open the detail dialog. It has three tabs:
- **Overview** — all stored fields for the license
![License Overview](_readme_images/LicenseOverview.jpg)
- **Activations** — list of active machines with fingerprint, hostname, country, and session info
![License Activations](_readme_images/LicenseActivations.jpg)
- **Violations** — anti-piracy violation records with type, severity, and detection time. Use the **Resolve Selected** button to clear false positives.
![License Activations](_readme_images/LicenseViolations.jpg)
---

## Keyboard Shortcuts

| Shortcut | Action             |
|----------|--------------------|
| `F5`     | Refresh licenses   |
| `Ctrl+N` | Create new license |
---

## Activation Counts
The CG Lounge License Server's list endpoint does not return live activation counts. The app fetches them automatically in the background in two ways:

![Status Bar](_readme_images/RefreshCount.jpg)
- **After every refresh** — activation counts are fetched one license at a time at 50ms intervals to avoid overloading the server.
- **Every 60 seconds** — a background timer re-fetches all counts automatically. A live countdown in the bottom-right status bar shows when the next refresh is due.
- **On detail view** — opening the **View Details** dialog for a license fetches its activations immediately and updates that row.

> The **Activations** tab inside the detail dialog has a live filter: type a hostname or country to narrow the list, or enable **Only active sessions** to show only machines with an active session.
---

## Troubleshooting
**Table shows 0/N activations** — The counts load in the background after the initial list.
Wait a few seconds for them to populate, or open the detail view for a specific license to update it immediately.

**Authentication errors** — Double-check your `apiKey` value. It must be a creator-scoped key (starts with `cgls_`).
You only have to create this once; every product uses the same `apiKey`.

**For more information** — please read the follwoing docs:
- [Licensing Handbook](https://cglounge.studio/handbook/licensing).
- [CG Lounge API Docs](https://cglicenseserver.vercel.app).

## Change Log
All notable changes to this project will be documented below:

### [1.0.0-beta] - 2026-04-10
#### Added:
- Initial public beta release for beta testing.

## Contruibutions
- [Aaron Strasbourg](https://www.aaronstrasbourgvfx.ca/) - Original code for the Creator Manager.
- [Arvid Schneider](https://www.arvidschneider.com/) - Huge special thanks for creating CG Lounge!