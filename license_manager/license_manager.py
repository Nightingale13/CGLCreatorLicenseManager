"""
Creator License Manager v1.0.0 — Desktop admin tool for CG Lounge License Server.
Requires: PySide6, Python 3.9+
Config:   config.json in the same directory as this script.

"""

VERSION = "1.0.0"

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    QThread, Signal, Qt, QTimer, QSortFilterProxyModel,
    QAbstractTableModel, QModelIndex, QUrl, QSize, QSettings,
)
from PySide6.QtGui import (
    QColor, QFont, QPalette, QPainter, QPen, QPixmap, QKeySequence, QShortcut,
    QIcon, QDesktopServices,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QPushButton, QComboBox, QCheckBox, QLabel,
    QLineEdit, QDialog, QFormLayout, QDialogButtonBox, QMessageBox,
    QHeaderView, QSpinBox, QDateTimeEdit, QGroupBox,
    QMenu, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QAbstractItemView,
    QTabWidget, QFrame, QProgressBar, QScrollArea,
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
        pen = QPen(QColor("#ffffff"), pen_width, Qt.PenStyle.SolidLine,
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


def _make_machines_spinbox(*, value: int = 2) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(-1, 9999)
    spin.setValue(value)
    spin.setSpecialValueText("Unlimited (-1)")
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
        return self._send(req, timeout)

    def _get(self, endpoint: str, params: dict = None, timeout: int = 15) -> dict:
        items = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        url = f"{self.server_url}/{endpoint}{'?' + items if items else ''}"
        api_key = (params or {}).get("apiKey", "")
        headers = {"x-api-key": api_key} if api_key else {}
        req = urllib.request.Request(url, headers=headers, method="GET")
        return self._send(req, timeout)

    def _send(self, req, timeout: int) -> dict:
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

    def reset_activations(self, auth: dict, license_key: str) -> dict:
        return self._post("resetActivations", {**auth, "licenseKey": license_key})


# =============================================================================
# Background Worker
# =============================================================================

class Worker(QThread):
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
    """QComboBox that fetches variants from the API and populates itself."""
    variant_selected = Signal(dict)  # emits full variant dict on selection change

    def __init__(self, parent=None):
        super().__init__(parent)
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
    ("status",       "Status"),
    ("key",          "License Key"),
    ("email",        "Email"),
    ("variant",      "Tier"),
    ("licenseType",  "Type"),
    ("_saleDate",    "Sale Date"),
    ("_expiresIn",   "Expires In"),
    ("_activations", "Activations"),
    ("_refunded",    "Refunded"),
    ("_disabled",    "Disabled"),
    ("_expired",     "Expired"),
    ("threatLevel",  "Threat lvl"),
    ("_productName", "Product"),
]


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
    used = len(activations) if activations is not None else lic.get("machinesUsed", 0)
    lic["_activations"] = f"{used}/{max_m}"

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

    return lic


class LicenseTableModel(QAbstractTableModel):
    def __init__(self, products: dict = None, parent=None):
        super().__init__(parent)
        self._data: List[dict] = []
        self._columns = LICENSE_COLUMNS
        self._privacy_mode: bool = False
        # Build productId → product name lookup from config
        self._product_names: dict = {}
        if products:
            for name, info in products.items():
                pid = info.get("productId")
                if pid:
                    self._product_names[pid] = name

    def set_privacy_mode(self, enabled: bool):
        self._privacy_mode = enabled

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
        lic = self._data[index.row()]
        col_key = self._columns[index.column()][0]
        val = lic.get(col_key, "")

        if role == Qt.DisplayRole:
            if col_key == "status":
                return ""
            if col_key == "key":
                k = str(val)
                return f"{k[:6]}...{k[-4:]}" if len(k) > 12 else k
            if col_key == "threatLevel":
                tl = val if val is not None else 0
                return str(tl)
            return str(val) if val is not None else ""

        if role == Qt.ToolTipRole:
            if col_key == "key":
                return None if self._privacy_mode else str(val)
            if col_key == "threatLevel":
                tl = int(val) if val else 0
                return {
                    0: "Level 0 — Clean: No violations. Normal operation.",
                    1: "Level 1 — Warning: Minor suspicious activity detected. License still active, warning logged internally.",
                    2: "Level 2 — Degraded: Significant violations detected. Nag message shown to user; still functional but token refreshes every 24 hours.",
                    3: "Level 3 — Suspended: Serious abuse detected. User sees warning; access blocked after 72 hours unless resolved.",
                    4: "Level 4 — Revoked: Chargeback or confirmed fraud. License immediately blocked.",
                }.get(tl, f"Level {tl} — Unknown threat level.")
            return None

        if role == Qt.UserRole:
            return lic

        if role == Qt.ForegroundRole:
            if col_key == "threatLevel":
                tl = int(val) if val is not None else 0
                return {
                    0: QColor("#4ade80"),  # green
                    1: QColor("#facc15"),  # yellow
                    2: QColor("#fb923c"),  # yellow-orange
                    3: QColor("#f97316"),  # orange
                    4: QColor("#ef4444"),  # red
                }.get(tl, QColor("#ffffff"))
            if col_key == "_disabled" and val == "Yes":
                return QColor("#ff6b6b")
            if col_key == "_refunded" and val == "Yes":
                return QColor("#ffa94d")
            if col_key == "_expired" and val == "Yes":
                return QColor("#ff6b6b")

        if role == Qt.FontRole:
            if col_key == "threatLevel":
                font = QFont()
                font.setBold(True)
                return font

        if role == Qt.TextAlignmentRole:
            if col_key in ("_activations", "threatLevel", "_refunded",
                           "_disabled", "_expired", "status"):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

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
            QTimer.singleShot(0, self.viewport().update)


# =============================================================================
# Status Delegate
# =============================================================================

class StatusDelegate(QStyledItemDelegate):
    STATUS_COLORS = {
        "active": "#51cf66",
        "degraded": "#ffa94d",
        "suspended": "#ff922b",
        "revoked": "#ff6b6b",
        "expired": "#868e96",
    }

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
        color = QColor(self.STATUS_COLORS.get(status, "#868e96"))

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
    "key", "email", "productId", "purchaseId", "bundleId", "discountCode",
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
        if not self._privacy or index.column() not in _PRIVACY_SENSITIVE_COLS:
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

    def set_filters(self, hide_trials=None, hide_disabled=None,
                    hide_expired=None, product_filter=None,
                    search_text=None):
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
            "It is pulled directly from the product's variant configuration."
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
        # Reset max machines to the variant's default for each selection
        default_max = variant.get("maxMachines")
        if default_max is None:
            default_max = -1 if is_site else (1 if license_type == "per-machine" else 5)
        self.machines_spin.setValue(default_max)
        self.machines_label.setText("Machines Unlimited:" if is_site else "Max Machines:")

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
        product_label = PixelatedLabel(lic.get("productId", "")) if privacy_mode else QLabel(lic.get("productId", ""))
        info_layout.addRow("Product:", product_label)
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
            "It is pulled directly from the product's variant configuration."
        )
        form.addRow("License Type:", self.type_label)

        is_site = (lic.get("licenseType") or "").lower() == "site"
        self.machines_spin = _make_machines_spinbox(value=lic.get("maxMachines", 2))
        self.machines_spin.setEnabled(not is_site)
        form.addRow("Max Machines:", self.machines_spin)

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

        _make_dialog_buttons(layout, accept=self.accept, reject=self.reject)

        pid = lic.get("productId", "")
        self.variant_combo.load(api, auth, pid, lic.get("variant", ""))

    def _on_variant_selected(self, variant: dict):
        license_type = variant.get("licenseType", "per-machine")
        self.type_label.setText(license_type)
        is_site = license_type == "site"
        self.machines_spin.setEnabled(not is_site)

        # If the user returned to the license's original variant, restore the
        # license's original maxMachines. Otherwise, use this variant's default.
        original_variant = self.variant_combo._strip_prefix(self.lic.get("variant", "") or "")
        selected_variant = self.variant_combo.currentData() or ""
        if selected_variant == original_variant:
            self.machines_spin.setValue(self.lic.get("maxMachines", 2))
        else:
            default_max = variant.get("maxMachines")
            if default_max is None:
                default_max = -1 if is_site else (1 if license_type == "per-machine" else 5)
            self.machines_spin.setValue(default_max)

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
            new_exp = self.expires_edit.dateTime().toUTC().toString(Qt.ISODate)
            changes["expiresAt"] = new_exp
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
                      "discountCode", "purchaseId", "bundleId",
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
                    frame.setStyleSheet("QFrame { background: #1a1730; color: #5a5580; }")
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
            frame.setStyleSheet("QFrame { background: #3b2d72; border: 1px solid #7c3aed; }")
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
# Main Window
# =============================================================================

