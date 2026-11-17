# Runbook: Redis Cache Eviction Spike & Latency Degradation (ERR_REDIS_OOM)
- **Affected Services:** session-gateway, catalog-service
- **Severity:** SEV-2 (High)
- **Symptoms:**
  - Sudden drop in cache hit ratio below 40%, causing downstream database CPU saturation.
  - Logs report `OOM command not allowed when used memory > 'maxmemory'` (`ERR_REDIS_OOM`).
  - API response times degrade from 30 ms to 900+ ms.
- **Root Cause:** Missing TTL (Time-To-Live) on newly introduced session keys or large uncompacted JSON blobs filling Redis `maxmemory`.
- **Diagnostic Steps:**
  1. Inspect `service_metrics` for `catalog-service` or `session-gateway` latency anomalies.
  2. Check keyspace eviction rate (`INFO stats` -> `evicted_keys`).
- **Remediation:**
  1. Flush non-critical ephemeral keys matching the un-expiring prefix: `redis-cli --scan --pattern "tmp:session:*" | xargs redis-cli del`
  2. Deploy hotfix enforcing `EX 3600` TTL on all `SET` operations.
