# Demo Operational Runbooks

These are synthetic project guidelines for the RampUp demo, not evidence that
the systems described are deployed. Confirm the actual environment and owner
before using any procedure outside the demo.

## Banking API: authentication and access checks

1. Confirm the request has a valid authentication token before processing it.
2. Check that the authenticated customer is authorized to access the requested
	account or transaction; never rely on an account ID supplied by the caller
	alone.
3. Return a clear validation or authorization error without exposing secrets
	or another customer's data.
4. Apply rate limits to sensitive endpoints and record request metadata needed
	for audit, excluding tokens and sensitive personal data.
5. Test successful requests, missing or invalid fields, expired credentials,
	and attempts to access another customer's records.

## Banking events: retries and replay

1. Give each transaction event a stable idempotency key and make consumers
	safe to run the same event more than once.
2. Retry transient failures a bounded number of times. Send events that still
	fail to a dead-letter topic with enough context to investigate, but no
	credentials or unnecessary personal information.
3. Before replaying events, confirm the target consumer and replay range. Keep
	processing and reconciliation logs so duplicate or missing outcomes can be
	detected.
4. Reconcile results after replay. The demo decision calls for validation with
	at least 100,000 replayed events before full rollout.
5. The initial Kafka design in the sample records uses 3 brokers and 6
	partitions; treat these as starting values to measure, not universal
	production settings.

## Retail checkout: inventory correctness

Product pages may use cached availability for faster browsing, but checkout
must perform an atomic stock check against the authoritative store before
confirming an order. Do not treat a cached quantity as a reservation. If the
stock check fails, do not create a confirmed order; return the current
availability and let the customer choose what to do next.

## Healthcare integration: safe sample data

Use synthetic patient and appointment records only. Validate incoming and
outgoing payloads against the agreed FHIR-compatible structures and version.
Reject or quarantine invalid payloads for review rather than silently
discarding fields. Do not put patient details in application logs or demo
screenshots.

## Telecom alarms: burst handling

1. Accept alarms into the background ingestion path and preserve an event ID
	so retries can be recognized.
2. Separate ingestion from dashboard aggregation so a slow dashboard query
	does not block incoming alarms.
3. Monitor accepted, processed, retried, and failed event counts. Alert when
	accepted and processed counts diverge.
4. Test a burst of 5,000 alarms and verify that every accepted alarm is either
	processed or explicitly reported as failed; do not silently drop events.
