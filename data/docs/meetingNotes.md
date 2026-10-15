# Architecture and Delivery Notes

Synthetic notes for the RampUp demo. Decision IDs and project IDs correspond
to records in `data/decision.json` and `data/projects.json`. These notes explain
selected decisions; the structured JSON records remain the canonical source
for decision owners, dates, and supersession links.

## 2026-02-10 - Banking event processing

**Project:** Secure Digital Banking API (`proj_001`)  
**Decision:** `decision_kafka`  
**Source ID:** `doc_payment_architecture`

The initial design used synchronous calls between payment, fraud detection,
and transaction audit services. Load testing reached about 450 transactions
per second before latency rose sharply. The team chose Kafka to buffer traffic,
decouple consumers, and support event replay. The initial plan is 3 brokers and
6 partitions. The trade-off is greater infrastructure and partition-management
work.

## 2026-02-12 - Transactional database

**Project:** Secure Digital Banking API (`proj_001`)  
**Decision:** `decision_003`  
**Source ID:** `doc_payment_database_comparison`

PostgreSQL was selected for customer, account, and payment records because the
workflow depends on relational constraints and reliable transactions. The
team plans indexes for account identifiers, transaction timestamps, and
payment status, then performance tests against at least one million records.

## 2026-02-18 - Fraud scoring boundary

**Project:** Real-Time Fraud Detection System (`proj_002`)  
**Decision:** `decision_004`  
**Source ID:** `doc_fraud_detection_design`

Fraud scoring will run as a separate service so risk rules and models can be
changed independently of payment execution. The extra network hop needs
monitoring. The target is below 100 ms at the 95th percentile under normal
load, with a defined fallback for scoring timeouts.

## 2026-03-05 - Kafka reliability revision

**Project:** Secure Digital Banking API (`proj_001`)  
**Decision:** `decision_kafka_v2`, superseding `decision_kafka`  
**Source ID:** `doc_kafka_reliability_review`

A replay test exposed a duplicate-processing risk when a consumer completed an
operation but restarted before committing its offset. Keep Kafka, but add
idempotency keys, bounded retries, a dead-letter topic, and reconciliation
checks. Validate with at least 100,000 replayed events before enabling the new
path for all transactions.

## 2026-03-20 - Decision documentation

**Project:** Secure Digital Banking API (`proj_001`)  
**Decision:** `decision_015`  
**Source ID:** `doc_architecture_decision_process`

Major architecture decisions should have a named owner, affected project,
supporting source, rationale, alternatives, and any decision they supersede.
This makes later onboarding and implementation reviews traceable to their
original context.
