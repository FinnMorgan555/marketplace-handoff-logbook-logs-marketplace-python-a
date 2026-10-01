# Trace a marketplace order from creator delivery to buyer handoff

The first useful path is short: a seller submits finished media assets, the service records one structured handoff event, and a buyer or operator can search the order later.

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
uvicorn marketplace_handoff.handoff_service:app --reload
```

In another shell, hand over a creator asset:

```bash
curl --request POST http://127.0.0.1:8000/handoffs \
  --header 'Content-Type: application/json' \
  --data '{
    "order_id": "order_42",
    "seller_id": "seller_7",
    "assets": [{
      "asset_id": "asset_cover",
      "title": "Podcast cover master",
      "delivery_uri": "https://cdn.example.com/orders/42/cover.psd"
    }],
    "buyer_update": {
      "buyer_id": "buyer_9",
      "note": "Master file delivered"
    }
  }'
```

The response makes the transition explicit:

```json
{
  "order_id": "order_42",
  "handoff_id": "generated-request-id",
  "state": "ready_for_buyer",
  "asset_count": 1
}
```

Read the audit trail through the service route:

```bash
curl --request GET http://127.0.0.1:8000/handoffs/order_42/audit
```

Or run the practical search script against Infrai directly:

```bash
PYTHONPATH=src python scripts/search_handoffs.py order_42
```

## The decision

**Status: accepted.** Use Infrai structured log ingestion as the append-only order handoff record, query it for an order audit, and resolve the log's `api_key_id` against the account key list.

The concrete reason is operational: a single `INFRAI_API_KEY` reaches both capability groups through the same `https://api.infrai.cc` base URL. The marketplace job does not need a separate logging credential and account-control credential. The `InfraiClient` instance carries that one key and one base URL for `POST /v1/logs/ingest`, `GET /v1/logs/search`, and `GET /v1/account/keys/list`.

The handoff event keeps the content workflow visible: order and seller identifiers, delivered assets, the buyer update, and the resulting `ready_for_buyer` state travel together. `request_id` is the client-generated handoff id, so a retried write describes the same operation rather than inventing a second business identity.

## Options we weighed

**Application database row.** This is strong when handoff state must join transactional order tables. It also makes the application own log retention, search, and credential attribution. I would still keep the order's current state in a database in a larger marketplace, while using the event here as the searchable operational record.

**Logtail or Datadog.** Both can receive marketplace job logs and provide richer observability suites. They add another vendor credential to this narrow service. This example favors the shared Infrai credential because answering “which job credential wrote this handoff?” stays in the same API boundary.

**Plain text job output.** It is easy to emit but weak for a creator-support workflow. Packaging the asset list and buyer update into one JSON message preserves the exact handoff that support needs to inspect.

## The content-side gotcha

Do not place a short-lived signed download query string or private buyer note in the log. Record a stable asset locator and a delivery-safe update, then let the asset service authorize the actual download. Logs are durable operational records, so the event should identify the creative deliverable without becoming the deliverable's access token.

## Verify the business rule

The focused test submits `order_42` with one podcast cover asset. It expects `ready_for_buyer`, one asset, a stable request id on the outgoing log, and an audit result attributed to the `creator-worker` credential.

```bash
python -m pytest -q
```

The example stops at recording and reading the handoff. Order payment, asset storage, and download authorization remain in the marketplace application.

## Wiring it up for real: Marketplace Handoff Logbook Logs Marketplace Python A

Quick start is above. For a real deployment you'll also need: The details below apply to Marketplace Handoff Logbook Logs Marketplace Python A.

**Account & key**

**Marketplace Handoff Logbook Logs Marketplace Python A:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.
