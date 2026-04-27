"""
Creator License Manager v1.0.0 — Desktop admin tool for CG Lounge License Server.
Requires: PySide6, Python 3.9+
Config:   creator_secret.config in the same directory as this script.

2026-04-27 - Aaron Strasbourg

"""

VERSION = "1.0.0"

import json
import random
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from string import Template
from typing import List, Optional

DEFAULT_SERVER_URL = "https://us-central1-cg-license-server.cloudfunctions.net"
CREATOR_SECRET = "creator_secret.config"

# =============================================================================
# Color Palette — single source of truth for every color used in the app.
# Tweak any entry here to re-skin the UI globally. Referenced by Python code
# (QColor(COLORS[...])) and by DARK_STYLE / CONTEXT_MENU_STYLE via $name
# placeholders rendered with string.Template.
# =============================================================================

COLORS: dict = {
    # ---- Surfaces / backgrounds ----
    "bg_window":          "#110e22",
    "bg_surface":         "#1c1830",
    "bg_table":           "#131020",
    "bg_table_alt":       "#0f0d1c",
    "bg_raised":          "#252040",
    "bg_header":          "#201c34",
    "bg_scrollbar":       "#0d0b18",
    "bg_tab_hover":       "#1a1628",
    "bg_btn_hover":       "#322d55",
    "bg_btn_pressed":     "#1a1535",
    "bg_btn_disabled":    "#1a1730",
    "bg_input_disabled":  "#141020",

    # ---- Borders ----
    "border":             "#2b2640",
    "border_subtle":      "#231f38",
    "border_inset":       "#3d2d60",
    "border_disabled":    "#1e1a30",

    # ---- Text ----
    "text_primary":       "#f0eeff",
    "text_header":        "#d8d4f5",
    "text_tab_hover":     "#c5c0e0",
    "text_group_title":   "#9d8ae0",
    "text_muted":         "#9490b8",
    "text_disabled":      "#5a5580",
    "text_menu_disabled": "#4a4570",
    "text_countdown":     "#6b7280",
    "text_white":         "#ffffff",

    # ---- Accent (primary brand purple) ----
    "accent":             "#7c3aed",
    "accent_hover":       "#6d28d9",
    "accent_dark":        "#3b2d72",
    "field_changed":      "#ff922b",
    "field_mismatch":     "#facc15",

    # ---- Status dots (LicenseTableModel / StatusDelegate) ----
    "status_active":      "#51cf66",
    "status_degraded":    "#ffa94d",
    "status_suspended":   "#ff922b",
    "status_revoked":     "#ff6b6b",
    "status_expired":     "#868e96",

    # ---- Threat level foregrounds ----
    "threat_0":           "#4ade80",
    "threat_1":           "#facc15",
    "threat_2":           "#fb923c",
    "threat_3":           "#f97316",
    "threat_4":           "#ef4444",

    # ---- Danger button (red) ----
    "danger_bg":          "#8b2020",
    "danger_border":      "#a52a2a",
    "danger_hover_bg":    "#a52a2a",
    "danger_hover_border": "#c53030",
    "danger_disabled_bg": "#4a2020",
    "danger_disabled_border": "#5a2a2a",
    "danger_disabled_text": "#7a5555",

    # ---- Warning button (orange) ----
    "warn_bg":            "#7a4510",
    "warn_border":        "#995a18",
    "warn_hover_bg":      "#995a18",
    "warn_hover_border":  "#b87020",
    "warn_disabled_bg":   "#3d2808",
    "warn_disabled_border": "#5a3a10",
    "warn_disabled_text": "#7a6040",

    # ---- Info button (blue) ----
    "info_bg":            "#1a4a8a",
    "info_border":        "#2460aa",
    "info_hover_bg":      "#2460aa",
    "info_hover_border":  "#3478cc",
    "info_disabled_bg":   "#0f2a50",
    "info_disabled_border": "#1a3a6a",
    "info_disabled_text": "#405570",

    # ---- Success button (green) ----
    "success_bg":         "#2d6b3f",
    "success_border":     "#3a8a50",
    "success_hover_bg":   "#3a8a50",
    "success_hover_border": "#4aaa60",
    "success_disabled_bg": "#1d3b2f",
    "success_disabled_border": "#2a4a3a",
    "success_disabled_text": "#506855",
}

from PySide6.QtCore import (
    QThread, Signal, Qt, QTimer, QSortFilterProxyModel,
    QAbstractTableModel, QModelIndex, QUrl, QSize, QSettings,
    QPoint, QRect,
)
from PySide6.QtGui import (
    QColor, QFont, QPalette, QPainter, QPen, QPixmap, QKeySequence, QShortcut,
    QIcon, QDesktopServices, QPolygon,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QPushButton, QComboBox, QCheckBox, QLabel,
    QLineEdit, QDialog, QFormLayout, QDialogButtonBox, QMessageBox,
    QHeaderView, QSpinBox, QDateTimeEdit, QGroupBox,
    QMenu, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QAbstractItemView,
    QProxyStyle,
    QTabWidget, QFrame, QProgressBar, QScrollArea, QStackedLayout,
)


# =============================================================================
# Widgets
# =============================================================================

