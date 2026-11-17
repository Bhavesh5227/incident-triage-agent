# Runbook: Kafka Consumer Group Lag & Partition Rebalance Storm (ERR_KAFKA_LAG_901)
- **Affected Services:** order-fulfillment-consumer, notification-worker
- **Severity:** SEV-2 (High)
- **Symptoms:**
  - Order confirmation emails and inventory updates are delayed by 15+ minutes.
  - Broker logs show continuous `Attempt to heartbeat failed since group is rebalancing` (`ERR_KAFKA_LAG_901`).
  - Consumer lag on topic `orders.events.v1` exceeds 250,000 messages.
- **Root Cause:** Slow downstream HTTP calls inside the consumer poll loop exceeded `max.poll.interval.ms` (300s), triggering repeated consumer group rebalances.
- **Diagnostic Steps:**
  1. Check `service_metrics` for `order-fulfillment-consumer` status `DEGRADED_CONSUMER_LAG`.
  2. Verify consumer group lag via `kafka-consumer-groups.sh --describe --group fulfillment-prod`.
- **Remediation:**
  1. Reduce `max.poll.records` from `500` to `100` so each batch completes well within `max.poll.interval.ms`.
  2. Scale consumer replicas to match topic partition count: `kubectl scale deployment/order-fulfillment-consumer --replicas=6 -n prod`
