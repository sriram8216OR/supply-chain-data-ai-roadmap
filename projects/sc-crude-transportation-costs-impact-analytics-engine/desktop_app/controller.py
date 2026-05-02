"""
Controller — single service object that the UI talks to.

Wraps the engine layer (loader, network, shock) and exposes:
  - Loaded NetworkData and NetworkDiagnostic (computed once at startup)
  - Current shock value (delta_brent_usd_per_bbl)
  - Cached ShockResult (recomputed when shock changes, debounced)
  - Signal: shock_changed — emitted when shock value changes (after debounce)

The UI subscribes to shock_changed and refreshes anything that depends on
the shock value. Vulnerability views ignore this signal entirely.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from engine.loader import NetworkData, load_network, BASELINE_BRENT_USD_PER_BBL
from engine.network import NetworkDiagnostic, compute_diagnostic
from engine.shock import ShockResult, compute_shock


# Debounce delay for shock recomputation (ms) — see threading discussion in
# build plan. 250ms feels snappy without recomputing while user drags slider.
SHOCK_DEBOUNCE_MS = 250

# Default shock on startup
DEFAULT_DELTA_BRENT = 15.0


class AppController(QObject):
    """Single application controller; instance is shared across UI."""

    # Emitted when shock value has changed AND the debounce timer has fired.
    # ShockResult is the recomputed result.
    shock_changed = pyqtSignal(object)  # ShockResult

    # Emitted immediately when shock value changes (before debounce). UI can
    # use this to update the display of the slider value or "computing..." indicator.
    shock_value_changed = pyqtSignal(float)  # delta_brent

    def __init__(self, data_dir: Path):
        super().__init__()
        self._data_dir = data_dir
        self._network: Optional[NetworkData] = None
        self._diagnostic: Optional[NetworkDiagnostic] = None
        self._shock_result: Optional[ShockResult] = None
        self._delta_brent: float = DEFAULT_DELTA_BRENT

        # Debounce timer
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(SHOCK_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._recompute_shock_now)

    # -------------------------------------------------------------------
    # Initial load
    # -------------------------------------------------------------------

    def load(self) -> None:
        """Load the network and compute the standing diagnostic. Call once at startup."""
        self._network = load_network(self._data_dir)
        self._diagnostic = compute_diagnostic(self._network)
        # Compute the initial shock result
        self._shock_result = compute_shock(self._network, self._diagnostic, self._delta_brent)

    # -------------------------------------------------------------------
    # Read-only accessors
    # -------------------------------------------------------------------

    @property
    def network(self) -> NetworkData:
        if self._network is None:
            raise RuntimeError("Controller not loaded — call load() first")
        return self._network

    @property
    def diagnostic(self) -> NetworkDiagnostic:
        if self._diagnostic is None:
            raise RuntimeError("Controller not loaded — call load() first")
        return self._diagnostic

    @property
    def shock_result(self) -> ShockResult:
        if self._shock_result is None:
            raise RuntimeError("Controller not loaded — call load() first")
        return self._shock_result

    @property
    def delta_brent(self) -> float:
        return self._delta_brent

    @property
    def baseline_brent(self) -> float:
        return BASELINE_BRENT_USD_PER_BBL

    # -------------------------------------------------------------------
    # Shock control
    # -------------------------------------------------------------------

    def set_delta_brent(self, value: float) -> None:
        """Set the shock value. Emits shock_value_changed immediately and
        triggers a debounced recompute that will emit shock_changed."""
        if value == self._delta_brent:
            return
        self._delta_brent = value
        self.shock_value_changed.emit(value)
        # Restart the debounce timer
        self._debounce_timer.start()

    def _recompute_shock_now(self) -> None:
        """Called by the debounce timer. Performs the actual shock recomputation."""
        assert self._network is not None and self._diagnostic is not None
        self._shock_result = compute_shock(self._network, self._diagnostic, self._delta_brent)
        self.shock_changed.emit(self._shock_result)