DARK_STYLE = """
QMainWindow, QDialog {
    background-color: #110e22;
}
QWidget {
    color: #f0eeff;
    font-size: 13px;
}
QTableView {
    background-color: #131020;
    alternate-background-color: #0f0d1c;
    gridline-color: #231f38;
    border: 1px solid #2b2640;
    selection-background-color: #3b2d72;
    selection-color: #ffffff;
}
QTableView::item {
    padding: 4px 8px;
}
QTableView::item:selected {
    background-color: #3b2d72;
    color: #ffffff;
}
QTableView::item:focus:!selected {
    background-color: transparent;
    border: none;
}
QHeaderView::section {
    background-color: #201c34;
    color: #d8d4f5;
    border: none;
    border-right: 1px solid #2b2640;
    border-bottom: 1px solid #2b2640;
    padding: 6px 8px;
    font-weight: bold;
}
QPushButton {
    background-color: #252040;
    color: #f0eeff;
    border: 1px solid #3d2d60;
    border-radius: 4px;
    padding: 6px 16px;
    min-height: 28px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #322d55;
    border-color: #7c3aed;
}
QPushButton:pressed {
    background-color: #1a1535;
}
QPushButton:disabled {
    background-color: #1a1730;
    color: #5a5580;
    border-color: #231f38;
}
QPushButton[cssClass="danger"] {
    background-color: #8b2020;
    border-color: #a52a2a;
}
QPushButton[cssClass="danger"]:hover {
    background-color: #a52a2a;
    border-color: #c53030;
}
QPushButton[cssClass="danger"]:disabled {
    background-color: #4a2020;
    border-color: #5a2a2a;
    color: #7a5555;
}
QPushButton[cssClass="warning"] {
    background-color: #7a4510;
    border-color: #995a18;
}
QPushButton[cssClass="warning"]:hover {
    background-color: #995a18;
    border-color: #b87020;
}
QPushButton[cssClass="warning"]:disabled {
    background-color: #3d2808;
    border-color: #5a3a10;
    color: #7a6040;
}
QPushButton[cssClass="info"] {
    background-color: #1a4a8a;
    border-color: #2460aa;
}
QPushButton[cssClass="info"]:hover {
    background-color: #2460aa;
    border-color: #3478cc;
}
QPushButton[cssClass="info"]:disabled {
    background-color: #0f2a50;
    border-color: #1a3a6a;
    color: #405570;
}
QPushButton[cssClass="success"] {
    background-color: #2d6b3f;
    border-color: #3a8a50;
}
QPushButton[cssClass="success"]:hover {
    background-color: #3a8a50;
    border-color: #4aaa60;
}
QPushButton[cssClass="success"]:disabled {
    background-color: #1d3b2f;
    border-color: #2a4a3a;
    color: #506855;
}
QComboBox {
    background-color: #1c1830;
    border: 1px solid #2b2640;
    border-radius: 4px;
    padding: 5px 10px;
    min-height: 26px;
}
QComboBox:hover {
    border-color: #6d28d9;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox:disabled {
    background-color: #141020;
    border-color: #1e1a30;
    color: #5a5580;
}
QComboBox QAbstractItemView {
    background-color: #1c1830;
    selection-background-color: #3b2d72;
    border: 1px solid #2b2640;
}
QLineEdit {
    background-color: #1c1830;
    border: 1px solid #2b2640;
    border-radius: 4px;
    padding: 5px 10px;
    min-height: 26px;
}
QLineEdit:focus {
    border-color: #7c3aed;
}
QLineEdit:read-only {
    background-color: #141020;
    border-color: #1e1a30;
    color: #5a5580;
}
QCheckBox {
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3d2d60;
    border-radius: 3px;
    background-color: #1c1830;
}
QCheckBox::indicator:checked {
    background-color: #7c3aed;
    border-color: #7c3aed;
}
QGroupBox {
    border: 1px solid #2b2640;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #9d8ae0;
}
QTabWidget::pane {
    border: 1px solid #2b2640;
}
QTabBar::tab {
    background-color: #1c1830;
    border: 1px solid #2b2640;
    padding: 6px 16px;
    margin-right: 2px;
    color: #9490b8;
}
QTabBar::tab:selected {
    background-color: #252040;
    color: #f0eeff;
    border-bottom-color: #7c3aed;
}
QTabBar::tab:hover:!selected {
    background-color: #1a1628;
    color: #c5c0e0;
}
QStatusBar {
    background-color: #110e22;
    color: #9490b8;
    border-top: 1px solid #2b2640;
}
QStatusBar::item {
    border: none;
}
QFrame[frameShape="6"] {
    border: 1px solid #2b2640;
    border-radius: 4px;
    padding: 8px;
    margin: 4px 0;
}
QSpinBox, QDateTimeEdit {
    background-color: #1c1830;
    border: 1px solid #2b2640;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 26px;
}
QSpinBox:focus, QDateTimeEdit:focus {
    border-color: #7c3aed;
}
QSpinBox:disabled, QDateTimeEdit:disabled {
    background-color: #141020;
    border-color: #1e1a30;
    color: #5a5580;
}
QScrollBar:vertical {
    background-color: #0d0b18;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: #3d2d60;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #6d28d9;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
/* --- Calendar popup: force usable cell sizing --- */
QCalendarWidget {
    background-color: #1c1830;
    min-width: 320px;
    min-height: 260px;
}
QCalendarWidget QWidget {
    font-size: 11px;
}
QCalendarWidget QAbstractItemView {
    background-color: #1c1830;
    selection-background-color: #3b2d72;
    selection-color: #ffffff;
    font-size: 11px;
    gridline-color: #231f38;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #201c34;
    min-height: 32px;
    font-size: 11px;
}
QCalendarWidget QToolButton {
    color: #f0eeff;
    background-color: #201c34;
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
    background-color: #1c1830;
    font-size: 11px;
}
"""

