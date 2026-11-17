# Runbook: Kubernetes Pod OOMKilled & CrashLoopBackOff (ERR_K8S_137)
- **Affected Services:** recommendation-worker, user-profile-service
- **Severity:** SEV-2 (High)
- **Symptoms:**
  - Kubernetes pods repeatedly restart and enter `CrashLoopBackOff`.
  - Pod status shows `Last State: Terminated — Reason: OOMKilled (Exit Code 137)`.
  - Spike in failed batch inference requests and elevated 503 responses.
- **Root Cause:** Container memory usage exceeded its cgroup memory limit due to unbounded in-memory payload caching after a worker deployment.
- **Diagnostic Steps:**
  1. Check `service_metrics` for `WARN_EXIT_CODE_137` or elevated error rates on worker pods.
  2. Verify recent container image updates in `recent_deployments`.
- **Remediation:**
  1. Patch the deployment memory limit from `512Mi` to `1Gi`: `kubectl set resources deployment/recommendation-worker --limits=memory=1Gi -n prod`
  2. Reduce worker concurrency flag to `--workers 2` to cap per-pod RSS footprint.
