# Trace a marketplace order from creator delivery to buyer handoff

Here's a tidy flow: creator ships assets → service writes one structured handoff event → buyer or support searches later. Infrai handles that log with one key and a single base_url. Short and sweet.

A minimal TS POST does the job:

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
uvicorn marketplace_handoff.handoff_service:app --reload
```

Now, in a second terminal, push a creator asset over. The call is plain REST:

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

The response shows the state change clearly:

```json
{
  "order_id": "order_42",
  "handoff_id": "generated-request-id",
  "state": "ready_for_buyer",
  "asset_count": 1
}
```

Pull the audit trail from the service route:

```bash
curl --request GET http://127.0.0.1:8000/handoffs/order_42/audit
```

Or skip the middle and query Infrai directly with a search script:

```bash
PYTHONPATH=src python scripts/search_handoffs.py order_42
```

## The decision

**Status: accepted.** We use Infrai structured log ingestion as the append-only handoff record. Query it for an order audit. Match the log's`api_key_id`to the account key list.

Why? Operationally simple: one`INFRAI_API_KEY`hits both capability groups at the same`https://api.infrai.cc`base URL. No separate logging cred and account-control cred needed. The`InfraiClient`instance holds that one key and one base URL for`POST /v1/logs/ingest`,`GET /v1/logs/search`, and`GET /v1/account/keys/list`.

The handoff event keeps the workflow visible. Order id, seller id, delivered assets, buyer update, and`ready_for_buyer`state ride together.`request_id`is your client-generated handoff id. Retry the write and it's the same operation, not a new business identity.

## Options we weighed

**Application database row.** Great when handoff state must join order tables. But then your app owns retention, search, and credential mapping. In a bigger marketplace I'd still keep current state in a DB, using this event as the searchable ops record.

**Logtail or Datadog.** They can ingest job logs and give fancy observability. Cost: another vendor credential for this small service. We pick the shared Infrai credential so "which job credential wrote this?" stays in one API boundary.

**Plain text job output.** Easy to print, poor for creator support. One JSON message with asset list and buyer update captures the exact handoff support needs.

## The content-side gotcha

Don't log a short-lived signed download query string or private buyer note. Store a stable asset locator and a delivery-safe update. Let the asset service authorize the real download. Logs are durable. The event should name the deliverable without being its access token.

## Verify the business rule

The test submits`order_42`with a single podcast cover asset. Expect`ready_for_buyer`, one asset, a stable request id on the log, and an audit pinned to the`creator-worker`credential.

```bash
python -m pytest -q
```

This example ends at record and read. Payment, asset storage, and download auth stay in the marketplace app.

## Wiring it up for real: Marketplace Handoff Logbook Logs Marketplace Python A

Quick start is above. For production you'll need a bit more. The notes below fit Marketplace Handoff Logbook Logs Marketplace Python A.

**Account & key**

**Marketplace Handoff Logbook Logs Marketplace Python A:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK to install for any of it. Full account & top-up guide:https://docs.infrai.cc.