CONTEXT_MENU_STYLE = """
QMenu {
    background-color: #1c1830;
    border: 1px solid #2b2640;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    color: #f0eeff;
}
QMenu::item:selected {
    background-color: #3b2d72;
    color: #ffffff;
}
QMenu::item:disabled {
    color: #4a4570;
}
QMenu::separator {
    height: 1px;
    background: #2b2640;
    margin: 4px 8px;
}
"""


class LicenseManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"CGLounge Creator License Manager   v{VERSION}")
        self.setMinimumSize(1200, 700)
        self.resize(1600, 800)

        _icon_path = Path(__file__).parent / "icon.png"
        if _icon_path.exists():
            self.setWindowIcon(QIcon(str(_icon_path)))

        self.config = self._load_config()
        self.server_url = self.config.get(
            "serverUrl",
            "https://us-central1-cg-license-server.cloudfunctions.net",
        )
        self.api_key = self.config.get("apiKey", "")
        self.products = self.config.get("products", {})
        self.api = APIClient(self.server_url)
        self._workers: list = []
        self._active_workers: int = 0

        self._setup_ui()
        self._apply_style()
        self._update_button_states()

        self._activation_timer = QTimer(self)
        self._activation_timer.setInterval(60_000)
        self._activation_timer.timeout.connect(self._refresh_activation_counts)
        self._activation_timer.start()

        # Countdown label pinned to the right of the status bar
        self._countdown_lbl = QLabel()
        self._countdown_lbl.setStyleSheet("color: #6b7280; font-size: 11px; padding: 0 8px 0 0;")
        self._countdown_lbl.setFixedWidth(260)
        self._countdown_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.statusBar().addPermanentWidget(self._countdown_lbl)

        self._countdown_tick = QTimer(self)
        self._countdown_tick.setInterval(1000)
        self._countdown_tick.setTimerType(Qt.TimerType.CoarseTimer)
        self._countdown_tick.timeout.connect(self._update_countdown)
        self._countdown_tick.start()
        self._update_countdown()

        if self.products:
            QTimer.singleShot(200, self._refresh_licenses)

    def _load_config(self) -> dict:
        for loc in [Path(__file__).parent / "config.json",
                    Path("config.json")]:
            if loc.exists():
                try:
                    return json.loads(loc.read_text())
                except Exception as e:
                    print(f"Warning: Failed to load {loc}: {e}")
        return {}

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

        # ---- Top toolbar ----
        toolbar = QHBoxLayout()

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
        self.search_edit.setPlaceholderText("Search license, email, tier...")
        self.search_edit.setMinimumWidth(240)
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_edit)

        toolbar.addSpacing(20)

        settings = QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope,
            "CGLounge", "Creator License Manager",
        )
        self.hide_trials_cb = _make_settings_checkbox("Hide Trials", "filter/hideTrials", self._on_filter_changed, settings)
        toolbar.addWidget(self.hide_trials_cb)

        self.hide_disabled_cb = _make_settings_checkbox("Hide Disabled", "filter/hideDisabled", self._on_filter_changed, settings)
        toolbar.addWidget(self.hide_disabled_cb)

        self.hide_expired_cb = _make_settings_checkbox("Hide Expired", "filter/hideExpired", self._on_filter_changed, settings)
        toolbar.addWidget(self.hide_expired_cb)

        toolbar.addStretch()

        self.privacy_cb = _make_settings_checkbox("Privacy Mode", "filter/privacyMode", self._toggle_privacy_mode, settings)
        toolbar.addWidget(self.privacy_cb)

        toolbar.addSpacing(16)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #9490b8;")
        toolbar.addWidget(self.count_label)

        toolbar.addSpacing(12)

        self.help_btn = QPushButton()
        self.help_btn.setIcon(self._make_help_icon(18))
        self.help_btn.setIconSize(QSize(18, 18))
        self.help_btn.setFixedWidth(32)
        self.help_btn.setToolTip("Open documentation")
        self.help_btn.clicked.connect(self._open_help)
        toolbar.addWidget(self.help_btn)

        main_layout.addLayout(toolbar)

        # ---- Table ----
        self.model = LicenseTableModel(self.products)
        self.proxy = LicenseFilterProxy()
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(True)

        self.table = LicenseTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._save_sort_order)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.table.setItemDelegateForColumn(0, StatusDelegate(self.table))
        self._privacy_delegate = PrivacyDelegate(self.table)
        for col_idx in _PRIVACY_SENSITIVE_COLS:
            self.table.setItemDelegateForColumn(col_idx, self._privacy_delegate)
        # Apply persisted privacy state now that the delegate exists
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

        main_layout.addWidget(self.table, 1)

        # ---- Busy progress bar (full-width, shown during async ops) ----
        self._busy_bar = QProgressBar()
        self._busy_bar.setRange(0, 0)  # indeterminate
        self._busy_bar.setFixedHeight(6)
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setStyleSheet(
            "QProgressBar { border: none; background: transparent; }"
            "QProgressBar::chunk { background: #7c3aed; border-radius: 3px; }"
        )
        self._busy_bar.hide()
        main_layout.addWidget(self._busy_bar)

        # ---- Bottom action bar ----
        action_bar = QHBoxLayout()

        self.refresh_btn = _make_action_button("Refresh", self._refresh_licenses, action_bar)
        self.create_btn = _make_action_button("+ Create License", self._create_license, action_bar, css_class="success")
        self.edit_btn = _make_action_button("Edit Selected", self._edit_selected, action_bar)
        self.detail_btn = _make_action_button("View Details", self._view_detail, action_bar)

        action_bar.addSpacing(20)

        self.revoke_btn = _make_action_button("Revoke License", self._revoke_selected, action_bar, css_class="danger")
        self.suspend_btn = _make_action_button("Suspend License", self._suspend_selected, action_bar, css_class="warning")
        self.reinstate_btn = _make_action_button("Reinstate License", self._reinstate_selected, action_bar, css_class="success")
        self.reset_activations_btn = _make_action_button("Reset Activations", self._reset_activations, action_bar, css_class="info")

        action_bar.addStretch()

        self.copy_key_btn = _make_action_button("Copy Key", self._copy_key, action_bar)

        main_layout.addLayout(action_bar)

        self.statusBar().showMessage("Ready")

        # Restore persisted sort order (default: threat level ascending)
        _threat_col = next(i for i, (k, _) in enumerate(LICENSE_COLUMNS) if k == "threatLevel")
        _sort_col = settings.value("table/sortColumn", _threat_col, type=int)
        _sort_order = Qt.SortOrder(settings.value("table/sortOrder", 0, type=int))
        self.table.sortByColumn(_sort_col, _sort_order)

        # Keyboard shortcuts
        QShortcut(QKeySequence("F5"), self, self._refresh_licenses)
        new_license_key = "Meta+N" if sys.platform == "darwin" else "Ctrl+N"
        QShortcut(QKeySequence(new_license_key), self, self._create_license)

    def _apply_style(self):
        self.setStyleSheet(DARK_STYLE)

    # -- Button state management --
    def _update_button_states(self):
        selected = self.table.selectionModel().selectedRows()
        has_any = len(selected) > 0
        has_one = len(selected) == 1

        self.edit_btn.setEnabled(has_one)
        self.detail_btn.setEnabled(has_one)
        self.revoke_btn.setEnabled(has_any)
        self.suspend_btn.setEnabled(has_any)
        self.reinstate_btn.setEnabled(has_any)
        self.reset_activations_btn.setEnabled(has_any)
        self.copy_key_btn.setEnabled(has_any)

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

    def _save_sort_order(self, logical_index: int, order):
        s = QSettings(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope,
            "CGLounge", "Creator License Manager",
        )
        s.setValue("table/sortColumn", logical_index)
        s.setValue("table/sortOrder", order.value)

    def _open_help(self):
        QDesktopServices.openUrl(QUrl("https://github.com/Nightingale13/CGLCreatorLicenseManager"))

    def _make_help_icon(self, size: int = 20) -> QIcon:
        px = QPixmap(size, size)
        px.fill(Qt.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#7c3aed"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(int(size * 0.65))
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(px.rect(), Qt.AlignCenter, "?")
        painter.end()
        return QIcon(px)

    def _update_countdown(self):
        remaining = max(0, self._activation_timer.remainingTime() // 1000)
        text = f"Activation count refresh: ↻ {remaining}s"
        if self._countdown_lbl.text() != text:
            self._countdown_lbl.setText(text)

    def _refresh_activation_counts(self):
        keys = [lic["key"] for lic in self.model.all_licenses() if lic.get("key")]
        self._fetch_activation_counts(keys)

    def _fetch_activation_counts(self, keys: list):
        """Silently fetch getLicense for each key at 50ms intervals to populate activation counts."""
        if not keys:
            return
        self._activation_timer.start()  # reset the 60s countdown whenever activations are fetched
        auth = self._get_auth()

        def fetch_next(idx: int):
            if idx >= len(keys):
                return
            key = keys[idx]

            def fetch():
                return self.api.get_license(auth, key)

            def on_result(result):
                if result.get("success"):
                    activations = result.get("activations", [])
                    self.model.update_activation_count(key, len(activations))
                QTimer.singleShot(50, lambda: fetch_next(idx + 1))

            w = Worker(fetch)
            w.finished.connect(on_result)
            w.error.connect(lambda _: QTimer.singleShot(50, lambda: fetch_next(idx + 1)))
            self._workers.append(w)
            w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
            w.error.connect(lambda _: self._workers.remove(w) if w in self._workers else None)
            w.start()

        fetch_next(0)

    def _show_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}", 8000)
        QMessageBox.warning(self, "Error", msg)

    def _show_status(self, msg: str, timeout: int = 5000):
        self.statusBar().showMessage(msg, timeout)

    # -- Filters --
    def _on_filter_changed(self):
        pid = self.product_combo.currentData() or ""
        self.proxy.set_filters(
            hide_trials=self.hide_trials_cb.isChecked(),
            hide_disabled=self.hide_disabled_cb.isChecked(),
            hide_expired=self.hide_expired_cb.isChecked(),
            product_filter=pid,
        )
        self._update_count()

    def _on_search_changed(self, text):
        self.proxy.set_filters(search_text=text)
        self._update_count()

    def _update_count(self):
        total = self.model.rowCount()
        visible = self.proxy.rowCount()
        self.count_label.setText(f"Showing {visible} of {total} licenses")

    # -- Actions --
    def _refresh_licenses(self):
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
            self._update_count()
            self.refresh_btn.setEnabled(True)
            self._update_button_states()
            self._show_status(f"Loaded {len(licenses)} licenses")
            keys = [lic["key"] for lic in licenses if lic.get("key")]
            self._fetch_activation_counts(keys)

        def on_err(msg):
            self.refresh_btn.setEnabled(True)
            self._show_error(msg)

        self._run_async(fetch, on_done, on_err)

    def _create_license(self):
        if not self.products:
            self._show_error("No products configured. Edit config.json.")
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
            print(f"[updateLicense] payload changes: {json.dumps(changes, indent=2)}")
            result = self.api.update_license(auth, license_key, **changes)
            print(f"[updateLicense] response: {json.dumps(result, indent=2)}")
            return result

        def on_done(result):
            if result.get("success"):
                self._show_status("License updated.")
                self._refresh_licenses()
            else:
                status = result.get("_status", "?")
                msg = result.get("error") or result.get("message") or str(result)
                self._show_error(f"Update failed (HTTP {status}): {msg}")

        self._run_async(update, on_done)

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
                activations = result.get("activations", [])
                self.model.update_activation_count(lic["key"], len(activations))
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
            self._refresh_licenses()

        self._run_async(do_reset, on_done)

    def _revoke_selected(self):
        selected = self._selected_licenses()
        if not selected:
            return

        count = len(selected)
        if not _confirm(self, "Confirm Revoke",
                        f"Revoke {count} license(s)?\n\n"
                        "This will immediately prevent activation and validation."):
            return

        self._bulk_license_action(selected, self.api.revoke_license, "Revoked")

    def _suspend_selected(self):
        selected = self._selected_licenses()
        if not selected:
            return

        count = len(selected)
        if not _confirm(self, "Confirm Suspend",
                        f"Suspend {count} license(s)?\n\n"
                        "The license(s) will be marked as suspended and cannot be used until reinstated."):
            return

        self._bulk_license_action(selected, self.api.suspend_license, "Suspended")

    def _reinstate_selected(self):
        selected = self._selected_licenses()
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
        a = menu.addAction("Revoke License", self._revoke_selected)
        a.setEnabled(has_any)
        a = menu.addAction("Suspend License", self._suspend_selected)
        a.setEnabled(has_any)
        a = menu.addAction("Reinstate License", self._reinstate_selected)
        a.setEnabled(has_any)

        menu.exec(self.table.viewport().mapToGlobal(pos))


# =============================================================================
# Entry point
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Creator License Manager")
    app.setOrganizationName("CGLounge")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#110e22"))
    palette.setColor(QPalette.WindowText, QColor("#f0eeff"))
    palette.setColor(QPalette.Base, QColor("#1c1830"))
    palette.setColor(QPalette.AlternateBase, QColor("#131020"))
    palette.setColor(QPalette.ToolTipBase, QColor("#252040"))
    palette.setColor(QPalette.ToolTipText, QColor("#f0eeff"))
    palette.setColor(QPalette.Text, QColor("#f0eeff"))
    palette.setColor(QPalette.Button, QColor("#252040"))
    palette.setColor(QPalette.ButtonText, QColor("#f0eeff"))
    palette.setColor(QPalette.Highlight, QColor("#3b2d72"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = LicenseManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
