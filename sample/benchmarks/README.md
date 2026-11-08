# Local measured example

[local-results.json](local-results.json) is a sanitized summary exported from actual saved job `38ced867-7cfc-429f-9a3a-bc4ee90e51d6`. It contains conditions, original/benchmark planner estimates, actual index main-fork sizes, individual-sample latency summaries, all repetition means/TPS/p95 values and regression comparisons. No row data, passwords, DSNs or raw SQL artifacts are included.

The two representative queries were orders for user 101 (frequency 100) and the latest 100 paid orders (frequency 25). UUID ordering puts the paid-orders probe at read_q0 and the user probe at read_q1. The dataset has 10,000 orders at seed 42. Three arm rotations used one client, 20 read-warmup transactions and 200 measured transactions per phase, producing 54 measurements and 10,800 durable individual transaction samples.

The baseline has only template constraint indexes. The per-query singleton union uses status/created_at and user_id indexes without a storage constraint; the saved IndexPilot selection uses user_id within a 300,000 estimated-byte budget. Actual initial additional main-fork sizes were 0, 475,136 and 114,688 bytes respectively. The larger per-query arm is not budget-matched.

Read latency/TPS describe one SELECT plus BEGIN/COMMIT/protocol overhead. Controlled writes are committed orders-table transactions, restored independently by operation/arm. Pooled p95 uses actual individual samples, not an average of repetition p95 values. mean_repetition_tps is an arithmetic average of observed repetition rates, not a pooled duration-weighted rate. Array values retain variability and all outlying repetitions. The observed slower update/delete repetitions are not assigned a cause.

These figures describe this local warm-cache environment only. No cold-cache, WAL, significance or universal-win claim is made. Rerunning can change the timings, sampled statistics and physical layout. Follow [BENCHMARKING.md](../../docs/BENCHMARKING.md) for the actual API/worker procedure and limits; use a new recommendation/benchmark job to repeat the experiment rather than editing this evidence.

To reproduce the logical inputs after the standard local setup/migration/API startup, use PowerShell:

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
function Send-IndexPilot([string]$path, [hashtable]$body) {
  Invoke-RestMethod -Method Post -Uri "$api/$path" -ContentType application/json `
    -Body ($body | ConvertTo-Json -Depth 20)
}
$userPlan = Send-IndexPilot 'plans' @{
  sql = 'SELECT id,status FROM public.orders WHERE user_id=101'; frequency = 100
}
$paidPlan = Send-IndexPilot 'plans' @{
  sql = "SELECT id,total FROM public.orders WHERE status='paid' ORDER BY created_at DESC LIMIT 100"
  frequency = 25
}
$batch = Send-IndexPilot 'candidates' @{ plan_ids = @($userPlan.id, $paidPlan.id) }
$optimization = Send-IndexPilot 'optimizations' @{
  batch_id = $batch.id; storage_budget_bytes = 300000; max_query_regression_pct = 0
}
$recommendation = Send-IndexPilot 'recommendations' @{ optimization_id = $optimization.id }
$job = Send-IndexPilot 'benchmarks' @{
  recommendation_id = $recommendation.id; confirm_disposable_benchmark = $true
  orders = 10000; seed = 42; repetitions = 3; clients = 1
  transactions_per_client = 200; read_warmup_per_client = 20; timeout_seconds = 300
}
$job.id
```

Run `uv run python scripts/run_benchmarks.py --once` in another terminal, then retrieve `/api/v1/benchmarks/<new-job-id>` and its measurements. New UUID ordering can swap read_q0/read_q1; always use the new job's read_weights mapping. Current source indexes/statistics can change the candidates/selection, and measured timings are not expected constants. The benchmark itself generates its own seeded data without resetting public source data.
