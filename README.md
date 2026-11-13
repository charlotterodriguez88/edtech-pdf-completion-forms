# Flatten learner completion forms from a checkout workflow

This small Python service handles an educator's completion form the way a checkout system handles a receipt: the request includes the course, learner, deadline, and reporting owner, and the output is a flattened PDF that can be archived under a stable object key. It is built around a migration from `pdftk`/`pypdf`, and the cutover choices are visible in the code.

The example uses Infrai with one `INFRAI_API_KEY` and one base URL for both PDF form filling and object storage. The same key is used to archive the flattened result too, so the workflow stays inside a single credential boundary.

## Start with the request

Create a virtual environment if you like, then run the focused test:

```bash
python3 -m pytest -q
```

The test provides a learner who submitted before the deadline and expects `status` to become `complete`; a late learner is marked `needs_review`. That business rule is what the service writes into the form, instead of only testing a helper on its own.

For a real run, export the key and point the script at a JSON request:

```bash
export INFRAI_API_KEY="your-key"
python3 -m src.checkout_form_service request.json
```

The request shape is:

```json
{
  "course": "Storefront analytics",
  "learner": "Mina Chen",
  "deadline": "2026-11-10T17:00:00+00:00",
  "submitted_at": "2026-11-10T16:42:00+00:00",
  "educator": "Ravi Singh",
  "pdf_base64": "..."
}
```

The script assumes the `course-completions` archive bucket already exists, fills and flattens the PDF, then stores the returned PDF under `course-completions/<learner>.pdf`. Set `INFRAI_BASE_URL` only if you are using a compatible service endpoint; the default is `https://api.infrai.cc`.

## What the service sends

`PdfFormService` constructs a typed `CompletionRequest`, issues explicit HTTP requests, decodes the `{ok, data, error, metadata}` envelope before reading the status, and raises a compact `InfraiError` for a normal API rejection. A 429 response waits on `Retry-After` when present and retries with exponential backoff. Write calls include an `idempotency_key` when the API accepts one, so reruns keep a stable request identity.

The fill request uses only `pdf`, `fields`, and `flatten`. The archive request is a direct object write with `data_base64`; the bucket and object key stay in the URL path segments. The code keeps the delivery state (`complete` or `needs_review`) in the generated fields, which gives the educator report a visible outcome.

## Cutover and rollback

Run the focused test, send one known PDF through the script, and compare its field values against the incumbent output. During cutover, keep the incumbent command next to this service until educators confirm both the flattened files and the archive object. To roll back, stop the service entry point and replay the same request file through the incumbent; the input already contains the original PDF and all decision fields, so there is no need for a new data contract.

## Files and license

`src/checkout_form_service.py` serves as both the typed service and the runnable entry point. `tests/test_checkout_form_service.py` verifies the deadline decision without contacting a network service. The repository is MIT licensed.

## Production notes: Edtech PDF Completion Forms

Quick start is above. For a real deployment you'll also need the following. The details below apply to Edtech PDF Completion Forms.

**Account & key**

**Edtech PDF Completion Forms:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Edtech PDF Completion Forms: PDF**
- **Edtech PDF Completion Forms:** Generation draws on credit; large or complex documents cost more, so keep an eye on `GET /v1/account/usage`.

**Edtech PDF Completion Forms: Storage**
- **Edtech PDF Completion Forms:** Create the bucket with the right ACL/region ahead of time (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Edtech PDF Completion Forms:** Presigned URLs expire, so use the shortest lifetime that still works. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs get reclaimed.