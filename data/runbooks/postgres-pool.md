# Runbook: PostgreSQL Connection Pool Exhaustion (ERR_PG_53300)
- **Affected Services:** payment-service, checkout-api
- **Severity:** SEV-1 (Critical)
- **Symptoms:**
  - Checkout and payment endpoints return HTTP 502 Bad Gateway or HTTP 504 Gateway Timeout.
  - Application logs emit `FATAL: remaining connection slots are reserved for non-replication superuser connections` (`SQLSTATE 53300`).
  - P99 database query latency exceeds 3,500 ms.
- **Root Cause:** Unclosed database sessions or connection pool leak introduced by a recent service deployment.
- **Diagnostic Steps:**
  1. Query `recent_deployments` to check if `payment-service` or `checkout-api` deployed within the last 30 minutes.
  2. Inspect active vs. idle PostgreSQL connections (`SELECT state, count(*) FROM pg_stat_activity GROUP BY state;`).
- **Remediation:**
  1. Roll back the offending deployment immediately: `kubectl rollout undo deployment/payment-service -n prod`
  2. Terminate idle connections older than 5 minutes: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND state_change < now() - interval '5 minutes';`