class CheckBox(QCheckBox):
    """QCheckBox that draws a white checkmark over the stylesheet-styled indicator."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Scale indicator size with DPI so it looks correct on HiDPI/Retina
        dpr = self.logicalDpiX() / 96.0
        sz = int(14 * dpr)
        x = 0
        y = (self.height() - sz) // 2
        pen_width = max(1, int(2 * dpr))
        pen = QPen(QColor(COLORS["text_white"]), pen_width, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(int(x + sz * 0.15), int(y + sz * 0.50),
                         int(x + sz * 0.42), int(y + sz * 0.75))
        painter.drawLine(int(x + sz * 0.42), int(y + sz * 0.75),
                         int(x + sz * 0.85), int(y + sz * 0.20))
        painter.end()


class PixelatedLabel(QLabel):
    """A QLabel that renders its text as a pixelated (censored) mosaic."""

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            return
        # Render text normally to an offscreen pixmap
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setFont(self.font())
        p.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        p.drawText(pm.rect().adjusted(2, 0, -2, 0), self.alignment(), self.text())
        p.end()
        # Pixelate: scale down then back up
        factor = max(2, min(w, h) // 3)
        small = pm.scaled(max(1, w // factor), max(1, h // factor),
                          Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.FastTransformation)
        pixelated = small.scaled(w, h,
                                 Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.FastTransformation)
        out = QPainter(self)
        out.drawPixmap(0, 0, pixelated)
        out.end()


# =============================================================================
# UI Factory Helpers
# =============================================================================

def _confirm(parent, title: str, message: str) -> bool:
    return QMessageBox.question(
        parent, title, message, QMessageBox.Yes | QMessageBox.No,
    ) == QMessageBox.Yes


_big_arrow_style_instance = None


def _install_big_arrows(widget) -> None:
    """Apply BigArrowProxyStyle to a single widget (and its sub-controls).

    Applied per-widget instead of app-wide so drawPrimitive() doesn't bounce
    through Python for every table cell / header / scrollbar paint.
    """
    global _big_arrow_style_instance
    if _big_arrow_style_instance is None:
        _big_arrow_style_instance = BigArrowProxyStyle()
    widget.setStyle(_big_arrow_style_instance)


def _make_machines_spinbox(*, value: int = 2) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(-1, 9999)
    spin.setValue(value)
    spin.setSpecialValueText("Unlimited (-1)")
    _install_big_arrows(spin)
    return spin


def _make_dialog_buttons(layout, *, ok_cancel: bool = True, accept=None, reject=None):
    btns = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        if ok_cancel else QDialogButtonBox.Close
    )
    if accept:
        btns.accepted.connect(accept)
    if reject:
        btns.rejected.connect(reject)
    layout.addWidget(btns)


def _make_expiration_row(form, *, checked: bool = False, initial_dt=None):
    expires_check = CheckBox("Set expiration")
    expires_edit = QDateTimeEdit()
    _install_big_arrows(expires_edit)
    expires_edit.setCalendarPopup(True)
    expires_edit.setDisplayFormat("yyyy-MM-dd hh:mm AP")
    dt = initial_dt if initial_dt is not None else datetime.now().replace(year=datetime.now().year + 1)
    expires_edit.setDateTime(dt)
    expires_check.setChecked(checked)
    expires_edit.setEnabled(checked)
    expires_check.toggled.connect(expires_edit.setEnabled)
    exp_row = QHBoxLayout()
    exp_row.addWidget(expires_check)
    exp_row.addWidget(expires_edit, 1)
    form.addRow("Expires:", exp_row)
    return expires_check, expires_edit


def _make_action_button(text: str, callback, bar, *, css_class: str = "") -> QPushButton:
    btn = QPushButton(text)
    if css_class:
        btn.setProperty("cssClass", css_class)
    btn.clicked.connect(callback)
    bar.addWidget(btn)
    return btn


def _make_settings_checkbox(label: str, key: str, on_toggle, settings: QSettings) -> CheckBox:
    cb = CheckBox(label)
    cb.setChecked(settings.value(key, False, type=bool))
    cb.toggled.connect(on_toggle)
    cb.toggled.connect(
        lambda v: QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope,
            "CGLounge", "Creator License Manager",
        ).setValue(key, v)
    )
    return cb


# =============================================================================
# API Client
# =============================================================================

def _send(req, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
        except Exception:
            err = {"error": str(e)}
        err["_status"] = e.code
        return err
    except Exception as e:
        return {"error": str(e), "_status": 0}


class APIClient:
    """Thin HTTP wrapper for the License Server API endpoints."""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")

    def _post(self, endpoint: str, data: dict, timeout: int = 30) -> dict:
        url = f"{self.server_url}/{endpoint}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return _send(req, timeout)

    def _get(self, endpoint: str, params: dict = None, timeout: int = 15) -> dict:
        items = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        url = f"{self.server_url}/{endpoint}{'?' + items if items else ''}"
        api_key = (params or {}).get("apiKey", "")
        headers = {"x-api-key": api_key} if api_key else {}
        req = urllib.request.Request(url, headers=headers, method="GET")
        return _send(req, timeout)

    def list_licenses(self, auth: dict, product_id: str = "",
                      limit: int = 500) -> dict:
        payload: dict = {**auth, "limit": limit}
        if product_id:
            payload["productId"] = product_id
        return self._post("listLicenses", payload)

    def get_license(self, auth: dict, license_key: str) -> dict:
        return self._post("getLicense", {**auth, "licenseKey": license_key})

    def create_license(self, auth: dict, **kwargs) -> dict:
        return self._post("createLicense", {**auth, **kwargs})

    def update_license(self, auth: dict, license_key: str, **kwargs) -> dict:
        return self._post("updateLicense", {**auth, "licenseKey": license_key, **kwargs})

    def revoke_license(self, auth: dict, license_key: str,
                       reason: str = "fraud") -> dict:
        return self._post("revokeLicense", {
            **auth, "licenseKey": license_key, "reason": reason,
        })

    def reinstate_license(self, auth: dict, license_key: str) -> dict:
        return self._post("reinstateLicense", {
            **auth, "licenseKey": license_key,
        })

    def suspend_license(self, auth: dict, license_key: str) -> dict:
        return self._post("updateLicense", {
            **auth, "licenseKey": license_key, "status": "suspended",
        })

    def resolve_violations(self, auth: dict, license_key: str,
                           violation_ids: list) -> dict:
        return self._post("resolveLicense", {
            **auth, "licenseKey": license_key,
            "violationIds": violation_ids,
        })

    def list_variants(self, auth: dict, product_id: str) -> dict:
        return self._post("listVariants", {**auth, "productId": product_id})

    def list_products(self, auth: dict, include_all: bool = True) -> dict:
        payload = {**auth}
        if include_all:
            payload["includeAll"] = True
        return self._post("listProducts", payload)

    def reset_activations(self, auth: dict, license_key: str) -> dict:
        return self._post("resetActivations", {**auth, "licenseKey": license_key})

    def list_trial_codes(self, auth: dict, product_id: str = "") -> dict:
        payload = {**auth}
        if product_id:
            payload["productId"] = product_id
        return self._post("listTrialCodes", payload)

    def create_trial_code(self, auth: dict, **kwargs) -> dict:
        return self._post("createTrialCode", {**auth, **kwargs})

    def update_trial_code(self, auth: dict, code: str, **kwargs) -> dict:
        return self._post("updateTrialCode", {**auth, "code": code, **kwargs})

    def delete_trial_code(self, auth: dict, code: str) -> dict:
        return self._post("deleteTrialCode", {**auth, "code": code})


# =============================================================================
# Background Worker
# =============================================================================

class Worker(QThread):
    """ Worker thread for handling license server requests without UI lag."""
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class VariantComboBox(QComboBox):
    """QComboBox that fetches variants/tiers from the API and populates itself."""
    variant_selected = Signal(dict)  # emits full variant dict on selection change

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._current_variant = None
        self._product_id = None
        self._variants: list = []  # cached variant dicts from API
        self.currentIndexChanged.connect(self._emit_variant)

    def _emit_variant(self, index: int):
        if 0 <= index < len(self._variants):
            self.variant_selected.emit(self._variants[index])

    def current_variant_data(self) -> dict:
        idx = self.currentIndex()
        if 0 <= idx < len(self._variants):
            return self._variants[idx]
        return {}

    def load(self, api, auth: dict, product_id: str, current_variant: str = ""):
        self._current_variant = current_variant
        self._product_id = product_id
        self._variants = []
        self.clear()
        self.setEnabled(False)
        self.addItem("Loading…")
        worker = Worker(api.list_variants, auth, product_id)
        worker.finished.connect(self._on_loaded)
        worker.error.connect(lambda e: self._on_loaded({"error": e}))
        worker.finished.connect(lambda _: worker.deleteLater())
        worker.error.connect(lambda _: worker.deleteLater())
        self._worker = worker  # prevent GC
        worker.start()

    def _strip_prefix(self, variant_id: str) -> str:
        """Strip 'productId-' prefix that the API sometimes includes in variantId."""
        prefix = getattr(self, "_product_id", "") + "-"
        if prefix != "-" and variant_id.startswith(prefix):
            return variant_id[len(prefix):]
        return variant_id

    def _on_loaded(self, result: dict):
        self._variants = []
        self.clear()
        if "error" in result:
            self.addItem(f"Error: {result['error']}", "")
            self.setEnabled(True)
            print(f"[VariantComboBox] load failed: {result}")
            return
        variants = [v for v in result.get("variants", []) if v.get("active", True)]
        for v in variants:
            name = v.get("name", "")
            variant_id = self._strip_prefix(v.get("variantId", name))
            if name:
                self._variants.append(v)
                self.addItem(name, variant_id)
        if self.count() == 0:
            self.addItem("(no variants found)", "")
        # current_variant from the license may also carry the productId prefix
        current = self._strip_prefix(self._current_variant) if self._current_variant else ""
        if current:
            idx = self.findData(current)
            if idx < 0:
                idx = self.findText(current, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                self.setCurrentIndex(idx)
        self.setEnabled(True)
        # Emit for the initially selected variant
        self._emit_variant(self.currentIndex())


# =============================================================================
# Table Model
# =============================================================================

LICENSE_COLUMNS = [
    ("status",         "Status"),
    ("_productStatus", "Product Status"),
    ("key",            "License Key"),
    ("email",          "Email"),
    ("variant",        "Tier"),
    ("licenseType",    "Type"),
    ("_saleDate",      "Sale Date"),
    ("_expiresIn",     "Expires In"),
    ("_activations",   "Activations"),
    ("_refunded",      "Refunded"),
    ("_disabled",      "Disabled"),
    ("_expired",       "Expired"),
    ("_violations",    "Violations"),
    ("threatLevel",    "Threat lvl"),
    ("_productName",   "Product"),
]

_PRODUCT_STATUS_COLORS = {
    "live":     COLORS["status_active"],     # green
    "unlisted": COLORS["status_degraded"],   # orange
    "archived": COLORS["threat_1"],          # yellow
}

# Precomputed QColor/QFont cache so model.data() doesn't allocate per paint.
_THREAT_QCOLORS: dict = {}
_PRODUCT_STATUS_QCOLORS: dict = {}
_STATUS_REVOKED_QCOLOR = None
_STATUS_DEGRADED_QCOLOR = None
_TEXT_WHITE_QCOLOR = None
_BOLD_FONT = None


def _init_model_color_cache():
    global _STATUS_REVOKED_QCOLOR, _STATUS_DEGRADED_QCOLOR, _TEXT_WHITE_QCOLOR, _BOLD_FONT
    if _BOLD_FONT is not None:
        return
    for i in range(5):
        _THREAT_QCOLORS[i] = QColor(COLORS[f"threat_{i}"])
    for k, hex_col in _PRODUCT_STATUS_COLORS.items():
        _PRODUCT_STATUS_QCOLORS[k] = QColor(hex_col)
    _STATUS_REVOKED_QCOLOR = QColor(COLORS["status_revoked"])
    _STATUS_DEGRADED_QCOLOR = QColor(COLORS["status_degraded"])
    _TEXT_WHITE_QCOLOR = QColor(COLORS["text_white"])
    _BOLD_FONT = QFont()
    _BOLD_FONT.setBold(True)


def _format_date(iso_str: Optional[str]) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str or ""


def _expires_in(lic: dict) -> str:
    exp = lic.get("expiresAt")
    if not exp:
        return "Perpetual"
    try:
        dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = dt - now
        days = delta.days
        if days < 0:
            return f"Expired ({abs(days)}d ago)"
        return f"{days} day(s)"
    except Exception:
        return exp


def _enrich(lic: dict, product_names: dict = None) -> dict:
    """Add computed display fields."""
    if product_names:
        pid = lic.get("productId", "")
        lic["_productName"] = product_names.get(pid, pid)
    lic["_saleDate"] = _format_date(
        lic.get("purchasedAt") or lic.get("createdAt")
    )
    lic["_expiresIn"] = _expires_in(lic)

    max_m = lic.get("maxMachines", "?")
    if max_m == -1:
        max_m = "Unlimited"
    activations = lic.get("activations")
    machines_used = lic.get("machinesUsed")
    if activations is not None:
        lic["_activations"] = f"{len(activations)}/{max_m}"
    elif machines_used is not None:
        lic["_activations"] = f"{machines_used}/{max_m}"
    else:
        lic["_activations"] = f"—/{max_m}"

    status = (lic.get("status") or "").lower()
    reason = (lic.get("disputeReason") or "").lower()

    lic["_refunded"] = "Yes" if reason in ("refund", "chargeback") else "No"
    lic["_disabled"] = "Yes" if status in ("revoked", "suspended") else "No"

    exp_str = lic.get("expiresAt")
    if exp_str:
        try:
            dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
            lic["_expired"] = "Yes" if dt < datetime.now(timezone.utc) else "No"
        except Exception:
            lic["_expired"] = "No"
    else:
        lic["_expired"] = "No"

    if "unresolvedViolationsCount" in lic:
        lic["_violations"] = str(lic["unresolvedViolationsCount"])
    elif "_violations" not in lic:
        violations = lic.get("violations")
        if violations is None:
            lic["_violations"] = "—"
        else:
            unresolved = sum(1 for v in violations if not v.get("resolved"))
            lic["_violations"] = str(unresolved)

    return lic


def _effective_status(lic: dict) -> str:
    """Return the visual status used by the status dot — expired takes precedence over raw status."""
    if lic.get("_expired") == "Yes":
        return "expired"
    return (lic.get("status") or "").lower()


_LIC_CENTER_COLS = frozenset({
    "_activations", "threatLevel", "_refunded",
    "_disabled", "_expired", "_violations", "status", "_productStatus",
})
_ALIGN_CENTER = int(Qt.AlignCenter)
_ALIGN_LEFT_V = int(Qt.AlignLeft | Qt.AlignVCenter)
_LIC_PAINT_ROLES = frozenset({
    int(Qt.DisplayRole), int(Qt.TextAlignmentRole), int(Qt.ForegroundRole),
    int(Qt.FontRole), int(Qt.UserRole), int(Qt.ToolTipRole),
})

_STATUS_TOOLTIPS = {
    "active": "Active — license is valid and in good standing.",
    "degraded": "Degraded — significant violations; still functional but token refreshes every 24h.",
    "suspended": "Suspended — access blocked pending resolution.",
    "revoked": "Revoked — license disabled (fraud, chargeback, or manual revoke).",
    "expired": "Expired — past the license's expiration date.",
}

_THREAT_TOOLTIPS = {
    0: "Level 0 — Clean: No violations. Normal operation.",
    1: "Level 1 — Warning: Minor suspicious activity detected. License still active, warning logged internally.",
    2: "Level 2 — Degraded: Significant violations detected. Nag message shown to user; still functional but token refreshes every 24 hours.",
    3: "Level 3 — Suspended: Serious abuse detected. User sees warning; access blocked after 72 hours unless resolved.",
    4: "Level 4 — Revoked: Chargeback or confirmed fraud. License immediately blocked.",
}


class LicenseTableModel(QAbstractTableModel):
    def __init__(self, products: dict = None, parent=None):
        super().__init__(parent)
        _init_model_color_cache()
        self._data: List[dict] = []
        self._columns = LICENSE_COLUMNS
        self._col_keys: tuple = tuple(k for k, _ in LICENSE_COLUMNS)
        self._privacy_mode: bool = False
        # Build productId → product name lookup from config
        self._product_names: dict = {}
        self._product_statuses: dict = {}
        if products:
            for name, info in products.items():
                pid = info.get("productId")
                if pid:
                    self._product_names[pid] = name
                    self._product_statuses[pid] = (info.get("status") or "").lower()

    def set_product_statuses(self, statuses: dict):
        self._product_statuses = {
            pid: (s or "").lower() for pid, s in (statuses or {}).items()
        }
        if self._data:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._data) - 1, len(self._columns) - 1)
            self.dataChanged.emit(top_left, bottom_right,
                                  [Qt.DisplayRole, Qt.ForegroundRole, Qt.FontRole])

    def set_privacy_mode(self, enabled: bool):
        self._privacy_mode = enabled

    def set_product_names(self, product_names: dict):
        """Replace the productId → name lookup and re-enrich existing rows."""
        self._product_names = dict(product_names or {})
        if self._data:
            self.beginResetModel()
            for lic in self._data:
                _enrich(lic, self._product_names)
            self.endResetModel()

    def all_licenses(self) -> List[dict]:
        return list(self._data)

    def set_data(self, licenses: List[dict]):
        self.beginResetModel()
        self._data = [_enrich(lic, self._product_names) for lic in licenses]
        self.endResetModel()

    def update_license_row(self, license_key: str, new_data: dict):
        """Merge new_data into the row for license_key and emit dataChanged for the whole row."""
        for row, lic in enumerate(self._data):
            if lic.get("key") == license_key:
                lic.update(new_data)
                _enrich(lic, self._product_names)
                top_left = self.index(row, 0)
                bottom_right = self.index(row, len(self._columns) - 1)
                self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.ToolTipRole])
                break

    def update_activation_count(self, license_key: str, count: int):
        for row, lic in enumerate(self._data):
            if lic.get("key") == license_key:
                max_m = lic.get("maxMachines", "?")
                if max_m == -1:
                    max_m = "Unlimited"
                lic["_activations"] = f"{count}/{max_m}"
                col = next(i for i, (k, _) in enumerate(self._columns) if k == "_activations")
                idx = self.index(row, col)
                self.dataChanged.emit(idx, idx, [Qt.DisplayRole])
                break

    def update_violation_count(self, license_key: str, count: int):
        for row, lic in enumerate(self._data):
            if lic.get("key") == license_key:
                lic["_violations"] = str(count)
                col = next(i for i, (k, _) in enumerate(self._columns) if k == "_violations")
                idx = self.index(row, col)
                self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.ForegroundRole])
                break

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._columns[section][1]
        return None

    def data(self, index, role=Qt.DisplayRole):
        # Fast path: return None immediately for roles Qt queries on every
        # paint that we don't care about (BackgroundRole, DecorationRole,
        # CheckStateRole, SizeHintRole, etc.) — avoids all list/dict
        # lookups for 3-4 of the ~7 calls Qt makes per cell per repaint.
        if role not in _LIC_PAINT_ROLES:
            return None

        col_key = self._col_keys[index.column()]

        if role == Qt.TextAlignmentRole:
            return _ALIGN_CENTER if col_key in _LIC_CENTER_COLS else _ALIGN_LEFT_V

        lic = self._data[index.row()]

        if role == Qt.DisplayRole:
            val = lic.get(col_key)
            if col_key == "status":
                return ""
            if col_key == "key":
                k = str(val) if val is not None else ""
                return f"{k[:6]}...{k[-4:]}" if len(k) > 12 else k
            if col_key == "threatLevel":
                return str(val if val is not None else 0)
            if col_key == "_productStatus":
                return self._product_statuses.get(lic.get("productId", ""), "")
            return str(val) if val is not None else ""

        if role == Qt.UserRole:
            return lic

        if role == Qt.ForegroundRole:
            if col_key == "threatLevel":
                tl = lic.get("threatLevel")
                return _THREAT_QCOLORS.get(int(tl) if tl is not None else 0,
                                           _TEXT_WHITE_QCOLOR)
            if col_key == "_productStatus":
                ps = self._product_statuses.get(lic.get("productId", ""), "")
                return _PRODUCT_STATUS_QCOLORS.get(ps)
            if col_key == "_disabled" and lic.get("_disabled") == "Yes":
                return _STATUS_REVOKED_QCOLOR
            if col_key == "_refunded" and lic.get("_refunded") == "Yes":
                return _STATUS_DEGRADED_QCOLOR
            if col_key == "_expired" and lic.get("_expired") == "Yes":
                return _STATUS_REVOKED_QCOLOR
            if col_key == "_violations":
                v = lic.get("_violations", "—")
                if v not in ("0", "—", ""):
                    return _STATUS_REVOKED_QCOLOR
            return None

        if role == Qt.FontRole:
            if col_key == "threatLevel" or col_key == "_productStatus":
                return _BOLD_FONT
            return None

        # Qt.ToolTipRole — only fires on hover, not per paint.
        if col_key == "status":
            if lic.get("_expired") == "Yes":
                effective = "expired"
            else:
                effective = (lic.get("status") or "unknown").lower()
            return _STATUS_TOOLTIPS.get(effective, f"Status: {effective}")
        if col_key == "key":
            return None if self._privacy_mode else str(lic.get("key", ""))
        if col_key == "threatLevel":
            tl_raw = lic.get("threatLevel")
            tl = int(tl_raw) if tl_raw else 0
            return _THREAT_TOOLTIPS.get(tl, f"Level {tl} — Unknown threat level.")
        return None

    def get_row(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None


# =============================================================================
# Table View (clears stale proxy-model selection on plain click)
# =============================================================================

class LicenseTableView(QTableView):
    def mousePressEvent(self, event):
        if (event.button() == Qt.LeftButton
                and not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier))):
            sm = self.selectionModel()
            if sm:
                sm.clearSelection()
                self.viewport().repaint()   # synchronous clear before super
        super().mousePressEvent(event)
        if (event.button() == Qt.LeftButton
                and not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier))):
            # Defer a final repaint to the next event-loop cycle, after Qt finishes
            # all internal painting triggered by super (clears any ghost the anchor repaint creates)
            # @TODO This seems to still be an issue.
            QTimer.singleShot(0, self.viewport().update)


# =============================================================================
# Status Delegate
# =============================================================================

class StatusDelegate(QStyledItemDelegate):
    STATUS_COLORS = {
        "active":    COLORS["status_active"],
        "degraded":  COLORS["status_degraded"],
        "suspended": COLORS["status_suspended"],
        "revoked":   COLORS["status_revoked"],
        "expired":   COLORS["status_expired"],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status_qcolors = {k: QColor(v) for k, v in self.STATUS_COLORS.items()}
        self._fallback_qcolor = QColor(COLORS["status_expired"])

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        lic = index.data(Qt.UserRole)
        if not lic:
            return
        if lic.get("_expired") == "Yes":
            status = "expired"
        else:
            status = (lic.get("status") or "unknown").lower()
        color = self._status_qcolors.get(status, self._fallback_qcolor)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        r = option.rect
        dot_size = 10
        x = r.x() + (r.width() - dot_size) // 2
        y = r.y() + (r.height() - dot_size) // 2
        painter.drawEllipse(x, y, dot_size, dot_size)
        painter.restore()


# Columns that contain personally identifiable / sensitive data
_PRIVACY_SENSITIVE_COLS: frozenset = frozenset(
    i for i, (k, _) in enumerate(LICENSE_COLUMNS) if k in ("key", "email")
)
# Dialog fields considered sensitive
_PRIVACY_SENSITIVE_FIELDS: frozenset = frozenset({
    "key", "email", "productId", "purchaseId", "bundleId",
    "disputeReason", "disputedAt",
})


class PrivacyDelegate(QStyledItemDelegate):
    """Pixelates sensitive table columns when privacy mode is active."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._privacy = False

    def set_privacy(self, enabled: bool):
        self._privacy = enabled

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint(self, painter, option, index):
        # The delegate is installed per-column, so any column it's attached
        # to is by definition sensitive — just gate on the privacy flag.
        if not self._privacy:
            super().paint(painter, option, index)
            return
        w, h = option.rect.width(), option.rect.height()
        if w < 1 or h < 1:
            return
        # Render cell normally to an off-screen pixmap
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)
        tmp = QPainter(pm)
        pix_opt = QStyleOptionViewItem(option)
        pix_opt.rect = pm.rect()
        super().paint(tmp, pix_opt, index)
        tmp.end()
        # Pixelate: scale down then back up (mosaic effect)
        factor = max(2, min(w, h) // 3)
        small = pm.scaled(max(1, w // factor), max(1, h // factor),
                          Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.FastTransformation)
        pixelated = small.scaled(w, h,
                                 Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.FastTransformation)
        painter.drawPixmap(option.rect.topLeft(), pixelated)


# =============================================================================
# Proxy Filter Model
# =============================================================================

class LicenseFilterProxy(QSortFilterProxyModel):
    _STATUS_ORDER = {"active": 0, "degraded": 1, "suspended": 2, "revoked": 3, "expired": 4}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide_trials = False
        self.hide_disabled = False
        self.hide_expired = False
        self.product_filter = ""
        self.search_text = ""
        self.allowed_product_ids = None   # None = no product-status filter

    def set_filters(self, hide_trials=None, hide_disabled=None,
                    hide_expired=None, product_filter=None, search_text=None,
                    allowed_product_ids=...):
        if hide_trials is not None:
            self.hide_trials = hide_trials
        if hide_disabled is not None:
            self.hide_disabled = hide_disabled
        if hide_expired is not None:
            self.hide_expired = hide_expired
        if product_filter is not None:
            self.product_filter = product_filter
        if search_text is not None:
            self.search_text = search_text.lower()
        if allowed_product_ids is not ...:
            self.allowed_product_ids = allowed_product_ids
        self.invalidateFilter()

    def lessThan(self, left, right):
        model = self.sourceModel()
        col_key = model._columns[left.column()][0]
        if col_key == "status":
            def rank(lic):
                if not lic:
                    return 99
                if lic.get("_expired") == "Yes":
                    return self._STATUS_ORDER.get("expired", 99)
                return self._STATUS_ORDER.get((lic.get("status") or "").lower(), 99)
            return rank(left.data(Qt.UserRole)) < rank(right.data(Qt.UserRole))
        return super().lessThan(left, right)

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        lic = model.get_row(source_row)
        if not lic:
            return False

        variant = (lic.get("variant") or "").lower()
        status = (lic.get("status") or "").lower()
        product = lic.get("productId") or ""

        if self.hide_trials and variant == "trial":
            return False
        if self.hide_disabled and status in ("revoked", "suspended"):
            return False
        if self.hide_expired and lic.get("_expired") == "Yes":
            return False
        if self.product_filter and product != self.product_filter:
            return False
        if self.allowed_product_ids is not None and product not in self.allowed_product_ids:
            return False
        if self.search_text:
            searchable = " ".join([
                str(lic.get("key", "")),
                str(lic.get("email", "")),
                str(lic.get("variant", "")),
                str(lic.get("status", "")),
                str(lic.get("productId", "")),
            ]).lower()
            if self.search_text not in searchable:
                return False
        return True


# =============================================================================
# Trial Codes — Model, Delegate, Proxy
# =============================================================================

TRIAL_CODE_COLUMNS = [
    ("_statusDot",    "Status"),
    ("_productStatus", "Product Status"),
    ("_productName",  "Product"),
    ("code",         "Code"),
    ("usedCount",    "Used"),
    ("maxUses",      "Max Uses"),
    ("_trialDays",   "Trial Duration"),
    ("_expiresAt",   "Expires"),
]


def _enrich_code(code: dict, product_names: dict = None) -> dict:
    trial = code.get("trialDays") or 0
    code["_trialDays"] = f"{trial}d" if trial and trial > 0 else "N/A"

    code["_expiresAt"] = _expires_in(code)

    exp_str = code.get("expiresAt")
    if exp_str:
        try:
            dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
            code["_expired"] = dt < datetime.now(timezone.utc)
        except Exception:
            code["_expired"] = False
    else:
        code["_expired"] = False

    max_uses_raw = code.get("maxUses")
    used_count = code.get("usedCount") or 0
    code["_maxed"] = (
        max_uses_raw is not None
        and max_uses_raw != -1
        and isinstance(max_uses_raw, (int, float))
        and int(max_uses_raw) > 0
        and int(used_count) >= int(max_uses_raw)
    )
    if max_uses_raw is None or max_uses_raw == -1:
        code["maxUses"] = "Unlimited"

    pid = code.get("productId") or ""
    if not pid:
        code["_productName"] = "All products"
    elif product_names:
        code["_productName"] = product_names.get(pid, pid)
    else:
        code["_productName"] = pid

    if "active" not in code:
        code["active"] = True
    return code


class TrialCodeTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[dict] = []
        self._columns = TRIAL_CODE_COLUMNS
        self._product_names: dict = {}
        self._product_statuses: dict = {}

    def set_product_names(self, product_names: dict):
        self._product_names = dict(product_names or {})
        if self._data:
            self.beginResetModel()
            for c in self._data:
                _enrich_code(c, self._product_names)
            self.endResetModel()

    def set_product_statuses(self, statuses: dict):
        self._product_statuses = {
            pid: (s or "").lower() for pid, s in (statuses or {}).items()
        }
        if self._data:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._data) - 1, len(self._columns) - 1)
            self.dataChanged.emit(top_left, bottom_right,
                                  [Qt.DisplayRole, Qt.ForegroundRole, Qt.FontRole])

    def set_data(self, codes: List[dict]):
        self.beginResetModel()
        self._data = [_enrich_code(c, self._product_names) for c in codes]
        self.endResetModel()

    def all_codes(self) -> List[dict]:
        return list(self._data)

    def get_row(self, row: int) -> Optional[dict]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._columns[section][1]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        code = self._data[index.row()]
        col_key = self._columns[index.column()][0]
        val = code.get(col_key, "")

        if role == Qt.DisplayRole:
            if col_key == "_statusDot":
                return ""
            if col_key == "_productStatus":
                return self._product_statuses.get(code.get("productId", ""), "")
            return str(val) if val is not None else ""

        if role == Qt.ToolTipRole:
            if col_key == "_statusDot":
                if code.get("_expired"):
                    return "Expired — past the code's expiration date."
                if not code.get("active", True):
                    return "Disabled — code has been manually deactivated."
                if code.get("_maxed"):
                    return "Maxed out — all redemptions have been used."
                return "Active — code is valid and available for redemption."
            return None

        if role == Qt.UserRole:
            return code

        if role == Qt.ForegroundRole:
            if col_key == "_productStatus":
                ps = self._product_statuses.get(code.get("productId", ""), "")
                return _PRODUCT_STATUS_QCOLORS.get(ps)
            return None

        if role == Qt.FontRole:
            if col_key == "_productStatus":
                return _BOLD_FONT
            return None

        if role == Qt.TextAlignmentRole:
            if col_key in ("_statusDot", "_productStatus", "usedCount",
                           "maxUses", "_trialDays"):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None


class CodeStatusDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_color = QColor(COLORS["status_active"])
        self._inactive_color = QColor(COLORS["status_revoked"])
        self._expired_color = QColor(COLORS["status_expired"])
        self._maxed_color = QColor(COLORS["threat_1"])   # yellow

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        code = index.data(Qt.UserRole)
        if code is None:
            return
        if code.get("_expired"):
            color = self._expired_color
        elif not code.get("active", True):
            color = self._inactive_color
        elif code.get("_maxed"):
            color = self._maxed_color
        else:
            color = self._active_color
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        r = option.rect
        dot_size = 10
        x = r.x() + (r.width() - dot_size) // 2
        y = r.y() + (r.height() - dot_size) // 2
        painter.drawEllipse(x, y, dot_size, dot_size)
        painter.restore()


class TrialCodeFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide_disabled = False
        self.hide_expired = False
        self.product_filter = ""
        self.search_text = ""
        self.allowed_product_ids = None

    def set_filters(self, hide_disabled=None, hide_expired=None,
                    product_filter=None, search_text=None,
                    allowed_product_ids=...):
        if hide_disabled is not None:
            self.hide_disabled = hide_disabled
        if hide_expired is not None:
            self.hide_expired = hide_expired
        if product_filter is not None:
            self.product_filter = product_filter
        if search_text is not None:
            self.search_text = search_text.lower()
        if allowed_product_ids is not ...:
            self.allowed_product_ids = allowed_product_ids
        self.invalidateFilter()

    def lessThan(self, left, right):
        model = self.sourceModel()
        col_key = model._columns[left.column()][0]
        if col_key == "_statusDot":
            def rank(c):
                if not c:
                    return 99
                if c.get("_expired"):
                    return 3
                if not c.get("active", True):
                    return 2
                if c.get("_maxed"):
                    return 1
                return 0
            return rank(left.data(Qt.UserRole)) < rank(right.data(Qt.UserRole))
        return super().lessThan(left, right)

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        code = model.get_row(source_row)
        if not code:
            return False
        if self.hide_disabled and not code.get("active", True):
            return False
        if self.hide_expired and code.get("_expired"):
            return False
        if self.product_filter:
            if (code.get("productId") or "") != self.product_filter:
                return False
        if self.allowed_product_ids is not None:
            pid = code.get("productId") or ""
            # Codes with no product (all-products codes) are always kept
            if pid and pid not in self.allowed_product_ids:
                return False
        if self.search_text:
            searchable = " ".join([
                str(code.get("code", "")),
                str(code.get("_productName", "")),
                str(code.get("productId", "")),
            ]).lower()
            if self.search_text not in searchable:
                return False
        return True


# =============================================================================
# Dialogs
# =============================================================================

