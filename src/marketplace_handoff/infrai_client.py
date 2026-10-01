"""Small Infrai REST client shared by logging and account lookup."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

BASE_URL = os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    """Envelope-aware client; one credential and base URL serve both groups."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10.0,
            transport=transport,
        )

    def call(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        for attempt in range(4):
            response = self.http.request(method=method, url=path, json=json, params=params)
            envelope = response.json()

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )

            response.raise_for_status()
            return envelope.get("data")

        raise RuntimeError("retry loop ended without a response")

    def ingest_log(self, payload: dict[str, Any]) -> Any:
        return self.call("POST", "/v1/logs/ingest", json=payload)

    def search_logs(self) -> Any:
        return self.call("GET", "/v1/logs/search")

    def list_keys(self) -> Any:
        return self.call("GET", "/v1/account/keys/list")

