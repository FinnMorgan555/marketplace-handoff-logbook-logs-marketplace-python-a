"""Typed HTTP routes for recording and auditing a marketplace handoff."""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_client import InfraiClient, InfraiError


class SellerAsset(BaseModel):
    asset_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    delivery_uri: str = Field(pattern=r"^https://")


class BuyerUpdate(BaseModel):
    buyer_id: str = Field(min_length=1)
    note: str = Field(min_length=1, max_length=500)


class OrderHandoffRequest(BaseModel):
    order_id: str = Field(min_length=1)
    seller_id: str = Field(min_length=1)
    assets: list[SellerAsset] = Field(min_length=1)
    buyer_update: BuyerUpdate


class HandoffReceipt(BaseModel):
    order_id: str
    handoff_id: str
    state: Literal["ready_for_buyer"]
    asset_count: int


class AuditEntry(BaseModel):
    handoff: dict[str, Any]
    credential: dict[str, Any] | None


def _records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for name in ("items", "logs", "events", "keys"):
            value = data.get(name)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _handoff_from_log(record: dict[str, Any]) -> dict[str, Any] | None:
    message = record.get("message")
    if not isinstance(message, str):
        return None
    try:
        decoded = json.loads(message)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) and decoded.get("event") == "order_handoff" else None


class HandoffLogbook:
    def __init__(self, infrai: InfraiClient) -> None:
        self.infrai = infrai

    def record(self, request: OrderHandoffRequest) -> HandoffReceipt:
        handoff_id = str(uuid4())
        event = {
            "event": "order_handoff",
            "handoff_id": handoff_id,
            "order_id": request.order_id,
            "seller_id": request.seller_id,
            "assets": [asset.model_dump() for asset in request.assets],
            "buyer_update": request.buyer_update.model_dump(),
            "state": "ready_for_buyer",
        }
        self.infrai.ingest_log(
            {
                "entries": [
                    {
                        "level": "info",
                        "message": json.dumps(event, separators=(",", ":"), sort_keys=True),
                        "service": "marketplace-handoff",
                        "env": "production",
                        "request_id": handoff_id,
                        "user_id": request.buyer_update.buyer_id,
                    }
                ]
            }
        )
        return HandoffReceipt(
            order_id=request.order_id,
            handoff_id=handoff_id,
            state="ready_for_buyer",
            asset_count=len(request.assets),
        )

    def audit(self, order_id: str) -> list[AuditEntry]:
        keys = _records(self.infrai.list_keys())
        keys_by_id = {str(item.get("id")): item for item in keys}
        entries: list[AuditEntry] = []
        for record in _records(self.infrai.search_logs()):
            handoff = _handoff_from_log(record)
            if handoff is None or handoff.get("order_id") != order_id:
                continue
            key_id = record.get("api_key_id")
            entries.append(
                AuditEntry(
                    handoff=handoff,
                    credential=keys_by_id.get(str(key_id)) if key_id is not None else None,
                )
            )
        return entries


def get_logbook() -> HandoffLogbook:
    return HandoffLogbook(InfraiClient())


app = FastAPI(title="Marketplace handoff logbook")


@app.post("/handoffs", response_model=HandoffReceipt, status_code=201)
def create_handoff(
    request: OrderHandoffRequest,
    logbook: HandoffLogbook = Depends(get_logbook),
) -> HandoffReceipt:
    try:
        return logbook.record(request)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.detail) from exc


@app.get("/handoffs/{order_id}/audit", response_model=list[AuditEntry])
def audit_handoff(
    order_id: str,
    logbook: HandoffLogbook = Depends(get_logbook),
) -> list[AuditEntry]:
    try:
        return logbook.audit(order_id)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.detail) from exc