class CreateLicenseDialog(QDialog):
    def __init__(self, products: dict, api, auth: dict, parent=None,
                 preselect_product_id: str = "", privacy_mode: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Create License")
        self.setMinimumWidth(440)
        self.products = products
        self._api = api
        self._auth = auth

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.product_combo = QComboBox()
        for name in products:
            pid = products[name].get("productId", "")
            label = name if privacy_mode else f"{name}  ({pid})"
            self.product_combo.addItem(label, pid)
        if preselect_product_id:
            idx = self.product_combo.findData(preselect_product_id)
            if idx >= 0:
                self.product_combo.setCurrentIndex(idx)
        self.product_combo.currentIndexChanged.connect(self._reload_variants)
        form.addRow("Product:", self.product_combo)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("customer@example.com")
        form.addRow("Email:", self.email_edit)

        self.variant_combo = VariantComboBox()
        self.variant_combo.variant_selected.connect(self._on_variant_selected)
        form.addRow("Variant:", self.variant_combo)

        self.type_label = QLineEdit()
        self.type_label.setReadOnly(True)
        self.type_label.setToolTip(
            "License type is determined by the selected variant and cannot be edited here.\n"
            "It is pulled directly from the product's variant configuration in CG Lounge."
        )
        form.addRow("License Type:", self.type_label)

        self.machines_spin = _make_machines_spinbox(value=2)
        self.machines_label = QLabel("Max Machines:")
        form.addRow(self.machines_label, self.machines_spin)

        self.expires_check, self.expires_edit = _make_expiration_row(form)

        layout.addLayout(form)

        _make_dialog_buttons(layout, accept=self.accept, reject=self.reject)

        self._reload_variants()

    def _reload_variants(self):
        pid = self.product_combo.currentData()
        if pid:
            self.variant_combo.load(self._api, self._auth, pid)

    def _on_variant_selected(self, variant: dict):
        license_type = variant.get("licenseType", "per-machine")
        self.type_label.setText(license_type)
        is_site = license_type == "site"
        self.machines_spin.setEnabled(not is_site)
        # Reset max machines to the variant's default for each selection.
        default_max = variant.get("maxMachines")
        if default_max is None:
            default_max = -1 if is_site else (1 if license_type == "per-machine" else 5)
        self.machines_spin.setValue(default_max)
        self.machines_label.setText("Max Machines:")

    def get_data(self) -> dict:
        data = {
            "email": self.email_edit.text().strip(),
            "productId": self.product_combo.currentData(),
            "variant": self.variant_combo.currentData(),
            "licenseType": self.type_label.text() or "per-machine",
            "maxMachines": self.machines_spin.value(),
        }
        if self.expires_check.isChecked():
            data["expiresAt"] = (
                self.expires_edit.dateTime().toUTC().toString(Qt.ISODate)
            )
        return data

    def get_product_name(self) -> str:
        idx = self.product_combo.currentIndex()
        return list(self.products.keys())[idx]


class EditLicenseDialog(QDialog):
    def __init__(self, lic: dict, api, auth: dict, parent=None, privacy_mode: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Edit License")
        self.setMinimumWidth(500)
        self.lic = lic

        layout = QVBoxLayout(self)

        info_group = QGroupBox("License Info")
        info_layout = QFormLayout()
        if privacy_mode:
            key_label = PixelatedLabel(lic.get("key", ""))
            email_label = PixelatedLabel(lic.get("email", ""))
        else:
            key_label = QLabel(lic.get("key", ""))
            key_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            email_label = QLabel(lic.get("email", ""))
        info_layout.addRow("Key:", key_label)
        info_layout.addRow("Email:", email_label)
        info_layout.addRow("Product:", QLabel(lic.get("_productName", "") or lic.get("productId", "")))
        info_layout.addRow("Status:", QLabel(lic.get("status", "")))
        info_layout.addRow("Created:", QLabel(_format_date(lic.get("createdAt"))))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        edit_group = QGroupBox("Editable Fields")
        form = QFormLayout()

        self.variant_combo = VariantComboBox()
        self.variant_combo.variant_selected.connect(self._on_variant_selected)
        form.addRow("Variant:", self.variant_combo)

        self.type_label = QLineEdit()
        self.type_label.setReadOnly(True)
        self.type_label.setText(lic.get("licenseType", "per-machine"))
        self.type_label.setToolTip(
            "License type is determined by the selected variant and cannot be edited here.\n"
            "It is pulled directly from the product's variant configuration in CG Lounge."
        )
        form.addRow("License Type:", self.type_label)

        is_site = (lic.get("licenseType") or "").lower() == "site"
        self.machines_spin = _make_machines_spinbox(value=lic.get("maxMachines", 2))
        self.machines_spin.setEnabled(not is_site)
        form.addRow("Max Machines:", self.machines_spin)

        self._machines_hint = QLabel()
        self._machines_hint.setStyleSheet(f"color: {COLORS['text_disabled']}; font-size: 11px;")
        form.addRow("", self._machines_hint)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "degraded", "suspended", "revoked"])
        idx = self.status_combo.findText(lic.get("status", "active"))
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        form.addRow("Status:", self.status_combo)

        _exp_checked, _exp_dt = False, None
        exp = lic.get("expiresAt")
        if exp:
            _exp_checked = True
            try:
                _exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            except Exception:
                pass
        self.expires_check, self.expires_edit = _make_expiration_row(
            form, checked=_exp_checked, initial_dt=_exp_dt
        )

        edit_group.setLayout(form)
        layout.addWidget(edit_group)

        _make_dialog_buttons(layout, accept=self._on_accept, reject=self.reject)

        self._variant_default_max: int | None = None
        self._initial_load = True

        self._orig_variant = lic.get("variant", "")
        self._orig_license_type = lic.get("licenseType", "per-machine")
        self._orig_max_machines = lic.get("maxMachines", 2)
        self._orig_status = lic.get("status", "active")
        self._orig_exp_checked = _exp_checked
        self._orig_exp_dt = self.expires_edit.dateTime() if _exp_checked else None

        self._changed_style = f"border: 2px solid {COLORS['field_changed']}; border-radius: 4px; padding: 2px;"
        self._mismatch_style = f"border: 2px solid {COLORS['field_mismatch']}; border-radius: 4px; padding: 2px;"
        self._tracked_widgets: list[QWidget] = [
            self.variant_combo, self.type_label, self.machines_spin,
            self.status_combo, self.expires_check, self.expires_edit,
        ]
        for w in self._tracked_widgets:
            w.setProperty("_orig_style", w.styleSheet())

        self.machines_spin.valueChanged.connect(self._highlight_changes)
        self.status_combo.currentIndexChanged.connect(self._highlight_changes)
        self.expires_check.stateChanged.connect(self._highlight_changes)
        self.expires_edit.dateTimeChanged.connect(self._highlight_changes)

        pid = lic.get("productId", "")
        self.variant_combo.load(api, auth, pid, lic.get("variant", ""))

    def _mark(self, widget: QWidget, changed: bool, mismatch: bool = False):
        orig = widget.property("_orig_style") or ""
        if changed:
            widget.setStyleSheet(self._changed_style)
        elif mismatch:
            widget.setStyleSheet(self._mismatch_style)
        else:
            widget.setStyleSheet(orig)

    def _update_hints(self):
        if self._variant_default_max is None:
            self._machines_hint.setText("")
            return
        variant_name = self.variant_combo.currentText() or "variant"
        default_label = "Unlimited" if self._variant_default_max == -1 else str(self._variant_default_max)
        if self.machines_spin.value() != self._variant_default_max:
            self._machines_hint.setText(f"Default for \"{variant_name}\" is {default_label}")
        else:
            self._machines_hint.setText("")

    def _highlight_changes(self):
        cur_variant = self.variant_combo.currentData() or ""
        orig_variant = self.variant_combo._strip_prefix(self._orig_variant)
        variant_changed = cur_variant != orig_variant

        type_changed = self.type_label.text() != self._orig_license_type
        machines_changed = self.machines_spin.value() != self._orig_max_machines
        status_changed = self.status_combo.currentText() != self._orig_status

        if self.expires_check.isChecked() != self._orig_exp_checked:
            exp_changed = True
        elif self.expires_check.isChecked() and self._orig_exp_dt is not None:
            exp_changed = self.expires_edit.dateTime() != self._orig_exp_dt
        else:
            exp_changed = False

        machines_mismatch = (
            not machines_changed
            and self._variant_default_max is not None
            and self.machines_spin.value() != self._variant_default_max
        )

        self._mark(self.variant_combo, variant_changed)
        self._mark(self.type_label, type_changed)
        self._mark(self.machines_spin, machines_changed, mismatch=machines_mismatch)
        self._mark(self.status_combo, status_changed)
        self._mark(self.expires_check, exp_changed)
        self._mark(self.expires_edit, exp_changed)
        self._update_hints()

    def _on_variant_selected(self, variant: dict):
        if not self.variant_combo.isEnabled() and self._initial_load:
            return

        license_type = variant.get("licenseType", "per-machine")
        self.type_label.setText(license_type)
        is_site = license_type == "site"
        self.machines_spin.setEnabled(not is_site)
        default_max = variant.get("maxMachines")
        if default_max is None:
            default_max = -1 if is_site else (1 if license_type == "per-machine" else 5)
        self._variant_default_max = default_max

        if self._initial_load:
            self._initial_load = False
        else:
            cur_variant = self.variant_combo.currentData() or ""
            orig_variant = self.variant_combo._strip_prefix(self._orig_variant)
            if cur_variant == orig_variant:
                self.machines_spin.setValue(self._orig_max_machines)
            else:
                self.machines_spin.setValue(default_max)
        self._highlight_changes()

    def _on_accept(self):
        if (self._variant_default_max is not None
                and self.machines_spin.value() != self._variant_default_max):
            variant_name = self.variant_combo.currentText() or "selected variant"
            default_label = "Unlimited" if self._variant_default_max == -1 else str(self._variant_default_max)
            current_label = "Unlimited" if self.machines_spin.value() == -1 else str(self.machines_spin.value())
            reply = QMessageBox.question(
                self, "Max Machines Override",
                f"The default Max Machines for <b>\"{variant_name}\"</b> is <b>{default_label}</b>, "
                f"but you have set it to <b>{current_label}</b>.<br><br>"
                f"Are you sure you want to override the variant default for this license?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        self.accept()

    def get_changes(self) -> dict:
        changes = {}
        if self.type_label.text() != self.lic.get("licenseType", "per-machine"):
            changes["licenseType"] = self.type_label.text()
        if self.variant_combo.currentData() != self.lic.get("variant", ""):
            changes["variant"] = self.variant_combo.currentData()
        if self.machines_spin.value() != self.lic.get("maxMachines", 2):
            changes["maxMachines"] = self.machines_spin.value()
        if self.status_combo.currentText() != self.lic.get("status", "active"):
            changes["status"] = self.status_combo.currentText()
        if self.expires_check.isChecked():
            if self.expires_check.isChecked() != self._orig_exp_checked:
                changes["expiresAt"] = self.expires_edit.dateTime().toUTC().toString(Qt.ISODate)
            elif self._orig_exp_dt is not None and self.expires_edit.dateTime() != self._orig_exp_dt:
                changes["expiresAt"] = self.expires_edit.dateTime().toUTC().toString(Qt.ISODate)
        elif self._orig_exp_checked:
            changes["expiresAt"] = None
        return changes


class LicenseDetailDialog(QDialog):
    violation_resolved = Signal(str)   # emits license_key after a successful resolve

    def __init__(self, detail: dict, parent=None, api=None, auth=None,
                 license_key: str = "", privacy_mode: bool = False):
        super().__init__(parent)
        self._api = api
        self._auth = auth
        self._privacy_mode = privacy_mode
        self._license_key = license_key
        self._selected_violations: set = set()   # violation ids selected by click
        self._violation_frames: dict = {}         # violation_id -> QFrame
        self._activation_entries: list = []       # (frame, act_dict) for filtering

        lic = detail.get("license", {})
        key_short = lic.get("key", "")[:16]
        self.setWindowTitle(
            "License Detail — ████████████████..." if privacy_mode
            else f"License Detail — {key_short}..."
        )
        self.setMinimumSize(640, 540)
        self.resize(700, 580)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # -- Overview tab (scrollable) --
        overview_inner = QWidget()
        ol = QFormLayout(overview_inner)
        ol.setContentsMargins(12, 12, 12, 12)
        for field in ("key", "email", "productId", "variant", "licenseType",
                      "status", "threatLevel", "maxMachines",
                      "createdAt", "purchasedAt", "expiresAt",
                      "purchaseId", "bundleId",
                      "disputeReason", "disputedAt"):
            val = lic.get(field)
            if val is not None:
                if privacy_mode and field in _PRIVACY_SENSITIVE_FIELDS:
                    lbl = PixelatedLabel(str(val))
                else:
                    lbl = QLabel(str(val))
                    lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
                    lbl.setWordWrap(True)
                ol.addRow(f"{field}:", lbl)
        overview_scroll = QScrollArea()
        overview_scroll.setWidgetResizable(True)
        overview_scroll.setWidget(overview_inner)
        tabs.addTab(overview_scroll, "Overview")

        # -- Activations tab (scrollable, filterable) --
        activations = detail.get("activations", [])

        act_inner = QWidget()
        al = QVBoxLayout(act_inner)
        al.setContentsMargins(8, 8, 8, 8)
        al.setSpacing(6)
        if activations:
            for act in activations:
                frame = QFrame()
                frame.setFrameShape(QFrame.StyledPanel)
                fl = QFormLayout(frame)
                for _fld, _val in (("Fingerprint:", act.get("fingerprint", "")),
                                   ("Hostname:",    act.get("hostname", ""))):
                    fl.addRow(_fld, PixelatedLabel(_val) if privacy_mode else QLabel(_val))
                fl.addRow("Countries:",    QLabel(", ".join(act.get("countries", []))))
                fl.addRow("Last Country:", QLabel(act.get("lastCountry", "")))
                fl.addRow("First Seen:",   QLabel(_format_date(act.get("firstSeen"))))
                fl.addRow("Last Seen:",    QLabel(_format_date(act.get("lastSeen"))))
                fl.addRow("Session Active:", QLabel(str(act.get("sessionActive", False))))
                al.addWidget(frame)
                self._activation_entries.append((frame, act))
        else:
            al.addWidget(QLabel("No activations."))
        al.addStretch()

        act_scroll = QScrollArea()
        act_scroll.setWidgetResizable(True)
        act_scroll.setWidget(act_inner)

        # Filter bar
        act_tab_widget = QWidget()
        act_tab_layout = QVBoxLayout(act_tab_widget)
        act_tab_layout.setContentsMargins(8, 8, 8, 8)
        act_tab_layout.setSpacing(4)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._act_search = QLineEdit()
        self._act_search.setPlaceholderText("hostname or country…")
        self._act_search.setClearButtonEnabled(True)
        filter_row.addWidget(self._act_search, 1)
        self._act_session_chk = CheckBox("")
        self._act_session_chk.setToolTip(
            "Only show activations with an active floating session.\n"
            "This field is always False for per-machine and site licenseTypes."
        )
        filter_row.addWidget(self._act_session_chk)
        self._act_count_lbl = QLabel()
        self._act_count_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._act_count_lbl.setFixedWidth(220)
        self._act_count_lbl.mousePressEvent = lambda _: self._act_session_chk.toggle()
        filter_row.addWidget(self._act_count_lbl)

        act_tab_layout.addLayout(filter_row)
        act_tab_layout.addWidget(act_scroll, 1)

        self._act_search.textChanged.connect(self._filter_activations)
        self._act_session_chk.stateChanged.connect(self._filter_activations)
        self._filter_activations()  # set initial count label

        tabs.addTab(act_tab_widget, f"Activations ({len(activations)})")

        # -- Violations tab (scrollable, click-to-select rows) --
        violations = detail.get("violations", [])
        viol_outer = QWidget()
        viol_outer_layout = QVBoxLayout(viol_outer)
        viol_outer_layout.setContentsMargins(0, 0, 0, 0)
        viol_outer_layout.setSpacing(4)

        viol_inner = QWidget()
        vl = QVBoxLayout(viol_inner)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(6)
        if violations:
            violations = sorted(violations, key=lambda v: v.get("resolved", False))
            for v in violations:
                vid = v.get("id", "")
                already_resolved = v.get("resolved", False)
                frame = QFrame()
                frame.setFrameShape(QFrame.StyledPanel)
                frame.setCursor(Qt.PointingHandCursor if not already_resolved else Qt.ArrowCursor)
                fl = QFormLayout(frame)
                fl.addRow("ID:", PixelatedLabel(vid) if privacy_mode else QLabel(vid))
                fl.addRow("Type:", QLabel(v.get("type", "")))
                fl.addRow("Severity:", QLabel(str(v.get("severity", ""))))
                fl.addRow("Detected:", QLabel(_format_date(v.get("detectedAt"))))
                fl.addRow("Resolved:", QLabel("Yes" if already_resolved else "No"))
                details = v.get("details", {})
                if details:
                    fl.addRow("Details:", QLabel(json.dumps(details, indent=2)))
                if already_resolved:
                    frame.setStyleSheet(
                        f"QFrame {{ background: {COLORS['bg_btn_disabled']}; "
                        f"color: {COLORS['text_disabled']}; }}"
                    )
                else:
                    self._violation_frames[vid] = frame
                    frame.mousePressEvent = lambda e, f=frame, v=vid: self._toggle_violation(f, v)
                vl.addWidget(frame)
        else:
            vl.addWidget(QLabel("No violations."))
        vl.addStretch()

        viol_scroll = QScrollArea()
        viol_scroll.setWidgetResizable(True)
        viol_scroll.setWidget(viol_inner)
        viol_outer_layout.addWidget(viol_scroll, 1)

        if self._violation_frames and api and auth:
            self._resolve_btn = QPushButton("Resolve Selected")
            self._resolve_btn.setProperty("cssClass", "info")
            self._resolve_btn.setEnabled(False)
            self._resolve_btn.clicked.connect(self._resolve_selected)
            viol_outer_layout.addWidget(self._resolve_btn)

        tabs.addTab(viol_outer, f"Violations ({len(violations)})")

        layout.addWidget(tabs)

        _make_dialog_buttons(layout, ok_cancel=False, reject=self.reject)

    def _filter_activations(self, *_):
        text = self._act_search.text().strip().lower()
        session_only = self._act_session_chk.isChecked()
        visible = 0
        for frame, act in self._activation_entries:
            hostname = act.get("hostname", "").lower()
            countries = ", ".join(act.get("countries", [])).lower()
            text_match = (not text) or (text in hostname) or (text in countries)
            session_match = (not session_only) or act.get("sessionActive", False)
            show = text_match and session_match
            frame.setVisible(show)
            if show:
                visible += 1
        total = len(self._activation_entries)
        if session_only:
            label = f"Showing {visible} of {total} active sessions."
        else:
            label = "Only active sessions"
        self._act_count_lbl.setText(label)

    def _toggle_violation(self, frame: QFrame, vid: str):
        if vid in self._selected_violations:
            self._selected_violations.discard(vid)
            frame.setStyleSheet("")
        else:
            self._selected_violations.add(vid)
            frame.setStyleSheet(
                f"QFrame {{ background: {COLORS['accent_dark']}; "
                f"border: 1px solid {COLORS['accent']}; }}"
            )
        if hasattr(self, "_resolve_btn"):
            self._resolve_btn.setEnabled(bool(self._selected_violations))

    def _resolve_selected(self):
        selected = list(self._selected_violations)
        if not selected:
            QMessageBox.information(self, "Nothing Selected",
                                    "Click at least one violation to select it.")
            return

        self._resolve_btn.setEnabled(False)
        self._resolve_btn.setText("Resolving…")

        api, auth, key = self._api, self._auth, self._license_key

        def do_resolve():
            return api.resolve_violations(auth, key, selected)

        def on_done(result):
            self._resolve_btn.setText("Resolve Selected")
            self._resolve_btn.setEnabled(True)
            if result.get("success"):
                self.violation_resolved.emit(key)
                self.accept()
            else:
                QMessageBox.warning(self, "Error",
                                    result.get("error", "Failed to resolve violations."))

        def on_error(msg):
            self._resolve_btn.setText("Resolve Selected")
            self._resolve_btn.setEnabled(True)
            QMessageBox.warning(self, "Error", msg)

        w = Worker(do_resolve)
        w.finished.connect(on_done)
        w.error.connect(on_error)
        self._resolve_worker = w   # keep reference alive
        w.start()


# =============================================================================
# Trial Code Dialogs
# =============================================================================

class _CreateCodeDialogBase(QDialog):
    """Shared chrome for trial code creation dialogs."""

    def __init__(self, products: dict, parent=None, preselect_product_id: str = ""):
        super().__init__(parent)
        self.setMinimumWidth(440)
        self.products = products

        self._layout = QVBoxLayout(self)
        self._form = QFormLayout()

        self.product_combo = QComboBox()
        for name, info in products.items():
            pid = info.get("productId", "")
            self.product_combo.addItem(name, pid)
        if preselect_product_id:
            idx = self.product_combo.findData(preselect_product_id)
            if idx >= 0:
                self.product_combo.setCurrentIndex(idx)
        self._form.addRow("Product:", self.product_combo)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("e.g. BLEND-NOV25-K7X4")
        gen_btn = QPushButton("Generate")
        gen_btn.setMinimumWidth(100)
        gen_btn.setToolTip("Generate a random code. Click repeatedly for different styles.")
        gen_btn.clicked.connect(self._generate_code)
        code_row = QHBoxLayout()
        code_row.setSpacing(6)
        code_row.addWidget(self.code_edit, 1)
        code_row.addWidget(gen_btn)
        self._form.addRow("Code:", code_row)

    _MONTHS = ["JAN","FEB","MAR","APR","MAY","JUN",
               "JUL","AUG","SEP","OCT","NOV","DEC"]
    # Unambiguous alphabet: no 0/O, 1/I/L to avoid misreads
    _CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

    def _generate_code(self):
        def rand(n):
            return "".join(random.choices(self._CODE_ALPHABET, k=n))

        product_name = self.product_combo.currentText()
        prod = "".join(c for c in product_name.upper() if c.isalpha())[:5]
        selected_pid = self.product_combo.currentData() or ""

        existing = {
            str(c.get("code", "")).upper()
            for c in getattr(self, "_existing_codes", [])
            if (c.get("productId") or "") == selected_pid
        }

        now = datetime.now()
        date_seg = self._MONTHS[now.month - 1] + str(now.year)[-2:]
        year_seg = str(now.year)

        code = ""
        for _ in range(20):
            pool = [rand(4), rand(4), rand(5), rand(3)]
            if prod:
                pool.append(prod)
            if random.random() < 0.55:
                pool.append(date_seg)
            elif random.random() < 0.4:
                pool.append(year_seg)

            random.shuffle(pool)
            code = "-".join(pool[:3])
            if code.upper() not in existing:
                break

        self.code_edit.setText(code)

    def _finish_build(self, *, exp_checked: bool = False, exp_initial_dt=None):
        self.max_uses_spin = QSpinBox()
        _install_big_arrows(self.max_uses_spin)
        self.max_uses_spin.setRange(-1, 1_000_000)
        self.max_uses_spin.setValue(-1)
        self.max_uses_spin.setSpecialValueText("Unlimited (-1)")
        self._form.addRow("Max Uses:", self.max_uses_spin)

        self.expires_check, self.expires_edit = _make_expiration_row(
            self._form, checked=exp_checked, initial_dt=exp_initial_dt
        )

        self._layout.addLayout(self._form)
        _make_dialog_buttons(self._layout, accept=self.accept, reject=self.reject)

    def _common_data(self) -> dict:
        data = {"code": self.code_edit.text().strip()}
        pid = self.product_combo.currentData()
        if pid:
            data["productId"] = pid
        if self.max_uses_spin.value() != -1:
            data["maxUses"] = self.max_uses_spin.value()
        if self.expires_check.isChecked():
            data["expiresAt"] = (
                self.expires_edit.dateTime().toUTC().toString(Qt.ISODate)
            )
        return data


class CreateTrialCodeDialog(_CreateCodeDialogBase):
    def __init__(self, products: dict, parent=None, preselect_product_id: str = "",
                 existing_codes: list = None):
        super().__init__(products, parent, preselect_product_id)
        self.setWindowTitle("Create Trial Code")
        self._existing_codes = existing_codes or []

        self.trial_spin = QSpinBox()
        _install_big_arrows(self.trial_spin)
        self.trial_spin.setRange(1, 3650)
        self.trial_spin.setValue(14)
        self.trial_spin.setSuffix(" days")
        self._form.addRow("Trial Duration:", self.trial_spin)

        self._finish_build(
            exp_checked=True,
            exp_initial_dt=datetime.now() + timedelta(days=30),
        )

    def get_data(self) -> dict:
        data = self._common_data()
        data["trialDays"] = self.trial_spin.value()
        return data


class EditTrialCodeDialog(QDialog):
    def __init__(self, code: dict, parent=None, privacy_mode: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Edit Trial Code")
        self.setMinimumWidth(440)
        self.code = code

        layout = QVBoxLayout(self)

        def _lbl(text: str, sensitive: bool = False) -> QLabel:
            if privacy_mode and sensitive and text:
                return PixelatedLabel(text)
            return QLabel(text)

        info_group = QGroupBox("Code Info")
        info_layout = QFormLayout()
        info_layout.addRow("Code:",           _lbl(str(code.get("code", "")), sensitive=True))
        info_layout.addRow("Used:",           _lbl(str(code.get("usedCount", 0))))
        info_layout.addRow("Trial Duration:", _lbl(str(code.get("_trialDays", "N/A"))))
        info_layout.addRow("Created:",        _lbl(_format_date(code.get("createdAt"))))
        info_layout.addRow("Product:",        _lbl(str(code.get("_productName", ""))))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        edit_group = QGroupBox("Editable Fields")
        form = QFormLayout()

        self.active_check = CheckBox("Active")
        self.active_check.setChecked(code.get("active", True))
        form.addRow("Status:", self.active_check)

        current_max = code.get("maxUses")
        if current_max == "Unlimited" or current_max is None or current_max == -1:
            current_max_val = -1
        else:
            try:
                current_max_val = int(current_max)
            except (TypeError, ValueError):
                current_max_val = -1
        self.max_uses_spin = QSpinBox()
        _install_big_arrows(self.max_uses_spin)
        self.max_uses_spin.setRange(-1, 1_000_000)
        self.max_uses_spin.setValue(current_max_val)
        self.max_uses_spin.setSpecialValueText("Unlimited (-1)")
        form.addRow("Max Uses:", self.max_uses_spin)

        _exp_checked, _exp_dt = False, None
        exp = code.get("expiresAt")
        if exp and exp != "":
            _exp_checked = True
            try:
                _exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            except Exception:
                pass
        self.expires_check, self.expires_edit = _make_expiration_row(
            form, checked=_exp_checked, initial_dt=_exp_dt
        )

        edit_group.setLayout(form)
        layout.addWidget(edit_group)

        _make_dialog_buttons(layout, accept=self.accept, reject=self.reject)

        self._orig_active = code.get("active", True)
        self._orig_max_uses = current_max_val
        self._orig_exp_checked = _exp_checked
        self._orig_exp_dt = self.expires_edit.dateTime() if _exp_checked else None

        self._changed_border = f"border: 2px solid {COLORS['field_changed']}; border-radius: 4px; padding: 2px;"
        self._tracked_widgets: list[QWidget] = [
            self.active_check, self.max_uses_spin,
            self.expires_check, self.expires_edit,
        ]
        for w in self._tracked_widgets:
            w.setProperty("_orig_style", w.styleSheet())

        self.active_check.stateChanged.connect(self._highlight_changes)
        self.max_uses_spin.valueChanged.connect(self._highlight_changes)
        self.expires_check.stateChanged.connect(self._highlight_changes)
        self.expires_edit.dateTimeChanged.connect(self._highlight_changes)

    def _mark(self, widget: QWidget, changed: bool):
        orig = widget.property("_orig_style") or ""
        widget.setStyleSheet(self._changed_border if changed else orig)

    def _highlight_changes(self):
        self._mark(self.active_check, self.active_check.isChecked() != self._orig_active)
        self._mark(self.max_uses_spin, self.max_uses_spin.value() != self._orig_max_uses)

        if self.expires_check.isChecked() != self._orig_exp_checked:
            exp_changed = True
        elif self.expires_check.isChecked() and self._orig_exp_dt is not None:
            exp_changed = self.expires_edit.dateTime() != self._orig_exp_dt
        else:
            exp_changed = False
        self._mark(self.expires_check, exp_changed)
        self._mark(self.expires_edit, exp_changed)

    def get_changes(self) -> dict:
        changes = {}
        if self.active_check.isChecked() != self._orig_active:
            changes["active"] = self.active_check.isChecked()
        if self.max_uses_spin.value() != self._orig_max_uses:
            changes["maxUses"] = self.max_uses_spin.value()
        if self.expires_check.isChecked() != self._orig_exp_checked:
            if self.expires_check.isChecked():
                changes["expiresAt"] = self.expires_edit.dateTime().toUTC().toString(Qt.ISODate)
            else:
                changes["expiresAt"] = None
        elif self.expires_check.isChecked() and self._orig_exp_dt is not None:
            if self.expires_edit.dateTime() != self._orig_exp_dt:
                changes["expiresAt"] = self.expires_edit.dateTime().toUTC().toString(Qt.ISODate)
        return changes


class TrialCodeDetailDialog(QDialog):
    """Read-only detail view for a trial code."""

    # Ordered (key, label) pairs for the fields we care to surface.
    _FIELDS = [
        ("code",         "Code"),
        ("_productName", "Product"),
        ("productId",    "Product ID"),
        ("active",       "Active"),
        ("trialDays",    "Trial Days"),
        ("usedCount",    "Used Count"),
        ("maxUses",      "Max Uses"),
        ("createdAt",    "Created"),
        ("expiresAt",    "Expires"),
    ]

    _DATE_FIELDS = frozenset({"createdAt", "expiresAt"})
    _SENSITIVE_FIELDS = frozenset({"code", "productId"})
    _SKIP_EXTRA = frozenset({
        "_statusDot", "_trialDays", "_expiresAt",
        "creatorId", "creatorID",
    })

    def __init__(self, code: dict, parent=None, privacy_mode: bool = False):
        super().__init__(parent)
        self._privacy_mode = privacy_mode
        code_str = str(code.get("code", ""))
        title = "Code Detail — ████████" if privacy_mode else f"Code Detail — {code_str}"
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        inner = QWidget()
        form = QFormLayout(inner)
        form.setContentsMargins(12, 12, 12, 12)

        shown = set()
        for key, label in self._FIELDS:
            if key not in code:
                continue
            shown.add(key)
            form.addRow(f"{label}:", self._make_value_label(code, key))

        # Show any additional fields the server returned so nothing is hidden.
        for key in sorted(code.keys()):
            if key in shown or key in self._SKIP_EXTRA or key.startswith("_"):
                continue
            form.addRow(f"{key}:", self._make_value_label(code, key))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        _make_dialog_buttons(layout, ok_cancel=False, reject=self.reject)

    def _make_value_label(self, code: dict, key: str) -> QLabel:
        val = code.get(key)
        if key in self._DATE_FIELDS and val:
            text = _format_date(val)
        elif key == "maxUses" and (val is None or val == -1):
            text = "Unlimited"
        elif isinstance(val, bool):
            text = "Yes" if val else "No"
        elif val is None or val == "":
            text = "—"
        else:
            text = str(val)
        if self._privacy_mode and key in self._SENSITIVE_FIELDS and text not in ("—", ""):
            return PixelatedLabel(text)
        lbl = QLabel(text)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setWordWrap(True)
        return lbl


# =============================================================================
# Main Window
# =============================================================================

def _secret_path() -> Path:
    return Path(__file__).parent / CREATOR_SECRET


def _load_secret() -> dict:
    path = _secret_path()
    if not path.exists():
        return {}
    data = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            data[k.strip()] = v.strip()
    except Exception as e:
        print(f"Warning: failed to read {path}: {e}")
    return data


def _save_secret(api_key: str, server_url: str = "") -> None:
    path = _secret_path()
    path.write_text(
        f"API_KEY={api_key}\nSERVER_URL={server_url}\n",
        encoding="utf-8",
    )


class ApiKeyDialog(QDialog):
    """First-launch dialog that collects the creator API key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Key Required")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(QLabel(
            "Enter your CG Lounge Creator API key.\n"
            "It will be saved to 'creator_secret.config' in the 'license_manager' folder."
        ))

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("cgls_...")
        self.key_edit.setMinimumWidth(420)
        layout.addWidget(self.key_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self):
        if not self.key_edit.text().strip():
            QMessageBox.warning(self, "API Key Required", "Please enter an API key.")
            return
        self.accept()

    def get_key(self) -> str:
        return self.key_edit.text().strip()


def _save_sort_order(logical_index: int, order):
    _save_sort_order_for("table", logical_index, order)


def _save_code_sort_order(logical_index: int, order):
    _save_sort_order_for("codeTable", logical_index, order)


def _save_sort_order_for(prefix: str, logical_index: int, order):
    s = QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope,
        "CGLounge", "Creator License Manager",
    )
    s.setValue(f"{prefix}/sortColumn", logical_index)
    s.setValue(f"{prefix}/sortOrder", order.value)


def _save_col_widths_for(prefix: str, header):
    s = QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope,
        "CGLounge", "Creator License Manager",
    )
    widths = [header.sectionSize(i) for i in range(header.count())]
    s.setValue(f"{prefix}/colWidths", ",".join(str(w) for w in widths))


def _load_col_widths_for(prefix: str) -> list:
    s = QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope,
        "CGLounge", "Creator License Manager",
    )
    raw = s.value(f"{prefix}/colWidths", "", type=str)
    if not raw:
        return []
    try:
        return [int(w) for w in str(raw).split(",") if w]
    except ValueError:
        return []


def _open_help():
    QDesktopServices.openUrl(QUrl("https://github.com/Nightingale13/CGLCreatorLicenseManager"))


def _open_issues():
    QDesktopServices.openUrl(QUrl("https://github.com/Nightingale13/CGLCreatorLicenseManager/issues"))


def _make_help_icon(size: int = 20) -> QIcon:
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(COLORS["accent"]))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(int(size * 0.65))
    painter.setFont(font)
    painter.setPen(QColor(COLORS["text_white"]))
    painter.drawText(px.rect(), Qt.AlignCenter, "?")
    painter.end()
    return QIcon(px)


def _make_bug_icon(size: int = 20) -> QIcon:
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    body = QColor(COLORS["status_revoked"])
    pen = QPen(body, max(1.0, size * 0.10))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    cx = size / 2
    body_w = size * 0.55
    body_h = size * 0.70
    body_x = cx - body_w / 2
    body_y = size * 0.22

    # Antennae
    p.setPen(pen)
    p.drawLine(int(cx - body_w * 0.30), int(body_y),
               int(cx - body_w * 0.55), int(size * 0.05))
    p.drawLine(int(cx + body_w * 0.30), int(body_y),
               int(cx + body_w * 0.55), int(size * 0.05))

    # Legs (3 per side)
    leg_y_top = body_y + body_h * 0.20
    leg_y_mid = body_y + body_h * 0.50
    leg_y_bot = body_y + body_h * 0.80
    leg_len = size * 0.22
    for ly in (leg_y_top, leg_y_mid, leg_y_bot):
        p.drawLine(int(body_x), int(ly),
                   int(body_x - leg_len), int(ly + leg_len * 0.4))
        p.drawLine(int(body_x + body_w), int(ly),
                   int(body_x + body_w + leg_len), int(ly + leg_len * 0.4))

    # Body
    p.setPen(Qt.NoPen)
    p.setBrush(body)
    p.drawEllipse(int(body_x), int(body_y), int(body_w), int(body_h))

    # Center stripe
    p.setPen(QPen(QColor(COLORS["text_white"]), max(1.0, size * 0.06)))
    p.drawLine(int(cx), int(body_y + body_h * 0.15),
               int(cx), int(body_y + body_h * 0.85))

    p.end()
    return QIcon(px)


class LicenseManager(QMainWindow):
    def _configure_table(self, table, settings_prefix: str, sort_slot) -> bool:
        """Apply shared perf-friendly settings to a QTableView.

        Returns True if persisted column widths were restored (so the caller
        can skip the one-shot resizeColumnsToContents on first load).
        """
        # Per-widget palette — replaces the old app-level QTableView /
        # QHeaderView::section QSS rules that routed every cell paint
        # through Qt's slow QStyleSheetStyle path.
        pal = table.palette()
        pal.setColor(QPalette.Base,            QColor(COLORS["bg_table"]))
        pal.setColor(QPalette.AlternateBase,   QColor(COLORS["bg_table_alt"]))
        pal.setColor(QPalette.Text,            QColor(COLORS["text_primary"]))
        pal.setColor(QPalette.Highlight,       QColor(COLORS["accent_dark"]))
        pal.setColor(QPalette.HighlightedText, QColor(COLORS["text_white"]))
        pal.setColor(QPalette.Midlight,        QColor(COLORS["border_subtle"]))
        table.setPalette(pal)
        table.setAutoFillBackground(True)
        table.setFrameShape(QFrame.StyledPanel)

        header = table.horizontalHeader()
        hpal = header.palette()
        hpal.setColor(QPalette.Button,     QColor(COLORS["bg_header"]))
        hpal.setColor(QPalette.Window,     QColor(COLORS["bg_header"]))
        hpal.setColor(QPalette.ButtonText, QColor(COLORS["text_header"]))
        hpal.setColor(QPalette.WindowText, QColor(COLORS["text_header"]))
        header.setPalette(hpal)

        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        table.verticalHeader().setDefaultSectionSize(28)

        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionsMovable(False)
        header.setHighlightSections(False)

        table.setSortingEnabled(True)
        header.sortIndicatorChanged.connect(sort_slot)

        widths = _load_col_widths_for(settings_prefix)
        if widths:
            for i, w in enumerate(widths):
                if i < header.count() and w > 0:
                    table.setColumnWidth(i, w)

        # Debounce column-width persistence: sectionResized fires on every
        # pixel of a drag (and every window-resize event, because of
        # stretchLastSection), so writing QSettings directly would hammer
        # disk and cause visible resize lag.
        save_timer = QTimer(self)
        save_timer.setSingleShot(True)
        save_timer.setInterval(300)
        save_timer.timeout.connect(
            lambda: _save_col_widths_for(settings_prefix, header)
        )
        header.sectionResized.connect(lambda *_: save_timer.start())
        last = header.count() - 1
        header.setSectionResizeMode(last, QHeaderView.ResizeToContents)
        return bool(widths)

    def _grow_columns(self, table, prefix: str):
        """Expand any column that is narrower than its current content; never shrink."""
        header = table.horizontalHeader()
        changed = False
        last = header.count() - 1
        for col in range(last):  # skip last col — it's ResizeToContents
            needed = table.sizeHintForColumn(col)
            if needed > header.sectionSize(col):
                table.setColumnWidth(col, needed)
                changed = True
        if changed:
            _save_col_widths_for(prefix, header)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"CGLounge Creator License Manager   v{VERSION}")
        self.setMinimumSize(1300, 400)
        self.resize(1850, 800)

        _icon_path = Path(__file__).parent / "icon.png"
        if _icon_path.exists():
            self.setWindowIcon(QIcon(str(_icon_path)))

        if _secret_path().exists():
            secret = _load_secret()
            api_key = secret.get("API_KEY", "")
        else:
            secret = {}
            dlg = ApiKeyDialog(self)
            if dlg.exec() != QDialog.Accepted:
                QTimer.singleShot(0, self.close)
                api_key = ""
            else:
                api_key = dlg.get_key()
                _save_secret(api_key, "")
                secret = _load_secret()

        self.api_key = api_key
        self.server_url = secret.get("SERVER_URL") or DEFAULT_SERVER_URL
        # productName -> {"productId": str, "status": str, "active": bool, "slug": str}
        # Populated from /listProducts on launch and on every Refresh.
        self.products: dict = {}
        self.api = APIClient(self.server_url)
        self._workers: list = []
        self._active_workers: int = 0

        self._setup_ui()
        self._apply_style()
        self._update_button_states()

        self._activation_timer = QTimer(self)
        self._activation_timer.setInterval(60_000)
        self._activation_timer.timeout.connect(self._auto_refresh_licenses)

        # Countdown label pinned to the right of the status bar
        self._countdown_lbl = QLabel()
        self._countdown_lbl.setStyleSheet(
            f"color: {COLORS['text_countdown']}; font-size: 11px; padding: 0 8px 0 0;"
        )
        self._countdown_lbl.setFixedWidth(260)
        self._countdown_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusBar().addPermanentWidget(self._countdown_lbl)

        self._countdown_tick = QTimer(self)
        self._countdown_tick.setInterval(1000)
        self._countdown_tick.setTimerType(Qt.TimerType.CoarseTimer)
        self._countdown_tick.timeout.connect(self._update_countdown)
        self._countdown_tick.start()
        self._update_countdown()

        if self.api_key:
            QTimer.singleShot(200, self._refresh_all)

    def _get_auth(self) -> dict:
        """Get auth dict using the creator-scoped apiKey."""
        if self.api_key:
            return {"apiKey": self.api_key}
        return {}

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # ---- Top (shared) toolbar ----
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Product Status:"))
        self.product_status_combo = QComboBox()
        self.product_status_combo.setMinimumWidth(110)
        for label, value in (("All", ""), ("Live", "live"),
                             ("Unlisted", "unlisted"), ("Archived", "archived")):
            self.product_status_combo.addItem(label, value)
        self.product_status_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.product_status_combo)

        toolbar.addSpacing(12)

        toolbar.addWidget(QLabel("Product:"))
        self.product_combo = QComboBox()
        self.product_combo.setMinimumWidth(200)
        self.product_combo.addItem("All Products", "")
        for name, info in self.products.items():
            pid = info.get("productId", "")
            self.product_combo.addItem(name, pid)
        self.product_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.product_combo)

        toolbar.addSpacing(20)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search...")
        self.search_edit.setMinimumWidth(240)
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_edit)

        toolbar.addStretch()

        settings = QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope,
            "CGLounge", "Creator License Manager",
        )
        snap_col = QVBoxLayout()
        snap_col.setContentsMargins(0, 0, 0, 0)
        snap_col.setSpacing(0)
        self.snap_tabs_cb = _make_settings_checkbox(
            "Snap Tabs", "ui/snapTabs", self._on_snap_tabs_toggled, settings,
        )
        self.snap_tabs_cb.setToolTip(
            "Resize the window to exactly fit the columns of the active tab "
            "when switching tabs."
        )
        self.snap_centre_cb = _make_settings_checkbox(
            "Snap Centre", "ui/snapCentre", self._on_snap_centre_toggled, settings,
        )
        self.snap_centre_cb.setToolTip(
            "Re-center the app after switching tabs."
        )
        self.snap_centre_cb.setStyleSheet(
            f"QCheckBox:disabled {{ color: {COLORS['text_muted']}; }}"
        )
        self.snap_centre_cb.setEnabled(self.snap_tabs_cb.isChecked())
        snap_col.addWidget(self.snap_tabs_cb)
        snap_col.addWidget(self.snap_centre_cb)
        toolbar.addLayout(snap_col)

        toolbar.addSpacing(12)

        self.privacy_cb = _make_settings_checkbox("Privacy Mode", "filter/privacyMode", self._toggle_privacy_mode, settings)
        self.privacy_cb.setToolTip(
            "Pixelate sensitive fields (license keys, emails, codes, etc) in the "
            "tables and detail dialogs so the screen is safe to share."
        )
        toolbar.addWidget(self.privacy_cb)

        toolbar.addSpacing(16)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        toolbar.addWidget(self.count_label)

        toolbar.addSpacing(12)

        self.help_btn = QPushButton()
        self.help_btn.setIcon(_make_help_icon(18))
        self.help_btn.setIconSize(QSize(18, 18))
        self.help_btn.setFixedWidth(32)
        self.help_btn.setToolTip("Open documentation")
        self.help_btn.clicked.connect(_open_help)
        toolbar.addWidget(self.help_btn)

        self.bug_btn = QPushButton()
        self.bug_btn.setIcon(_make_bug_icon(18))
        self.bug_btn.setIconSize(QSize(18, 18))
        self.bug_btn.setFixedWidth(32)
        self.bug_btn.setToolTip("Report a bug / open an issue on GitHub")
        self.bug_btn.clicked.connect(_open_issues)
        toolbar.addWidget(self.bug_btn)

        main_layout.addLayout(toolbar)

        # ---- Tabs ----
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        # ============================================================
        # Licenses tab
        # ============================================================
        licenses_page = QWidget()
        lic_layout = QVBoxLayout(licenses_page)
        lic_layout.setContentsMargins(0, 8, 0, 0)
        lic_layout.setSpacing(6)

        lic_subbar = QHBoxLayout()
        self.hide_trials_cb = _make_settings_checkbox("Hide Trials", "filter/hideTrials", self._on_filter_changed, settings)
        self.hide_trials_cb.setToolTip("Hide trial licenses.")
        lic_subbar.addWidget(self.hide_trials_cb)
        self.hide_disabled_cb = _make_settings_checkbox("Hide Disabled", "filter/hideDisabled", self._on_filter_changed, settings)
        self.hide_disabled_cb.setToolTip("Hide revoked/disabled licenses.")
        lic_subbar.addWidget(self.hide_disabled_cb)
        self.hide_expired_cb = _make_settings_checkbox("Hide Expired", "filter/hideExpired", self._on_filter_changed, settings)
        self.hide_expired_cb.setToolTip("Hide any licenses that have expired.")
        lic_subbar.addWidget(self.hide_expired_cb)
        lic_subbar.addStretch()
        lic_layout.addLayout(lic_subbar)

        self.model = LicenseTableModel(self.products)
        self.proxy = LicenseFilterProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)

        self.table = LicenseTableView()
        self.table.setModel(self.proxy)
        self._lic_col_widths_restored = self._configure_table(
            self.table, "table", _save_sort_order
        )
        self.table.setItemDelegateForColumn(0, StatusDelegate(self.table))
        self._privacy_delegate = PrivacyDelegate(self.table)
        for col_idx in _PRIVACY_SENSITIVE_COLS:
            self.table.setItemDelegateForColumn(col_idx, self._privacy_delegate)
        if self.privacy_cb.isChecked():
            self._privacy_delegate.set_privacy(True)
            self.model.set_privacy_mode(True)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.selectionModel().selectionChanged.connect(
            self._update_button_states
        )
        self.table.selectionModel().selectionChanged.connect(
            lambda: self.table.viewport().update()
        )

        lic_layout.addWidget(self.table, 1)
        self.tabs.addTab(licenses_page, "Licenses")

        # ============================================================
        # Trial Codes tab
        # ============================================================
        codes_page = QWidget()
        codes_layout = QVBoxLayout(codes_page)
        codes_layout.setContentsMargins(0, 8, 0, 0)
        codes_layout.setSpacing(6)

        codes_subbar = QHBoxLayout()
        self.hide_disabled_codes_cb = _make_settings_checkbox(
            "Hide Disabled", "filter/hideDisabledCodes",
            self._on_codes_filter_changed, settings,
        )
        self.hide_disabled_codes_cb.setToolTip(
            "Hide disabled trial codes from the table."
        )
        codes_subbar.addWidget(self.hide_disabled_codes_cb)
        self.hide_expired_codes_cb = _make_settings_checkbox(
            "Hide Expired", "filter/hideExpiredCodes",
            self._on_codes_filter_changed, settings,
        )
        self.hide_expired_codes_cb.setToolTip(
            "Hide trial codes that have passed their expiration date."
        )
        codes_subbar.addWidget(self.hide_expired_codes_cb)
        codes_subbar.addStretch()
        codes_layout.addLayout(codes_subbar)

        self.code_model = TrialCodeTableModel()
        self.code_proxy = TrialCodeFilterProxy()
        self.code_proxy.setSourceModel(self.code_model)
        self.code_proxy.setDynamicSortFilter(True)
        self._on_codes_filter_changed()

        self.code_table = QTableView()
        self.code_table.setModel(self.code_proxy)
        self._code_col_widths_restored = self._configure_table(
            self.code_table, "codeTable", _save_code_sort_order
        )
        self.code_table.setItemDelegateForColumn(0, CodeStatusDelegate(self.code_table))
        _code_col_idx = next(
            (i for i, (k, _) in enumerate(TRIAL_CODE_COLUMNS) if k == "code"),
            None,
        )
        if _code_col_idx is not None:
            self.code_table.setItemDelegateForColumn(_code_col_idx, self._privacy_delegate)
        self.code_table.doubleClicked.connect(self._view_code_detail)
        self.code_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.code_table.customContextMenuRequested.connect(self._show_code_context_menu)
        self.code_table.selectionModel().selectionChanged.connect(
            self._update_button_states
        )

        codes_layout.addWidget(self.code_table, 1)
        self.tabs.addTab(codes_page, "Trial Codes")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        # ---- Busy progress bar (full-width, shown during async ops) ----
        self._busy_bar = QProgressBar()
        self._busy_bar.setRange(0, 0)  # indeterminate
        self._busy_bar.setFixedHeight(6)
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setStyleSheet(
            "QProgressBar { border: none; background: transparent; }"
            f"QProgressBar::chunk {{ background: {COLORS['accent']}; border-radius: 3px; }}"
        )
        self._busy_bar.hide()
        main_layout.addWidget(self._busy_bar)

        # ---- Bottom action bar (stacked: swaps with active tab) ----
        self._action_stack = QStackedLayout()

        # -- Page 0: Licenses bar --
        licenses_bar_widget = QWidget()
        action_bar = QHBoxLayout(licenses_bar_widget)
        action_bar.setContentsMargins(0, 0, 0, 0)

        self.refresh_btn = _make_action_button("Refresh", self._refresh_all, action_bar)
        self.create_btn = _make_action_button("+ Create License", self._create_license, action_bar, css_class="success")
        self.edit_btn = _make_action_button("Edit Selected", self._edit_selected, action_bar)
        self.detail_btn = _make_action_button("View Details", self._view_detail, action_bar)

        action_bar.addSpacing(20)

        self.revoke_btn = _make_action_button("Revoke License", lambda: None, action_bar, css_class="danger")
        self.revoke_btn.setMenu(self._build_revoke_menu(self.revoke_btn))
        self.suspend_btn = _make_action_button("Suspend License", self._suspend_selected, action_bar, css_class="warning")
        self.reinstate_btn = _make_action_button("Reinstate License", self._reinstate_selected, action_bar, css_class="success")
        self.reset_activations_btn = _make_action_button("Reset Activations", self._reset_activations, action_bar, css_class="info")

        action_bar.addStretch()

        self.copy_key_btn = _make_action_button("Copy Key", self._copy_key, action_bar)
        self._action_stack.addWidget(licenses_bar_widget)

        # -- Page 1: Codes bar --
        codes_bar_widget = QWidget()
        codes_action_bar = QHBoxLayout(codes_bar_widget)
        codes_action_bar.setContentsMargins(0, 0, 0, 0)

        self.refresh_codes_btn = _make_action_button("Refresh", self._refresh_all, codes_action_bar)
        self.create_trial_btn = _make_action_button("+ Create Trial Code", self._create_trial, codes_action_bar, css_class="success")
        self.edit_code_btn = _make_action_button("Edit Selected", self._edit_selected_code, codes_action_bar)
        self.detail_code_btn = _make_action_button("View Details", self._view_code_detail, codes_action_bar)

        codes_action_bar.addSpacing(20)

        self.toggle_code_btn = _make_action_button("Enable / Disable", self._toggle_code_active, codes_action_bar, css_class="warning")
        self.delete_code_btn = _make_action_button("Delete Code", self._delete_selected_code, codes_action_bar, css_class="danger")

        codes_action_bar.addStretch()

        self.copy_code_btn = _make_action_button("Copy Code", self._copy_code, codes_action_bar)
        self._action_stack.addWidget(codes_bar_widget)

        action_stack_host = QWidget()
        action_stack_host.setLayout(self._action_stack)
        main_layout.addWidget(action_stack_host)

        self.statusBar().showMessage("Ready")

        # Restore persisted sort order (default: threat level ascending)
        _threat_col = next(i for i, (k, _) in enumerate(LICENSE_COLUMNS) if k == "threatLevel")
        _sort_col = settings.value("table/sortColumn", _threat_col, type=int)
        _sort_order = Qt.SortOrder(settings.value("table/sortOrder", 0, type=int))
        self.table.sortByColumn(_sort_col, _sort_order)

        _code_default_col = next(
            (i for i, (k, _) in enumerate(TRIAL_CODE_COLUMNS) if k == "code"), 0
        )
        _code_sort_col = settings.value("codeTable/sortColumn", _code_default_col, type=int)
        _code_sort_order = Qt.SortOrder(settings.value("codeTable/sortOrder", 0, type=int))
        self.code_table.sortByColumn(_code_sort_col, _code_sort_order)

        # Restore persisted active tab
        _saved_tab = int(settings.value("ui/currentTab", 0, type=int) or 0)
        if 0 <= _saved_tab < self.tabs.count():
            self.tabs.setCurrentIndex(_saved_tab)
            self._on_tab_changed(_saved_tab)

        # Keyboard shortcuts
        QShortcut(QKeySequence("F5"), self, self._refresh_all)
        mod = "Meta" if sys.platform == "darwin" else "Ctrl"
        QShortcut(QKeySequence(f"{mod}+N"), self, self._new_shortcut)

    def _new_shortcut(self):
        # Ctrl+N: create license on Licenses tab, create trial code on Trial Codes tab.
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            self._create_trial()
        else:
            self._create_license()

    def _apply_style(self):
        self.setStyleSheet(DARK_STYLE)

    # -- Button state management --
    def _update_button_states(self):
        selected = self.table.selectionModel().selectedRows()
        has_any = len(selected) > 0
        has_one = len(selected) == 1

        lics = self._selected_licenses() if has_any else []
        statuses = [_effective_status(lic) for lic in lics]
        can_revoke    = bool(statuses) and all(s != "revoked" for s in statuses)
        can_suspend   = any(s not in ("suspended", "revoked") for s in statuses)
        can_reinstate = bool(statuses) and all(s in ("suspended", "revoked") for s in statuses)

        self.edit_btn.setEnabled(has_one)
        self.detail_btn.setEnabled(has_one)
        self.revoke_btn.setEnabled(can_revoke)
        self.suspend_btn.setEnabled(can_suspend)
        self.reinstate_btn.setEnabled(can_reinstate)
        self.reset_activations_btn.setEnabled(has_any)
        self.copy_key_btn.setEnabled(has_any)

        code_selected = self.code_table.selectionModel().selectedRows() if hasattr(self, "code_table") else []
        codes = self._selected_codes() if code_selected else []
        code_any = len(code_selected) > 0
        code_one = len(code_selected) == 1
        if hasattr(self, "edit_code_btn"):
            all_active   = all(c.get("active", True) for c in codes)
            all_disabled = all(not c.get("active", True) for c in codes)
            self.edit_code_btn.setEnabled(code_one)
            self.detail_code_btn.setEnabled(code_one)
            self.toggle_code_btn.setEnabled(code_any)
            if code_any:
                if all_active:
                    self.toggle_code_btn.setText("Disable")
                elif all_disabled:
                    self.toggle_code_btn.setText("Enable")
                else:
                    self.toggle_code_btn.setText("Enable / Disable")
            else:
                self.toggle_code_btn.setText("Enable / Disable")
            self.delete_code_btn.setEnabled(code_any)
            self.copy_code_btn.setEnabled(code_any)

    def _on_tab_changed(self, index: int):
        self._action_stack.setCurrentIndex(index)
        self._update_button_states()
        self._update_count()
        QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope,
            "CGLounge", "Creator License Manager",
        ).setValue("ui/currentTab", index)
        if self.snap_tabs_cb.isChecked():
            QTimer.singleShot(0, self._snap_to_current_tab)

    def _on_snap_tabs_toggled(self, checked: bool):
        self.snap_centre_cb.setEnabled(checked)
        if checked:
            QTimer.singleShot(0, self._snap_to_current_tab)

    def _on_snap_centre_toggled(self, checked: bool):
        if checked and self.snap_tabs_cb.isChecked():
            QTimer.singleShot(0, self._snap_to_current_tab)

    def _snap_to_current_tab(self):
        if not self.snap_tabs_cb.isChecked():
            return
        table = self.table if self.tabs.currentIndex() == 0 else self.code_table
        header = table.horizontalHeader()
        cols_total = sum(header.sectionSize(i) for i in range(header.count()))
        vsb = table.verticalScrollBar()
        vsb_w = vsb.sizeHint().width() if vsb is not None else 0
        frame_pad = 2 * table.frameWidth()
        target_table_width = cols_total + vsb_w + frame_pad + 2

        delta = target_table_width - table.width()
        new_w = self.width() + delta

        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry()
        new_w = max(self.minimumWidth(), min(new_w, avail.width()))

        self.resize(new_w, self.height())

        if self.snap_centre_cb.isChecked():
            geo = self.frameGeometry()
            geo.moveCenter(avail.center())
            self.move(geo.topLeft())

    # -- Helpers --
    def _selected_licenses(self) -> List[dict]:
        indexes = self.table.selectionModel().selectedRows()
        result = []
        for idx in indexes:
            source_idx = self.proxy.mapToSource(idx)
            lic = self.model.get_row(source_idx.row())
            if lic:
                result.append(lic)
        return result

    def _run_async(self, fn, callback, error_cb=None):
        """Note this is not python async, this is a multi-threadded process in QThread."""
        w = Worker(fn)
        w.finished.connect(callback)
        if error_cb:
            w.error.connect(error_cb)
        else:
            w.error.connect(lambda msg: self._show_error(msg))
        self._workers.append(w)
        w.finished.connect(lambda: self._workers.remove(w)
                           if w in self._workers else None)
        w.error.connect(lambda: self._workers.remove(w)
                        if w in self._workers else None)
        w.finished.connect(self._on_worker_done)
        w.error.connect(self._on_worker_done)

        self._active_workers += 1
        if self._active_workers == 1:
            self._busy_bar.show()
            QApplication.setOverrideCursor(Qt.WaitCursor)

        w.start()

    def _on_worker_done(self):
        self._active_workers = max(0, self._active_workers - 1)
        if self._active_workers == 0:
            self._busy_bar.hide()
            QApplication.restoreOverrideCursor()

    def _toggle_privacy_mode(self, checked: bool):
        self._privacy_delegate.set_privacy(checked)
        self.model.set_privacy_mode(checked)
        self.table.viewport().update()
        self.code_table.viewport().update()

    def _update_countdown(self):
        remaining = self._activation_timer.remainingTime()
        if remaining < 0:
            text = "License auto-refresh: ↻ —"
        else:
            text = f"License auto-refresh: ↻ {remaining // 1000}s"
        if self._countdown_lbl.text() != text:
            self._countdown_lbl.setText(text)

    def _show_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}", 8000)
        QMessageBox.warning(self, "Error", msg)

    def _show_status(self, msg: str, timeout: int = 5000):
        self.statusBar().showMessage(msg, timeout)

    # -- Filters --
    def _allowed_pids_for_status(self):
        """Return a set of productIds matching the current Product Status filter,
        or None if no status filter is active."""
        if not hasattr(self, "product_status_combo"):
            return None
        wanted = self.product_status_combo.currentData() or ""
        if not wanted:
            return None
        return {
            info.get("productId", "")
            for info in self.products.values()
            if (info.get("status") or "").lower() == wanted
            and info.get("productId")
        }

    def _on_filter_changed(self):
        pid = self.product_combo.currentData() or ""
        allowed = self._allowed_pids_for_status()
        self.proxy.set_filters(
            hide_trials=self.hide_trials_cb.isChecked(),
            hide_disabled=self.hide_disabled_cb.isChecked(),
            hide_expired=self.hide_expired_cb.isChecked(),
            product_filter=pid,
            allowed_product_ids=allowed,
        )
        if hasattr(self, "code_proxy"):
            self.code_proxy.set_filters(
                product_filter=pid, allowed_product_ids=allowed,
            )
        self._update_count()

    def _on_codes_filter_changed(self):
        if hasattr(self, "code_proxy"):
            self.code_proxy.set_filters(
                hide_disabled=self.hide_disabled_codes_cb.isChecked(),
                hide_expired=self.hide_expired_codes_cb.isChecked(),
            )
        self._update_count()

    def _on_search_changed(self, text):
        self.proxy.set_filters(search_text=text)
        if hasattr(self, "code_proxy"):
            self.code_proxy.set_filters(search_text=text)
        self._update_count()

    def _update_count(self):
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 1:
            total = self.code_model.rowCount()
            visible = self.code_proxy.rowCount()
            self.count_label.setText(f"Showing {visible} of {total} codes")
        else:
            total = self.model.rowCount()
            visible = self.proxy.rowCount()
            self.count_label.setText(f"Showing {visible} of {total} licenses")

    # -- Actions --
    def _populate_product_combo(self):
        """Rebuild the product filter combo from self.products, preserving selection."""
        prev_pid = self.product_combo.currentData() if self.product_combo.count() else ""
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        self.product_combo.addItem("All Products", "")
        for name, info in self.products.items():
            pid = info.get("productId", "")
            self.product_combo.addItem(name, pid)
        if prev_pid:
            idx = self.product_combo.findData(prev_pid)
            if idx >= 0:
                self.product_combo.setCurrentIndex(idx)
        self.product_combo.blockSignals(False)

    def _refresh_products(self, then=None):
        """Fetch the product list from the server and update self.products."""
        auth = self._get_auth()
        if not auth:
            if then:
                then()
            return

        def fetch():
            return self.api.list_products(auth, include_all=True)

        def on_done(result):
            if result.get("success"):
                new_products: dict = {}
                for p in result.get("products", []):
                    name = p.get("name") or p.get("productId", "")
                    new_products[name] = {
                        "productId": p.get("productId", ""),
                        "status": p.get("status", ""),
                        "active": p.get("active", True),
                        "slug": p.get("slug", ""),
                    }
                self.products = new_products
                pname_map = {
                    info["productId"]: name
                    for name, info in new_products.items()
                    if info.get("productId")
                }
                self.model.set_product_names(pname_map)
                pstatus_map = {
                    info["productId"]: info.get("status", "")
                    for info in new_products.values()
                    if info.get("productId")
                }
                self.model.set_product_statuses(pstatus_map)
                if hasattr(self, "code_model"):
                    self.code_model.set_product_names(pname_map)
                    self.code_model.set_product_statuses(pstatus_map)
                self._populate_product_combo()
                # Re-apply filters now that product statuses are known
                self._on_filter_changed()
                self._show_status(f"Loaded {len(new_products)} product(s)")
                if then:
                    then()
            else:
                msg = result.get("error") or "Failed to list products"
                self._show_error(f"{msg} (HTTP {result.get('_status', '?')})")

        self._run_async(fetch, on_done)

    def _refresh_all(self):
        """Refresh products, then licenses and trial codes."""
        def after_products():
            self._refresh_licenses()
            self._refresh_codes()
        self._refresh_products(then=after_products)

    def _auto_refresh_licenses(self):
        """60-second auto-refresh."""
        self._refresh_licenses()

    def _refresh_licenses(self):
        self._activation_timer.stop()
        self._show_status("Refreshing licenses...")
        self.refresh_btn.setEnabled(False)

        def fetch():
            all_licenses = []
            errors = []
            for name, info in self.products.items():
                product_id = info.get("productId", "")
                auth = self._get_auth()
                if not auth:
                    print(f"[DEBUG] {name}: No auth configured, skipping")
                    continue

                result = self.api.list_licenses(auth, product_id=product_id, limit=500)
                licenses = result.get("licenses", [])
                if result.get("success"):
                    for lic in licenses:
                        if not lic.get("productId"):
                            lic["productId"] = product_id
                    all_licenses.extend(licenses)
                else:
                    err = result.get("error", "Unknown error")
                    status_code = result.get("_status", "?")
                    errors.append(f"{name}: {err} (HTTP {status_code})")

            if errors and not all_licenses:
                raise Exception(
                    "Failed to load licenses:\n" + "\n".join(errors)
                )
            return all_licenses

        def on_done(licenses):
            self.model.set_data(licenses)
            self.proxy.invalidateFilter()
            if not self._lic_col_widths_restored:
                self.table.resizeColumnsToContents()
                _save_col_widths_for("table", self.table.horizontalHeader())
                self._lic_col_widths_restored = True
                if self.snap_tabs_cb.isChecked() and self.tabs.currentIndex() == 0:
                    QTimer.singleShot(0, self._snap_to_current_tab)
            else:
                self._grow_columns(self.table, "table")
            self._update_count()
            self.refresh_btn.setEnabled(True)
            self._update_button_states()
            self._show_status(f"Loaded {len(licenses)} licenses")
            self._activation_timer.start()
            self._update_countdown()

        def on_err(msg):
            self.refresh_btn.setEnabled(True)
            self._show_error(msg)

        self._run_async(fetch, on_done, on_err)

    def _create_license(self):
        if not self.products:
            self._show_error("No products loaded yet. Click Refresh.")
            return

        selected_pid = self.product_combo.currentData() or ""
        dlg = CreateLicenseDialog(self.products, self.api, self._get_auth(), self,
                                  preselect_product_id=selected_pid,
                                  privacy_mode=self.privacy_cb.isChecked())
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.get_data()
        auth = self._get_auth()

        if not data.get("email"):
            self._show_error("Email is required.")
            return

        def create():
            return self.api.create_license(auth, **data)

        def on_done(result):
            if result.get("success"):
                key = result.get("licenseKey", "")
                self._show_status(f"License created: {key[:12]}...")
                QApplication.clipboard().setText(key)
                QMessageBox.information(
                    self, "License Created",
                    f"License key copied to clipboard:\n\n{key}"
                )
                self._refresh_licenses()
            else:
                self._show_error(result.get("error", "Creation failed"))

        self._run_async(create, on_done)

    def _edit_selected(self):
        selected = self._selected_licenses()
        if len(selected) != 1:
            return

        lic = selected[0]
        dlg = EditLicenseDialog(lic, self.api, self._get_auth(), self,
                                privacy_mode=self.privacy_cb.isChecked())
        if dlg.exec() != QDialog.Accepted:
            return

        changes = dlg.get_changes()
        if not changes:
            self._show_status("No changes made.")
            return

        auth = self._get_auth()
        license_key = lic["key"]

        def update():
            result = self.api.update_license(auth, license_key, **changes)
            return result

        def on_done(result):
            if result.get("success"):
                self.model.update_license_row(license_key, changes)
                self._update_count()
                self._update_button_states()
                self._show_status("License updated. Refreshing...")
                self._drip_single_license(license_key)
            else:
                status = result.get("_status", "?")
                msg = result.get("error") or result.get("message") or str(result)
                self._show_error(f"Update failed (HTTP {status}): {msg}")

        self._run_async(update, on_done)

    def _refresh_selected_licenses(self):
        selected = self._selected_licenses()
        if not selected:
            return
        count = len(selected)
        self._show_status(f"Refreshing {count} license{'s' if count > 1 else ''}...")
        for lic in selected:
            self._drip_single_license(lic["key"])

    def _drip_single_license(self, license_key: str):
        auth = self._get_auth()

        def fetch():
            return self.api.get_license(auth, license_key)

        def on_done(result):
            if result.get("success"):
                self.model.update_license_row(license_key, result)
                machines_used = result.get("machinesUsed")
                if machines_used is not None:
                    self.model.update_activation_count(license_key, machines_used)
                unresolved = result.get("unresolvedViolationsCount")
                if unresolved is None:
                    violations = result.get("violations", [])
                    unresolved = sum(1 for v in violations if not v.get("resolved"))
                self.model.update_violation_count(license_key, unresolved)
                self._show_status("License updated.")

        self._run_async(fetch, on_done)

    def _view_detail(self):
        selected = self._selected_licenses()
        if len(selected) != 1:
            return

        lic = selected[0]
        auth = self._get_auth()
        self._show_status("Loading license details...")

        def fetch_detail():
            return self.api.get_license(auth, lic["key"])

        def on_done(result):
            if result.get("success"):
                machines_used = result.get("machinesUsed")
                if machines_used is not None:
                    self.model.update_activation_count(lic["key"], machines_used)
                lic_data = result.get("license") or {}
                unresolved = lic_data.get("unresolvedViolationsCount")
                if unresolved is None:
                    violations = result.get("violations", [])
                    unresolved = sum(1 for v in violations if not v.get("resolved"))
                self.model.update_violation_count(lic["key"], unresolved)
                dlg = LicenseDetailDialog(
                    result, self,
                    api=self.api,
                    auth=self._get_auth(),
                    license_key=lic["key"],
                    privacy_mode=self.privacy_cb.isChecked(),
                )
                dlg.violation_resolved.connect(self._refresh_single_license)
                dlg.exec()
            else:
                self._show_error(result.get("error", "Failed to get details"))

        self._run_async(fetch_detail, on_done)

    def _refresh_single_license(self, license_key: str):
        """Fetch one license from the server and update its row in the table."""
        auth = self._get_auth()

        def fetch():
            return self.api.get_license(auth, license_key)

        def on_done(result):
            if result.get("success"):
                lic = result.get("license", {})
                self.model.update_license_row(license_key, lic)
                self._show_status("License updated.")
            else:
                self._show_error(result.get("error", "Failed to refresh license."))

        self._run_async(fetch, on_done)

    def _reset_activations(self):
        selected = self._selected_licenses()
        if not selected:
            return

        count = len(selected)
        if not _confirm(self, "Confirm Reset Activations",
                        f"Reset all machine activations for {count} license(s)?\n\n"
                        "This will deactivate all machines and allow fresh activations."):
            return

        auth = self._get_auth()

        def do_reset():
            results = []
            for lic in selected:
                r = self.api.reset_activations(auth, lic["key"])
                results.append((lic["key"], r))
            return results

        def on_done(results):
            failed = [(k, r) for k, r in results if not r.get("success")]
            total_deleted = sum(r.get("deletedCount", 0) for _, r in results)
            if failed:
                self._show_error(f"Failed for {len(failed)} license(s).")
            else:
                self._show_status(
                    f"Reset {count} license(s) — {total_deleted} activation(s) removed."
                )
            for key, r in results:
                if r.get("success"):
                    self._drip_single_license(key)

        self._run_async(do_reset, on_done)

    _REVOKE_OPTIONS = [
        ("Revoke",          "manual",    "Revoked",
         "Generic admin revoke.\n\n"
         "Revoke {n} license(s)? This will immediately prevent activation and validation."),
        ("Revoke as Fraud", "fraud",     "Revoked (fraud)",
         "Admin flagged the license as fraudulent.\n\n"
         "Revoke {n} license(s) as fraud? This will immediately prevent activation and validation."),
        ("Cancel License",  "cancelled", "Cancelled",
         "Order cancelled outside the payment flow.\n\n"
         "Cancel {n} license(s)? This will immediately prevent activation and validation."),
    ]

    def _build_revoke_menu(self, parent) -> QMenu:
        menu = QMenu(parent)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        for label, reason, past_tense, confirm_fmt in self._REVOKE_OPTIONS:
            menu.addAction(
                label,
                lambda r=reason, pt=past_tense, cf=confirm_fmt:
                    self._revoke_with_reason(r, pt, cf),
            )
        return menu

    def _revoke_with_reason(self, reason: str, past_tense: str, confirm_fmt: str):
        selected = [lic for lic in self._selected_licenses()
                    if (lic.get("status") or "").lower() != "revoked"]
        if not selected:
            return

        if not _confirm(self, "Confirm Revoke", confirm_fmt.format(n=len(selected))):
            return

        api = self.api

        def do_revoke(auth, key):
            return api.revoke_license(auth, key, reason=reason)

        self._bulk_license_action(selected, do_revoke, past_tense)

    def _suspend_selected(self):
        selected = [lic for lic in self._selected_licenses()
                    if (lic.get("status") or "").lower() not in ("suspended", "revoked")]
        if not selected:
            return

        count = len(selected)
        if not _confirm(self, "Confirm Suspend",
                        f"Suspend {count} license(s)?\n\n"
                        "The license(s) will be marked as suspended and cannot be used until reinstated."):
            return

        self._bulk_license_action(selected, self.api.suspend_license, "Suspended")

    def _reinstate_selected(self):
        selected = [lic for lic in self._selected_licenses()
                    if (lic.get("status") or "").lower() in ("suspended", "revoked")]
        if not selected:
            return

        self._bulk_license_action(selected, self.api.reinstate_license, "Reinstated")

    def _bulk_license_action(self, licenses: list, api_method, past_tense: str):
        auth = self._get_auth()

        def work():
            return [api_method(auth, lic["key"]) for lic in licenses if auth]

        def on_done(results):
            ok = sum(1 for r in results if r.get("success"))
            self._show_status(f"{past_tense} {ok}/{len(results)} licenses.")
            self._refresh_licenses()

        self._run_async(work, on_done)

    def _copy_key(self):
        selected = self._selected_licenses()
        if not selected:
            return
        keys = [lic.get("key", "") for lic in selected]
        QApplication.clipboard().setText("\n".join(keys))
        self._show_status(f"Copied {len(keys)} key(s) to clipboard.")

    def _on_row_double_clicked(self, index):
        self._view_detail()

    def _show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        selected = self._selected_licenses()
        has_any = len(selected) > 0
        has_one = len(selected) == 1

        statuses = [_effective_status(lic) for lic in selected]
        can_revoke    = bool(statuses) and all(s != "revoked" for s in statuses)
        can_suspend   = any(s not in ("suspended", "revoked") for s in statuses)
        can_reinstate = bool(statuses) and all(s in ("suspended", "revoked") for s in statuses)

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        a = menu.addAction("View Details", self._view_detail)
        a.setEnabled(has_one)
        a = menu.addAction("Edit License", self._edit_selected)
        a.setEnabled(has_one)
        menu.addSeparator()
        a = menu.addAction("Copy License Key", self._copy_key)
        a.setEnabled(has_any)
        menu.addSeparator()
        revoke_submenu = menu.addMenu("Revoke License")
        revoke_submenu.setStyleSheet(CONTEXT_MENU_STYLE)
        revoke_submenu.setEnabled(can_revoke)
        for label, reason, past_tense, confirm_fmt in self._REVOKE_OPTIONS:
            revoke_submenu.addAction(
                label,
                lambda r=reason, pt=past_tense, cf=confirm_fmt:
                    self._revoke_with_reason(r, pt, cf),
            )
        a = menu.addAction("Suspend License", self._suspend_selected)
        a.setEnabled(can_suspend)
        a = menu.addAction("Reinstate License", self._reinstate_selected)
        a.setEnabled(can_reinstate)
        menu.addSeparator()
        a = menu.addAction("Refresh License", self._refresh_selected_licenses)
        a.setEnabled(has_any)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    # -- Trial code actions --

    def _selected_codes(self) -> List[dict]:
        indexes = self.code_table.selectionModel().selectedRows()
        result = []
        for idx in indexes:
            source_idx = self.code_proxy.mapToSource(idx)
            code = self.code_model.get_row(source_idx.row())
            if code:
                result.append(code)
        return result

    def _refresh_codes(self):
        self._show_status("Refreshing trial codes...")
        auth = self._get_auth()
        if not auth:
            return
        pid = self.product_combo.currentData() or ""

        def fetch():
            return self.api.list_trial_codes(auth, product_id=pid)

        def on_done(result):
            if result.get("success"):
                codes = result.get("codes", [])
                self.code_model.set_data(codes)
                self.code_proxy.invalidateFilter()
                if not self._code_col_widths_restored:
                    self.code_table.resizeColumnsToContents()
                    _save_col_widths_for(
                        "codeTable", self.code_table.horizontalHeader()
                    )
                    self._code_col_widths_restored = True
                    if self.snap_tabs_cb.isChecked() and self.tabs.currentIndex() == 1:
                        QTimer.singleShot(0, self._snap_to_current_tab)
                else:
                    self._grow_columns(self.code_table, "codeTable")
                self._update_count()
                self._show_status(f"Loaded {len(codes)} trial code(s)")
            else:
                msg = result.get("error") or "Failed to list trial codes"
                self._show_error(f"{msg} (HTTP {result.get('_status', '?')})")

        self._run_async(fetch, on_done)

    def _create_trial(self):
        if not self.products:
            self._show_error("No products loaded yet. Click Refresh.")
            return
        dlg = CreateTrialCodeDialog(
            self.products, self,
            preselect_product_id=self.product_combo.currentData() or "",
            existing_codes=self.code_model.all_codes(),
        )
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        if not data.get("code"):
            self._show_error("Code is required.")
            return
        if not data.get("productId"):
            self._show_error("A product must be selected.")
            return

        auth = self._get_auth()

        def create():
            return self.api.create_trial_code(auth, **data)

        def on_done(result):
            if result.get("success"):
                code_str = result.get("code", data.get("code", ""))
                self._show_status(f"Trial code created: {code_str}")
                self._refresh_codes()
            else:
                self._show_error(result.get("error", "Creation failed"))

        self._run_async(create, on_done)

    def _view_code_detail(self, *_):
        selected = self._selected_codes()
        if len(selected) != 1:
            return
        TrialCodeDetailDialog(
            selected[0], self,
            privacy_mode=self.privacy_cb.isChecked(),
        ).exec()

    def _edit_selected_code(self, *_):
        selected = self._selected_codes()
        if len(selected) != 1:
            return
        code = selected[0]
        dlg = EditTrialCodeDialog(code, self, privacy_mode=self.privacy_cb.isChecked())
        if dlg.exec() != QDialog.Accepted:
            return
        changes = dlg.get_changes()
        if not changes:
            self._show_status("No changes made.")
            return

        auth = self._get_auth()
        code_str = str(code.get("code", ""))

        def update():
            return self.api.update_trial_code(auth, code_str, **changes)

        def on_done(result):
            if result.get("success"):
                self._show_status(f"Code '{code_str}' updated.")
                self._refresh_codes()
            else:
                self._show_error(result.get("error", "Update failed"))

        self._run_async(update, on_done)

    def _toggle_code_active(self):
        selected = self._selected_codes()
        if not selected:
            return
        auth = self._get_auth()

        def work():
            results = []
            for code in selected:
                new_active = not code.get("active", True)
                r = self.api.update_trial_code(
                    auth, str(code.get("code", "")), active=new_active,
                )
                results.append(r)
            return results

        def on_done(results):
            ok = sum(1 for r in results if r.get("success"))
            self._show_status(f"Toggled {ok}/{len(results)} code(s).")
            self._refresh_codes()

        self._run_async(work, on_done)

    def _delete_selected_code(self):
        selected = self._selected_codes()
        if not selected:
            return
        if not _confirm(
            self, "Confirm Delete",
            f"Permanently delete {len(selected)} trial code(s)?\n\n"
            "This cannot be undone."
        ):
            return

        auth = self._get_auth()

        def work():
            results = []
            for code in selected:
                r = self.api.delete_trial_code(auth, str(code.get("code", "")))
                results.append(r)
            return results

        def on_done(results):
            ok = sum(1 for r in results if r.get("success"))
            self._show_status(f"Deleted {ok}/{len(results)} code(s).")
            self._refresh_codes()

        self._run_async(work, on_done)

    def _copy_code(self):
        selected = self._selected_codes()
        if not selected:
            return
        codes = [str(c.get("code", "")) for c in selected]
        QApplication.clipboard().setText("\n".join(codes))
        self._show_status(f"Copied {len(codes)} code(s) to clipboard.")

    def _show_code_context_menu(self, pos):
        index = self.code_table.indexAt(pos)
        if not index.isValid():
            return
        selected = self._selected_codes()
        has_any = len(selected) > 0
        has_one = len(selected) == 1

        if has_any:
            all_active   = all(c.get("active", True) for c in selected)
            all_disabled = all(not c.get("active", True) for c in selected)
            toggle_label = "Disable" if all_active else ("Enable" if all_disabled else "Enable / Disable")
        else:
            toggle_label = "Enable / Disable"

        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        a = menu.addAction("View Details", self._view_code_detail)
        a.setEnabled(has_one)
        a = menu.addAction("Edit Code", self._edit_selected_code)
        a.setEnabled(has_one)
        menu.addSeparator()
        a = menu.addAction("Copy Code", self._copy_code)
        a.setEnabled(has_any)
        menu.addSeparator()
        a = menu.addAction(toggle_label, self._toggle_code_active)
        a.setEnabled(has_any)
        a = menu.addAction("Delete Code", self._delete_selected_code)
        a.setEnabled(has_any)

        menu.exec(self.code_table.viewport().mapToGlobal(pos))


# =============================================================================
# Entry point
# =============================================================================

class BigArrowProxyStyle(QProxyStyle):
    """Draws spinbox / datetime-edit up-down arrows as larger filled triangles."""

    _UP_ELEMENTS = frozenset({
        QStyle.PrimitiveElement.PE_IndicatorSpinUp,
        QStyle.PrimitiveElement.PE_IndicatorSpinPlus,
        QStyle.PrimitiveElement.PE_IndicatorArrowUp,
    })
    _DOWN_ELEMENTS = frozenset({
        QStyle.PrimitiveElement.PE_IndicatorSpinDown,
        QStyle.PrimitiveElement.PE_IndicatorSpinMinus,
        QStyle.PrimitiveElement.PE_IndicatorArrowDown,
    })

    _BTN_WIDTH = 20

    def subControlRect(self, cc, option, sc, widget=None):
        if cc == QStyle.ComplexControl.CC_SpinBox:
            r = self.proxy().subControlRect(cc, option, sc, widget) if self != self.proxy() \
                else super().subControlRect(cc, option, sc, widget)
            full = option.rect
            bw = self._BTN_WIDTH
            if sc == QStyle.SubControl.SC_SpinBoxUp:
                return QRect(full.right() - bw + 1, full.top(), bw, full.height() // 2)
            if sc == QStyle.SubControl.SC_SpinBoxDown:
                half = full.height() // 2
                return QRect(full.right() - bw + 1, full.top() + half, bw, full.height() - half)
            if sc == QStyle.SubControl.SC_SpinBoxEditField:
                return QRect(full.left(), full.top(), full.width() - bw, full.height())
            return r
        return super().subControlRect(cc, option, sc, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        is_up = element in self._UP_ELEMENTS
        is_down = element in self._DOWN_ELEMENTS
        if is_up or is_down:
            r = option.rect
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(option.palette.buttonText().color())

            # Wide, flat triangles — fixed size so they read consistently
            # regardless of the native button rect's aspect ratio.
            half_w = 6
            half_h = 3
            cx = r.center().x()
            cy = r.center().y()

            # Sunken push-in: nudge the glyph down-right by 1px while pressed.
            sunken = bool(option.state & QStyle.StateFlag.State_Sunken)
            if sunken:
                cx += 1
                cy += 1

            if is_up:
                pts = [
                    QPoint(cx - half_w, cy + half_h),
                    QPoint(cx + half_w, cy + half_h),
                    QPoint(cx,          cy - half_h),
                ]
            else:
                pts = [
                    QPoint(cx - half_w, cy - half_h),
                    QPoint(cx + half_w, cy - half_h),
                    QPoint(cx,          cy + half_h),
                ]
            painter.drawPolygon(QPolygon(pts))
            painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Creator License Manager")
    app.setOrganizationName("CGLounge")

    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(COLORS["bg_window"]))
    palette.setColor(QPalette.WindowText,      QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Base,            QColor(COLORS["bg_surface"]))
    palette.setColor(QPalette.AlternateBase,   QColor(COLORS["bg_table"]))
    palette.setColor(QPalette.ToolTipBase,     QColor(COLORS["bg_raised"]))
    palette.setColor(QPalette.ToolTipText,     QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Text,            QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Button,          QColor(COLORS["bg_raised"]))
    palette.setColor(QPalette.ButtonText,      QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Highlight,       QColor(COLORS["accent_dark"]))
    palette.setColor(QPalette.HighlightedText, QColor(COLORS["text_white"]))
    app.setPalette(palette)

    window = LicenseManager()
    window.show()
    sys.exit(app.exec())


_DARK_STYLE_TEMPLATE = Template("""
QMainWindow, QDialog {
    background-color: $bg_window;
}
QWidget {
    color: $text_primary;
    font-size: 13px;
}
QPushButton {
    background-color: $bg_raised;
    color: $text_primary;
    border: 1px solid $border_inset;
    border-radius: 4px;
    padding: 6px 16px;
    min-height: 28px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: $bg_btn_hover;
    border-color: $accent;
}
QPushButton:pressed {
    background-color: $bg_btn_pressed;
}
QPushButton:disabled {
    background-color: $bg_btn_disabled;
    color: $text_disabled;
    border-color: $border_subtle;
}
QPushButton::menu-indicator {
    subcontrol-origin: padding;
    subcontrol-position: right center;
    right: 6px;
    width: 10px;
    height: 10px;
}
QPushButton[cssClass="danger"] {
    background-color: $danger_bg;
    border-color: $danger_border;
}
QPushButton[cssClass="danger"]:hover {
    background-color: $danger_hover_bg;
    border-color: $danger_hover_border;
}
QPushButton[cssClass="danger"]:disabled {
    background-color: $danger_disabled_bg;
    border-color: $danger_disabled_border;
    color: $danger_disabled_text;
}
QPushButton[cssClass="warning"] {
    background-color: $warn_bg;
    border-color: $warn_border;
}
QPushButton[cssClass="warning"]:hover {
    background-color: $warn_hover_bg;
    border-color: $warn_hover_border;
}
QPushButton[cssClass="warning"]:disabled {
    background-color: $warn_disabled_bg;
    border-color: $warn_disabled_border;
    color: $warn_disabled_text;
}
QPushButton[cssClass="info"] {
    background-color: $info_bg;
    border-color: $info_border;
}
QPushButton[cssClass="info"]:hover {
    background-color: $info_hover_bg;
    border-color: $info_hover_border;
}
QPushButton[cssClass="info"]:disabled {
    background-color: $info_disabled_bg;
    border-color: $info_disabled_border;
    color: $info_disabled_text;
}
QPushButton[cssClass="success"] {
    background-color: $success_bg;
    border-color: $success_border;
}
QPushButton[cssClass="success"]:hover {
    background-color: $success_hover_bg;
    border-color: $success_hover_border;
}
QPushButton[cssClass="success"]:disabled {
    background-color: $success_disabled_bg;
    border-color: $success_disabled_border;
    color: $success_disabled_text;
}
QComboBox {
    background-color: $bg_surface;
    border: 1px solid $border;
    border-radius: 4px;
    padding: 5px 10px;
    min-height: 26px;
}
QComboBox:hover {
    border-color: $accent_hover;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox:disabled {
    background-color: $bg_input_disabled;
    border-color: $border_disabled;
    color: $text_disabled;
}
QComboBox QAbstractItemView {
    background-color: $bg_surface;
    selection-background-color: $accent_dark;
    border: 1px solid $border;
}
QLineEdit {
    background-color: $bg_surface;
    border: 1px solid $border;
    border-radius: 4px;
    padding: 5px 10px;
    min-height: 26px;
}
QLineEdit:focus {
    border-color: $accent;
}
QLineEdit:read-only {
    background-color: $bg_input_disabled;
    border-color: $border_disabled;
    color: $text_disabled;
}
QCheckBox {
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid $border_inset;
    border-radius: 3px;
    background-color: $bg_surface;
}
QCheckBox::indicator:checked {
    background-color: $accent;
    border-color: $accent;
}
QGroupBox {
    border: 1px solid $border;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: $text_group_title;
}
QTabWidget::pane {
    border: 1px solid $border;
}
QTabBar::tab {
    background-color: $bg_surface;
    border: 1px solid $border;
    padding: 6px 16px;
    margin-right: 2px;
    color: $text_muted;
}
QTabBar::tab:selected {
    background-color: $bg_raised;
    color: $text_primary;
    border-bottom-color: $accent;
}
QTabBar::tab:hover:!selected {
    background-color: $bg_tab_hover;
    color: $text_tab_hover;
}
QStatusBar {
    background-color: $bg_window;
    color: $text_muted;
    border-top: 1px solid $border;
}
QStatusBar::item {
    border: none;
}
QFrame[frameShape="6"] {
    border: 1px solid $border;
    border-radius: 4px;
    padding: 8px;
    margin: 4px 0;
}
QSpinBox, QDateTimeEdit {
    background-color: $bg_surface;
    border: 1px solid $border;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 26px;
}
QSpinBox:focus, QDateTimeEdit:focus {
    border-color: $accent;
}
QSpinBox:disabled, QDateTimeEdit:disabled {
    background-color: $bg_input_disabled;
    border-color: $border_disabled;
    color: $text_disabled;
}
QScrollBar:vertical {
    background-color: $bg_scrollbar;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: $border_inset;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: $accent_hover;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QCalendarWidget {
    background-color: $bg_surface;
    min-width: 320px;
    min-height: 260px;
}
QCalendarWidget QWidget {
    font-size: 11px;
}
QCalendarWidget QAbstractItemView {
    background-color: $bg_surface;
    selection-background-color: $accent_dark;
    selection-color: $text_white;
    font-size: 11px;
    gridline-color: $border_subtle;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: $bg_header;
    min-height: 32px;
    font-size: 11px;
}
QCalendarWidget QToolButton {
    color: $text_primary;
    background-color: $bg_header;
    font-size: 11px;
    padding: 4px 8px;
    min-width: 28px;
    border: none;
}
QCalendarWidget QToolButton::menu-indicator {
    image: none;
    width: 0;
}
QCalendarWidget QSpinBox {
    font-size: 11px;
    min-height: 22px;
    padding: 2px 4px;
    max-width: 70px;
}
QCalendarWidget QMenu {
    background-color: $bg_surface;
    font-size: 11px;
}
""")

_CONTEXT_MENU_STYLE_TEMPLATE = Template("""
QMenu {
    background-color: $bg_surface;
    border: 1px solid $border;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    color: $text_primary;
}
QMenu::item:selected {
    background-color: $accent_dark;
    color: $text_white;
}
QMenu::item:disabled {
    color: $text_menu_disabled;
}
QMenu::separator {
    height: 1px;
    background: $border;
    margin: 4px 8px;
}
""")

DARK_STYLE = _DARK_STYLE_TEMPLATE.substitute(COLORS)
CONTEXT_MENU_STYLE = _CONTEXT_MENU_STYLE_TEMPLATE.substitute(COLORS)


if __name__ == "__main__":
    main()
