"""
Thin HTTP client for the deblaot backend. Every method is a plain blocking
call -- callers (main_window.py) are responsible for running these off the
Qt main thread via workers.ApiWorker so a slow request (especially an
admin-password prompt on the backend side) never freezes the UI.
"""
from __future__ import annotations

from typing import Optional

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8765"

# Applying a tweak can involve a native macOS admin-password dialog that
# waits on a human, so it gets a much longer timeout than a plain GET.
QUICK_TIMEOUT = 15
APPLY_TIMEOUT = 180


class ApiError(Exception):
    """Raised for anything from a network failure to a 4xx/5xx response."""


class DeblaotClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, timeout: int, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"Couldn't reach deblaot at {self.base_url}: {exc}") from exc

        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except ValueError:
                pass
            raise ApiError(str(detail))

        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise ApiError(f"Backend returned a non-JSON response: {resp.text[:200]}") from exc

    # -- read-only ----------------------------------------------------

    def health(self) -> dict:
        return self._request("GET", "/health", QUICK_TIMEOUT)

    def system_info(self) -> dict:
        return self._request("GET", "/system", QUICK_TIMEOUT)

    def categories(self) -> list:
        return self._request("GET", "/categories", QUICK_TIMEOUT)

    def tweaks(self, category: Optional[str] = None) -> list:
        params = {"category": category} if category else None
        return self._request("GET", "/tweaks", QUICK_TIMEOUT, params=params)

    def presets(self) -> dict:
        return self._request("GET", "/presets", QUICK_TIMEOUT)

    def history_runs(self, limit: int = 20) -> list:
        return self._request("GET", "/history/runs", QUICK_TIMEOUT, params={"limit": limit})

    def history_run_detail(self, run_id: str) -> list:
        return self._request("GET", f"/history/runs/{run_id}", QUICK_TIMEOUT)

    # -- actions (long timeout: may involve an admin prompt) -----------

    def apply_tweak(self, tweak_id: str, param: Optional[str] = None, confirm_experimental: bool = False) -> dict:
        body = {"param": param, "confirm_experimental": confirm_experimental}
        return self._request("POST", f"/tweaks/{tweak_id}/apply", APPLY_TIMEOUT, json=body)

    def apply_category(self, category_id: str) -> dict:
        return self._request("POST", f"/categories/{category_id}/apply", APPLY_TIMEOUT)

    def apply_preset(self, preset_id: str) -> dict:
        return self._request("POST", f"/presets/{preset_id}/apply", APPLY_TIMEOUT)

    def revert(self, run_id: Optional[str] = None) -> dict:
        body = {"run_id": run_id} if run_id else {}
        return self._request("POST", "/history/revert", APPLY_TIMEOUT, json=body)
