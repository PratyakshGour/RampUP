# Payments architecture sync — 2026-10-03

Priya Nair, Arjun Mehta, and Riya Sharma attended the Atlas Payments architecture sync.

The team confirmed Kafka for asynchronous payment events because synchronous calls between payment, fraud, and audit services reached a latency knee at approximately 450 transactions per second. Kafka buffers bursts, separates consumers, and supports replay. The trade-off is additional broker and partition operations.

The team confirmed PostgreSQL for payment records because the workflow needs transactions and relational constraints. MongoDB was considered but not selected for the primary transactional store.

Priya Nair owns the Atlas Payments project. Arjun will add bounded retries and a dead-letter topic to the Kafka consumer before the next load test.
