import json

from marketplace_handoff.handoff_service import HandoffLogbook, OrderHandoffRequest


class RecordingInfrai:
    def __init__(self) -> None:
        self.payload = {}

    def ingest_log(self, payload):
        self.payload = payload
        return {"accepted": True}

    def search_logs(self):
        return {
            "items": [
                {
                    "message": self.payload["entries"][0]["message"],
                    "api_key_id": "key_creator_job",
                },
                {"message": json.dumps({"event": "order_handoff", "order_id": "other"})},
            ]
        }

    def list_keys(self):
        return {"keys": [{"id": "key_creator_job", "name": "creator-worker"}]}


def test_ready_handoff_is_searchable_with_its_credential() -> None:
    infrai = RecordingInfrai()
    logbook = HandoffLogbook(infrai)  # type: ignore[arg-type]
    request = OrderHandoffRequest.model_validate(
        {
            "order_id": "order_42",
            "seller_id": "seller_7",
            "assets": [
                {
                    "asset_id": "asset_cover",
                    "title": "Podcast cover master",
                    "delivery_uri": "https://cdn.example.test/orders/42/cover.psd",
                }
            ],
            "buyer_update": {"buyer_id": "buyer_9", "note": "Master file delivered"},
        }
    )

    receipt = logbook.record(request)
    audit = logbook.audit("order_42")

    assert receipt.state == "ready_for_buyer"
    assert receipt.asset_count == 1
    assert set(infrai.payload) == {"entries"}
    assert infrai.payload["entries"][0]["request_id"] == receipt.handoff_id
    assert audit[0].handoff["assets"][0]["asset_id"] == "asset_cover"
    assert audit[0].credential == {"id": "key_creator_job", "name": "creator-worker"}
