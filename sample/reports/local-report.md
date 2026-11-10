# Local two\-query benchmark evidence

Report: 237c2186-be58-474c-b21d-a3d7369ca80d
Format: indexpilot-report-v1
Created: 2026-11-10T15:40:28.543068+00:00
Recommendation: 74790511-99fe-4452-973c-df9eb247f670
Optimization: ba9dafc3-8bc0-4e6c-9152-f98c34e827e9
Candidate batch: b2f59f43-b5c1-4dcd-a34a-a559842e4679

## Evidence and privacy policy

Frozen historical evidence. Planner costs are estimates, not milliseconds.
Bound representative SQL, raw plans and typed parameter maps are omitted\. Original SQL may still contain literal values\.

## Missing evidence and limitations

- Cold\-cache, WAL and statistical significance were not measured\.
- Greedy selection does not establish a global optimum\.

## Estimated workload result

- Storage budget: 300000 bytes
- Selected estimated size: 286720 bytes
- Weighted baseline root cost: 39270.0 planner_cost
- Weighted final root cost: 12562.0 planner_cost
- Estimated read improvement: 68.01120448179272 percent
- Search stop: no\_feasible\_gain; complete: True

## Settings and provenance

```json
{
  "settings": {
    "storage_budget_bytes": 300000,
    "max_selected_indexes": 8,
    "max_evaluations": 128,
    "max_query_regression_pct": 0.0,
    "write_penalty_cost_per_mib": 0.0,
    "write_weights": {},
    "frequency_basis": "user_supplied_scenario"
  },
  "provenance": {
    "evaluation_context": {
      "policy": "greedy-marginal-v1",
      "database": "indexpilot_demo",
      "database_oid": 16389,
      "server_version": "18.6 (Debian 18.6-1.pgdg12+2)",
      "frequency_basis": "user_supplied_scenario",
      "max_evaluations": 128,
      "snapshot_policy": "repeatable-read-read-only",
      "planner_settings": {
        "jit": "on",
        "work_mem": "4096",
        "enable_sort": "on",
        "seq_page_cost": "1",
        "cpu_tuple_cost": "0.01",
        "enable_hashagg": "on",
        "enable_memoize": "on",
        "enable_seqscan": "on",
        "hypopg.enabled": "on",
        "enable_hashjoin": "on",
        "enable_material": "on",
        "enable_nestloop": "on",
        "plan_cache_mode": "auto",
        "enable_indexscan": "on",
        "enable_mergejoin": "on",
        "random_page_cost": "4",
        "cpu_operator_cost": "0.0025",
        "enable_bitmapscan": "on",
        "parallel_setup_cost": "1000",
        "parallel_tuple_cost": "0.1",
        "cpu_index_tuple_cost": "0.005",
        "effective_cache_size": "524288",
        "enable_indexonlyscan": "on",
        "hypopg.use_real_oids": "off",
        "enable_incremental_sort": "on",
        "max_parallel_workers_per_gather": "2"
      },
      "catalog_observed_at": "2026-11-08T17:35:07.602493+00:00",
      "planning_budget_seconds": 30.0
    },
    "generation_options": {
      "max_columns": 3,
      "max_candidates": 32
    },
    "explanation_version": "recommendation-explanations-v1",
    "selection_algorithm": "greedy-marginal-v1",
    "generation_truncated": false,
    "optimization_created_at": "2026-11-08T17:35:07.672080+00:00",
    "recommendation_created_at": "2026-11-08T17:35:08.014472+00:00"
  }
}
```

## Queries

### Query 2b5289c1-8ce7-44a7-af64-0369a3ece466

Frequency: 25.0
Root cost: 390.8 -> 390.8 planner_cost
Weighted contribution: 0.0 percent of baseline

Original SQL:

```sql
SELECT id,total FROM public.orders WHERE status='paid' ORDER BY created_at DESC LIMIT 100
```

```json
{
  "explanation": {
    "baseline_cost": 390.8,
    "final_cost": 390.8,
    "estimated_cost_reduction": 0.0,
    "estimated_improvement_pct": 0.0,
    "baseline_weighted_cost": 9770.0,
    "final_weighted_cost": 9770.0,
    "estimated_weighted_cost_reduction": 0.0,
    "contribution_to_baseline_pct": 0.0,
    "regression": false,
    "comparison": {
      "baseline_node_types": [
        "Limit",
        "Seq Scan",
        "Sort"
      ],
      "final_node_types": [
        "Limit",
        "Seq Scan",
        "Sort"
      ],
      "baseline_index_names": [],
      "final_used_candidate_ids": [],
      "observations": [
        "Estimated root cost changed from 390.8 to 390.8 planner units.",
        "Final plan references 0 selected hypothetical index(es)."
      ]
    },
    "warnings": [
      "Index usage is cumulative and is insufficient evidence for dropping an index."
    ]
  },
  "statistics": [
    {
      "relation_oid": 16592,
      "schema_name": "public",
      "table_name": "orders",
      "last_analyze": "2026-11-07T11:24:15.708057Z",
      "last_autoanalyze": "2026-11-07T11:24:21.264140Z"
    }
  ]
}
```

### Query 3ad12961-131d-424e-ab81-39d563cac260

Frequency: 100.0
Root cost: 295.0 -> 27.92 planner_cost
Weighted contribution: 68.01120448179272 percent of baseline

Original SQL:

```sql
SELECT id,status FROM public.orders WHERE user_id=101
```

```json
{
  "explanation": {
    "baseline_cost": 295.0,
    "final_cost": 27.92,
    "estimated_cost_reduction": 267.08,
    "estimated_improvement_pct": 90.53559322033898,
    "baseline_weighted_cost": 29500.0,
    "final_weighted_cost": 2792.0,
    "estimated_weighted_cost_reduction": 26708.0,
    "contribution_to_baseline_pct": 68.01120448179272,
    "regression": false,
    "comparison": {
      "baseline_node_types": [
        "Seq Scan"
      ],
      "final_node_types": [
        "Bitmap Heap Scan",
        "Bitmap Index Scan"
      ],
      "baseline_index_names": [],
      "final_used_candidate_ids": [
        "5b302cf2-85ae-4a47-84ba-99c4962adc90"
      ],
      "observations": [
        "Estimated root cost changed from 295 to 27.92 planner units.",
        "Final plan references 1 selected hypothetical index(es).",
        "Observed plan node types changed; this is an estimated plan comparison."
      ]
    },
    "warnings": [
      "Index usage is cumulative and is insufficient evidence for dropping an index."
    ]
  },
  "statistics": [
    {
      "relation_oid": 16592,
      "schema_name": "public",
      "table_name": "orders",
      "last_analyze": "2026-11-07T11:24:15.708057Z",
      "last_autoanalyze": "2026-11-07T11:24:21.264140Z"
    }
  ]
}
```

## Selected indexes

### ip\_orders\_4a8e7bfd62a3805b

Estimated size: 286720 bytes
Chosen at step 1: estimated objective decreased by 26708 weighted planner units, at 0\.0931501 units per additional estimated byte\.
Additional B\-Tree indexes can add storage and maintenance for inserts, deletes and updates to indexed columns\. Write latency, WAL and maintenance overhead have not been measured\.

Deployment SQL for human review only:

```sql
CREATE INDEX "ip_orders_4a8e7bfd62a3805b" ON "public"."orders" USING btree ("user_id" "pg_catalog"."int8_ops" ASC NULLS LAST);
```

## All candidate decisions

- 7c3c2226-f8a2-4750-bfbb-d89ce6be9db9: public.orders (status, created\_at); generation=proposed; selected=False; reason=storage\_budget
- 9dbea782-f987-49c4-b9a7-064b453007a8: public.orders (created\_at); generation=proposed; selected=False; reason=storage\_budget
- 5b302cf2-85ae-4a47-84ba-99c4962adc90: public.orders (user\_id); generation=proposed; selected=True; reason=selected
- 4772182d-2eda-4aa4-b0cb-c328ae0db052: public.orders (status); generation=proposed; selected=False; reason=storage\_budget

## Saved search trials

```json
[
  {
    "step": 1,
    "added_candidate_id": "4772182d-2eda-4aa4-b0cb-c328ae0db052",
    "candidate_ids": [
      "4772182d-2eda-4aa4-b0cb-c328ae0db052"
    ],
    "score": {
      "read_cost": 38311.5,
      "storage_bytes": 270336,
      "write_penalty": 0.0,
      "objective": 38311.5,
      "feasible": true,
      "reason": null
    },
    "marginal_net_gain": 958.5,
    "additional_bytes": 270336,
    "gain_per_byte": 0.003545587713068182,
    "chosen": false,
    "reason": "lower_marginal_score",
    "query_changes": [
      {
        "source_plan_id": "2b5289c1-8ce7-44a7-af64-0369a3ece466",
        "frequency": 25.0,
        "baseline_cost": 390.8,
        "cost": 352.46,
        "absolute_change": -38.34000000000003,
        "estimated_improvement_pct": 9.810644831115667,
        "regression": false
      },
      {
        "source_plan_id": "3ad12961-131d-424e-ab81-39d563cac260",
        "frequency": 100.0,
        "baseline_cost": 295.0,
        "cost": 295.0,
        "absolute_change": 0.0,
        "estimated_improvement_pct": 0.0,
        "regression": false
      }
    ]
  },
  {
    "step": 1,
    "added_candidate_id": "5b302cf2-85ae-4a47-84ba-99c4962adc90",
    "candidate_ids": [
      "5b302cf2-85ae-4a47-84ba-99c4962adc90"
    ],
    "score": {
      "read_cost": 12562.0,
      "storage_bytes": 286720,
      "write_penalty": 0.0,
      "objective": 12562.0,
      "feasible": true,
      "reason": null
    },
    "marginal_net_gain": 26708.0,
    "additional_bytes": 286720,
    "gain_per_byte": 0.09315011160714286,
    "chosen": true,
    "reason": "selected",
    "query_changes": [
      {
        "source_plan_id": "2b5289c1-8ce7-44a7-af64-0369a3ece466",
        "frequency": 25.0,
        "baseline_cost": 390.8,
        "cost": 390.8,
        "absolute_change": 0.0,
        "estimated_improvement_pct": 0.0,
        "regression": false
      },
      {
        "source_plan_id": "3ad12961-131d-424e-ab81-39d563cac260",
        "frequency": 100.0,
        "baseline_cost": 295.0,
        "cost": 27.92,
        "absolute_change": -267.08,
        "estimated_improvement_pct": 90.53559322033898,
        "regression": false
      }
    ]
  },
  {
    "step": 1,
    "added_candidate_id": "7c3c2226-f8a2-4750-bfbb-d89ce6be9db9",
    "candidate_ids": [
      "7c3c2226-f8a2-4750-bfbb-d89ce6be9db9"
    ],
    "score": {
      "read_cost": 30250.25,
      "storage_bytes": 385024,
      "write_penalty": 0.0,
      "objective": 30250.25,
      "feasible": false,
      "reason": "storage_budget"
    },
    "marginal_net_gain": 9019.75,
    "additional_bytes": 385024,
    "gain_per_byte": null,
    "chosen": false,
    "reason": "storage_budget",
    "query_changes": [
      {
        "source_plan_id": "2b5289c1-8ce7-44a7-af64-0369a3ece466",
        "frequency": 25.0,
        "baseline_cost": 390.8,
        "cost": 30.01,
        "absolute_change": -360.79,
        "estimated_improvement_pct": 92.32088024564995,
        "regression": false
      },
      {
        "source_plan_id": "3ad12961-131d-424e-ab81-39d563cac260",
        "frequency": 100.0,
        "baseline_cost": 295.0,
        "cost": 295.0,
        "absolute_change": 0.0,
        "estimated_improvement_pct": 0.0,
        "regression": false
      }
    ]
  },
  {
    "step": 1,
    "added_candidate_id": "9dbea782-f987-49c4-b9a7-064b453007a8",
    "candidate_ids": [
      "9dbea782-f987-49c4-b9a7-064b453007a8"
    ],
    "score": {
      "read_cost": 30490.25,
      "storage_bytes": 286720,
      "write_penalty": 0.0,
      "objective": 30490.25,
      "feasible": true,
      "reason": null
    },
    "marginal_net_gain": 8779.75,
    "additional_bytes": 286720,
    "gain_per_byte": 0.030621337890625,
    "chosen": false,
    "reason": "lower_marginal_score",
    "query_changes": [
      {
        "source_plan_id": "2b5289c1-8ce7-44a7-af64-0369a3ece466",
        "frequency": 25.0,
        "baseline_cost": 390.8,
        "cost": 39.61,
        "absolute_change": -351.19,
        "estimated_improvement_pct": 89.86438075742068,
        "regression": false
      },
      {
        "source_plan_id": "3ad12961-131d-424e-ab81-39d563cac260",
        "frequency": 100.0,
        "baseline_cost": 295.0,
        "cost": 295.0,
        "absolute_change": 0.0,
        "estimated_improvement_pct": 0.0,
        "regression": false
      }
    ]
  },
  {
    "step": 2,
    "added_candidate_id": "4772182d-2eda-4aa4-b0cb-c328ae0db052",
    "candidate_ids": [
      "4772182d-2eda-4aa4-b0cb-c328ae0db052",
      "5b302cf2-85ae-4a47-84ba-99c4962adc90"
    ],
    "score": {
      "read_cost": 11603.5,
      "storage_bytes": 557056,
      "write_penalty": 0.0,
      "objective": 11603.5,
      "feasible": false,
      "reason": "storage_budget"
    },
    "marginal_net_gain": 958.5,
    "additional_bytes": 270336,
    "gain_per_byte": null,
    "chosen": false,
    "reason": "storage_budget",
    "query_changes": [
      {
        "source_plan_id": "2b5289c1-8ce7-44a7-af64-0369a3ece466",
        "frequency": 25.0,
        "baseline_cost": 390.8,
        "cost": 352.46,
        "absolute_change": -38.34000000000003,
        "estimated_improvement_pct": 9.810644831115667,
        "regression": false
      },
      {
        "source_plan_id": "3ad12961-131d-424e-ab81-39d563cac260",
        "frequency": 100.0,
        "baseline_cost": 295.0,
        "cost": 27.92,
        "absolute_change": -267.08,
        "estimated_improvement_pct": 90.53559322033898,
        "regression": false
      }
    ]
  },
  {
    "step": 2,
    "added_candidate_id": "7c3c2226-f8a2-4750-bfbb-d89ce6be9db9",
    "candidate_ids": [
      "5b302cf2-85ae-4a47-84ba-99c4962adc90",
      "7c3c2226-f8a2-4750-bfbb-d89ce6be9db9"
    ],
    "score": {
      "read_cost": 3542.25,
      "storage_bytes": 671744,
      "write_penalty": 0.0,
      "objective": 3542.25,
      "feasible": false,
      "reason": "storage_budget"
    },
    "marginal_net_gain": 9019.75,
    "additional_bytes": 385024,
    "gain_per_byte": null,
    "chosen": false,
    "reason": "storage_budget",
    "query_changes": [
      {
        "source_plan_id": "2b5289c1-8ce7-44a7-af64-0369a3ece466",
        "frequency": 25.0,
        "baseline_cost": 390.8,
        "cost": 30.01,
        "absolute_change": -360.79,
        "estimated_improvement_pct": 92.32088024564995,
        "regression": false
      },
      {
        "source_plan_id": "3ad12961-131d-424e-ab81-39d563cac260",
        "frequency": 100.0,
        "baseline_cost": 295.0,
        "cost": 27.92,
        "absolute_change": -267.08,
        "estimated_improvement_pct": 90.53559322033898,
        "regression": false
      }
    ]
  },
  {
    "step": 2,
    "added_candidate_id": "9dbea782-f987-49c4-b9a7-064b453007a8",
    "candidate_ids": [
      "5b302cf2-85ae-4a47-84ba-99c4962adc90",
      "9dbea782-f987-49c4-b9a7-064b453007a8"
    ],
    "score": {
      "read_cost": 3782.25,
      "storage_bytes": 573440,
      "write_penalty": 0.0,
      "objective": 3782.25,
      "feasible": false,
      "reason": "storage_budget"
    },
    "marginal_net_gain": 8779.75,
    "additional_bytes": 286720,
    "gain_per_byte": null,
    "chosen": false,
    "reason": "storage_budget",
    "query_changes": [
      {
        "source_plan_id": "2b5289c1-8ce7-44a7-af64-0369a3ece466",
        "frequency": 25.0,
        "baseline_cost": 390.8,
        "cost": 39.61,
        "absolute_change": -351.19,
        "estimated_improvement_pct": 89.86438075742068,
        "regression": false
      },
      {
        "source_plan_id": "3ad12961-131d-424e-ab81-39d563cac260",
        "frequency": 100.0,
        "baseline_cost": 295.0,
        "cost": 27.92,
        "absolute_change": -267.08,
        "estimated_improvement_pct": 90.53559322033898,
        "regression": false
      }
    ]
  }
]
```

## Physical benchmarks

### Benchmark 38ced867-7cfc-429f-9a3a-bc4ee90e51d6

Status: completed; cleanup confirmed: True; complete comparison: True
Local dashboard: /benchmarks?job=38ced867-7cfc-429f-9a3a-bc4ee90e51d6

Latency: ms; throughput: transactions/second; storage: bytes.
Measurements from unsuccessful jobs are partial, not a completed comparison.

```json
{
  "id": "38ced867-7cfc-429f-9a3a-bc4ee90e51d6",
  "status": "completed",
  "cleanup_confirmed": true,
  "complete_comparison": true,
  "created_at": "2026-11-08T17:35:08.154637+00:00",
  "finished_at": "2026-11-08T17:36:31.959418+00:00",
  "request": {
    "seed": 42,
    "orders": 10000,
    "clients": 1,
    "repetitions": 3,
    "timeout_seconds": 300,
    "read_warmup_per_client": 20,
    "transactions_per_client": 200,
    "regression_threshold_pct": 10.0
  },
  "conditions": {
    "policy": "isolated-pgbench-v1",
    "dataset": {
      "seed": 42,
      "anchor": "2026-01-01T00:00:00+00:00",
      "orders": 10000,
      "generator_version": 1
    },
    "threads": 1,
    "protocol": "simple",
    "arm_order": "cyclic rotation by repetition",
    "budget_bytes": 300000,
    "cache_policy": "read warmup; no OS/PostgreSQL cache flush; restored write datasets",
    "read_weights": [
      {
        "frequency": 25.0,
        "pgbench_weight": 2500,
        "source_plan_id": "2b5289c1-8ce7-44a7-af64-0369a3ece466"
      },
      {
        "frequency": 100.0,
        "pgbench_weight": 10000,
        "source_plan_id": "3ad12961-131d-424e-ab81-39d563cac260"
      }
    ],
    "weight_policy": "nearest integer after max-frequency scaling to 10000, minimum one; quantized",
    "host_cpu_count": 32,
    "python_version": "3.12.13",
    "server_version": "18.6 (Debian 18.6-1.pgdg12+2)",
    "client_platform": "Windows",
    "pgbench_version": "pgbench (PostgreSQL) 18.6 (Debian 18.6-1.pgdg12+2)",
    "container_limits": "cpu=max 100000\nmemory=max\ncpus=32\nMemTotal:       32712384 kB\n",
    "planner_settings": {
      "TimeZone": "Etc/UTC",
      "work_mem": "4096",
      "seq_page_cost": "1",
      "shared_buffers": "16384",
      "random_page_cost": "4",
      "effective_cache_size": "524288",
      "max_parallel_workers_per_gather": "2"
    },
    "sample_semantics": "committed transaction latency including BEGIN/COMMIT and protocol"
  },
  "measurements": [
    {
      "id": "cf694757-1490-43b8-a894-490eed6f8a82",
      "repetition": 0,
      "arm": "baseline",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.374715,
        "median_ms": 2.3,
        "p95_ms": 3.087,
        "tps": 420.26607,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2088960,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "352d074f-7f87-4635-ab3f-450f8f058cc3",
      "repetition": 0,
      "arm": "baseline",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.418925,
        "median_ms": 2.3215000000000003,
        "p95_ms": 3.07,
        "tps": 412.472339,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "ef428bdc-b587-4ac2-b553-a35b939e663e",
      "repetition": 0,
      "arm": "baseline",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.339945,
        "median_ms": 0.2705,
        "p95_ms": 0.544,
        "tps": 2930.574686,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "81caf94e-e7bb-4ba4-aaa3-0ee1fa282166",
      "repetition": 0,
      "arm": "baseline",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.499475,
        "median_ms": 0.476,
        "p95_ms": 0.58,
        "tps": 1997.343533,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "c2a46436-e698-4aa0-be28-347280035ee2",
      "repetition": 0,
      "arm": "baseline",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.28174,
        "median_ms": 0.264,
        "p95_ms": 0.362,
        "tps": 3534.880433,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "c92574ff-7501-42d8-bed0-77dee2d20b6d",
      "repetition": 0,
      "arm": "baseline",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.264005,
        "median_ms": 2.199,
        "p95_ms": 2.648,
        "tps": 440.881145,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "1040b908-a295-4d97-94e6-59657d38de05",
      "repetition": 0,
      "arm": "indexpilot",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.37032,
        "median_ms": 2.2945,
        "p95_ms": 2.805,
        "tps": 420.995022,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2203648,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "c99bba5a-a074-447c-b229-7134bad97554",
      "repetition": 0,
      "arm": "indexpilot",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.322045,
        "median_ms": 2.2960000000000003,
        "p95_ms": 2.805,
        "tps": 429.72955,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 122880
      }
    },
    {
      "id": "ed447838-cf09-48c2-a2a6-ba871caac731",
      "repetition": 0,
      "arm": "indexpilot",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.219685,
        "median_ms": 0.108,
        "p95_ms": 0.544,
        "tps": 4523.55642,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "85be5ded-97cb-48ca-9552-e29c1e94bcfd",
      "repetition": 0,
      "arm": "indexpilot",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.54486,
        "median_ms": 0.518,
        "p95_ms": 0.65,
        "tps": 1830.529572,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "d1f518f5-aa5e-451d-9819-ed0329554169",
      "repetition": 0,
      "arm": "indexpilot",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.112545,
        "median_ms": 0.103,
        "p95_ms": 0.162,
        "tps": 8795.84836,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "ded5aeab-caac-446f-b142-461676ea73d1",
      "repetition": 0,
      "arm": "indexpilot",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.333725,
        "median_ms": 2.299,
        "p95_ms": 2.719,
        "tps": 427.57335,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 122880
      }
    },
    {
      "id": "65c1a2e9-496f-4c56-853b-27e73703af1a",
      "repetition": 0,
      "arm": "per_query",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 10.344100000000001,
        "median_ms": 9.753499999999999,
        "p95_ms": 21.655,
        "tps": 96.588634,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2564096,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "f1f6cef9-3dd4-4e60-bbc7-e59ce4bd3e9f",
      "repetition": 0,
      "arm": "per_query",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.34807,
        "median_ms": 2.3034999999999997,
        "p95_ms": 2.852,
        "tps": 425.048084,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 491520
      }
    },
    {
      "id": "5900c254-6673-4ae5-bb1f-fff5136e65e6",
      "repetition": 0,
      "arm": "per_query",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.12304499999999999,
        "median_ms": 0.104,
        "p95_ms": 0.179,
        "tps": 8052.178114,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "09c8a6e6-b831-4764-921c-158645e26005",
      "repetition": 0,
      "arm": "per_query",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.139315,
        "median_ms": 0.128,
        "p95_ms": 0.199,
        "tps": 7124.283119,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "7a7093ae-8958-416c-9b58-6c4b2f4cc1d2",
      "repetition": 0,
      "arm": "per_query",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.11516,
        "median_ms": 0.103,
        "p95_ms": 0.153,
        "tps": 8600.670852,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "7502c668-ff6b-4c04-9e53-70f9a174dac7",
      "repetition": 0,
      "arm": "per_query",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.382505,
        "median_ms": 2.281,
        "p95_ms": 3.022,
        "tps": 418.871852,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 42,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 483328
      }
    },
    {
      "id": "9916051b-cbcc-455b-be9e-9eae2b1de617",
      "repetition": 1,
      "arm": "baseline",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.43925,
        "median_ms": 2.3739999999999997,
        "p95_ms": 3.023,
        "tps": 409.033087,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2088960,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "253dc085-20bf-4d3e-886a-a3ba476d33de",
      "repetition": 1,
      "arm": "baseline",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.3615049999999997,
        "median_ms": 2.285,
        "p95_ms": 2.824,
        "tps": 422.531045,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "b3690f20-80ab-4eaa-b89e-07185ac1b269",
      "repetition": 1,
      "arm": "baseline",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.36725499999999994,
        "median_ms": 0.306,
        "p95_ms": 0.612,
        "tps": 2713.483299,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "276b6624-a7f1-44d2-86c0-15e56cd9ab23",
      "repetition": 1,
      "arm": "baseline",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.536215,
        "median_ms": 0.5185,
        "p95_ms": 0.617,
        "tps": 1860.551654,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "7d625676-2ce9-4518-8eec-53df5fcd73a9",
      "repetition": 1,
      "arm": "baseline",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.321275,
        "median_ms": 0.3045,
        "p95_ms": 0.394,
        "tps": 3101.015583,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "b6aaefa3-9d6c-4b7b-9cf0-555c6afc78a5",
      "repetition": 1,
      "arm": "baseline",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.3321199999999997,
        "median_ms": 2.26,
        "p95_ms": 2.717,
        "tps": 427.981426,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "908059dd-71ba-43f7-964d-240a9849bcdc",
      "repetition": 1,
      "arm": "indexpilot",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.40723,
        "median_ms": 2.3295,
        "p95_ms": 2.938,
        "tps": 414.558464,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2203648,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "33c37887-499c-434b-82e0-82d9bc0c5a52",
      "repetition": 1,
      "arm": "indexpilot",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.30785,
        "median_ms": 2.257,
        "p95_ms": 2.75,
        "tps": 432.359516,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 122880
      }
    },
    {
      "id": "326872d2-5363-4668-9c51-aa8ed42dae04",
      "repetition": 1,
      "arm": "indexpilot",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.20349499999999998,
        "median_ms": 0.105,
        "p95_ms": 0.537,
        "tps": 4887.227232,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "5defadf1-b1f5-4e64-aa2e-8c03420f06c4",
      "repetition": 1,
      "arm": "indexpilot",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.53945,
        "median_ms": 0.52,
        "p95_ms": 0.612,
        "tps": 1848.924388,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "fb698939-eea9-4652-a32e-497ef521caa4",
      "repetition": 1,
      "arm": "indexpilot",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.11407,
        "median_ms": 0.103,
        "p95_ms": 0.151,
        "tps": 8685.079034,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "afe244d7-01c3-47e3-a150-98e15bcffbd3",
      "repetition": 1,
      "arm": "indexpilot",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.21467,
        "median_ms": 2.0895,
        "p95_ms": 3.025,
        "tps": 450.733682,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 122880
      }
    },
    {
      "id": "3547d08f-0c55-404d-8e43-8c339e7aa3e8",
      "repetition": 1,
      "arm": "per_query",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.379075,
        "median_ms": 2.343,
        "p95_ms": 2.802,
        "tps": 419.510599,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2564096,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "72ce7a6d-b258-4077-88ed-2a66b3219d0b",
      "repetition": 1,
      "arm": "per_query",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.295315,
        "median_ms": 2.1559999999999997,
        "p95_ms": 2.879,
        "tps": 434.802458,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 491520
      }
    },
    {
      "id": "eb5146e1-ea26-45b2-8912-f3db2fb80edf",
      "repetition": 1,
      "arm": "per_query",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.11955500000000001,
        "median_ms": 0.106,
        "p95_ms": 0.166,
        "tps": 8290.842764,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "cc02a093-e96d-47b7-8628-4c98be429199",
      "repetition": 1,
      "arm": "per_query",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.14204,
        "median_ms": 0.131,
        "p95_ms": 0.196,
        "tps": 6982.752601,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "77b0868f-97c1-4713-b279-d06cfb1a59d9",
      "repetition": 1,
      "arm": "per_query",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.11116999999999999,
        "median_ms": 0.104,
        "p95_ms": 0.145,
        "tps": 8910.670528,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "5d61746a-1416-4670-828c-3b8412fdb483",
      "repetition": 1,
      "arm": "per_query",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.406515,
        "median_ms": 2.3585000000000003,
        "p95_ms": 3.028,
        "tps": 414.674501,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 43,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 483328
      }
    },
    {
      "id": "44fc0ada-5552-497b-bdeb-bd526c014ab9",
      "repetition": 2,
      "arm": "baseline",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.334035,
        "median_ms": 2.29,
        "p95_ms": 2.74,
        "tps": 427.563295,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2088960,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "bd7f584f-838d-4529-973f-070516bc099a",
      "repetition": 2,
      "arm": "baseline",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.32474,
        "median_ms": 2.2720000000000002,
        "p95_ms": 2.761,
        "tps": 429.318135,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "50f892fc-bda0-4664-95cd-1dae0b7e54fe",
      "repetition": 2,
      "arm": "baseline",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.37406500000000004,
        "median_ms": 0.3065,
        "p95_ms": 0.583,
        "tps": 2664.748048,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "1263e2b8-dbd3-43c9-b8ab-3bc312f7253d",
      "repetition": 2,
      "arm": "baseline",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.546795,
        "median_ms": 0.519,
        "p95_ms": 0.621,
        "tps": 1823.885606,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "8ce63a86-10c3-48f6-a7bf-2a588c4aeb72",
      "repetition": 2,
      "arm": "baseline",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.322855,
        "median_ms": 0.302,
        "p95_ms": 0.381,
        "tps": 3086.27687,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": false,
        "additional_index_bytes": 0,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "329786d8-63fa-4a8a-9ba5-7ede6abd6145",
      "repetition": 2,
      "arm": "baseline",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.23998,
        "median_ms": 2.1624999999999996,
        "p95_ms": 2.615,
        "tps": 445.582164,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2080768,
        "returning_row_checked": true,
        "additional_index_bytes": 0,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 0
      }
    },
    {
      "id": "00f7fcf8-9fa7-4665-8da1-6858ae73dc88",
      "repetition": 2,
      "arm": "indexpilot",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.266635,
        "median_ms": 2.199,
        "p95_ms": 2.674,
        "tps": 440.412226,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2203648,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "be6c5c79-fde8-4060-9a98-c53da3e5f834",
      "repetition": 2,
      "arm": "indexpilot",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.326885,
        "median_ms": 2.2485,
        "p95_ms": 2.916,
        "tps": 428.773258,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 122880
      }
    },
    {
      "id": "c9e339d4-b4e5-431d-bfdd-bce20ba21a3b",
      "repetition": 2,
      "arm": "indexpilot",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.211925,
        "median_ms": 0.1045,
        "p95_ms": 0.565,
        "tps": 4691.091617,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "7e28fad7-4020-444f-a9b0-27718770e45a",
      "repetition": 2,
      "arm": "indexpilot",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.54022,
        "median_ms": 0.518,
        "p95_ms": 0.634,
        "tps": 1847.029054,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "3841b1fd-fd40-48f6-ba15-7df5c1eb4d9f",
      "repetition": 2,
      "arm": "indexpilot",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.11327999999999999,
        "median_ms": 0.102,
        "p95_ms": 0.182,
        "tps": 8748.523687,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": false,
        "additional_index_bytes": 114688,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 114688
      }
    },
    {
      "id": "9567838c-dae7-4942-8b3c-a497de368a74",
      "repetition": 2,
      "arm": "indexpilot",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 11.484490000000001,
        "median_ms": 14.118500000000001,
        "p95_ms": 21.803,
        "tps": 87.005812,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": true,
        "total_index_bytes": 2195456,
        "returning_row_checked": true,
        "additional_index_bytes": 114688,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": true,
        "additional_index_bytes_after": 122880
      }
    },
    {
      "id": "63c98a17-0091-4274-9aa3-32a7afc3f440",
      "repetition": 2,
      "arm": "per_query",
      "phase": "delete",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.285345,
        "median_ms": 2.219,
        "p95_ms": 2.707,
        "tps": 436.790897,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10200,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "bbcc9efb335c86489bbc695fb6102128",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2564096,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; allocate ID; DELETE childless probe order; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "c595f5f7-a48e-4407-b450-5e3d36cc0fca",
      "repetition": 2,
      "arm": "per_query",
      "phase": "insert",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.20854,
        "median_ms": 2.1505,
        "p95_ms": 2.679,
        "tps": 451.943697,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10200,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; INSERT orders with sequence-allocated ID; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 491520
      }
    },
    {
      "id": "8ff672ef-ff43-460b-a81f-52c9c3afa70a",
      "repetition": 2,
      "arm": "per_query",
      "phase": "read_mix",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.12020999999999998,
        "median_ms": 0.105,
        "p95_ms": 0.174,
        "tps": 8239.607795,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "19425541-99a5-45b5-ba96-3cd6e9041b03",
      "repetition": 2,
      "arm": "per_query",
      "phase": "read_q0",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.146085,
        "median_ms": 0.128,
        "p95_ms": 0.216,
        "tps": 6795.555707,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "775201de-7044-4f06-a48a-df1c815e64d8",
      "repetition": 2,
      "arm": "per_query",
      "phase": "read_q1",
      "metrics": {
        "samples": 200,
        "mean_ms": 0.112175,
        "median_ms": 0.104,
        "p95_ms": 0.132,
        "tps": 8840.560492,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": false,
        "additional_index_bytes": 475136,
        "read_warmup_per_client": 20,
        "transaction_definition": "BEGIN READ ONLY; one representative SELECT; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 475136
      }
    },
    {
      "id": "7f888fa1-ee63-4c22-b11d-7ca677f84357",
      "repetition": 2,
      "arm": "per_query",
      "phase": "update",
      "metrics": {
        "samples": 200,
        "mean_ms": 2.15715,
        "median_ms": 2.089,
        "p95_ms": 2.6,
        "tps": 462.75194,
        "latency_unit": "ms",
        "throughput_unit": "transactions_per_second",
        "percentile_method": "nearest_rank_individual_transactions",
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT"
      },
      "conditions": {
        "seed": 44,
        "clients": 1,
        "dataset": {
          "row_counts": {
            "users": 1000,
            "orders": 10000,
            "payments": 10000,
            "products": 500,
            "order_items": 20000,
            "indexpilot_dataset": 1
          },
          "row_hashes": {
            "users": "4d88f41877af888721d5247b1ef737d2",
            "orders": "0f695d4b02fa8611cd4d8ca46a1b3dc5",
            "payments": "cdaf9fd89487e48fb3a6350d6cf6567e",
            "products": "5d9aa9519f067db12fd85c9b0f230081",
            "order_items": "ac717010b855799cd8f6f6e8eba23823",
            "indexpilot_dataset": "2861efbe71a78ab4a7a3b855b8a221c8"
          }
        },
        "threads": 1,
        "protocol": "simple",
        "orders_after": 10000,
        "actual_budget_fit": false,
        "total_index_bytes": 2555904,
        "returning_row_checked": true,
        "additional_index_bytes": 475136,
        "transaction_definition": "BEGIN; UPDATE random positive order user_id to 1/2; COMMIT",
        "actual_budget_fit_after": false,
        "additional_index_bytes_after": 483328
      }
    }
  ],
  "comparisons": [
    {
      "phase": "delete",
      "arm": "per_query",
      "baseline_mean_ms": 2.3826666666666667,
      "mean_ms": 5.00284,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.05305629847938248,
      "repetition_stddev_ms": 4.625904248784772,
      "measured_improvement_pct": -109.96810296586457,
      "regression": true
    },
    {
      "phase": "delete",
      "arm": "indexpilot",
      "baseline_mean_ms": 2.3826666666666667,
      "mean_ms": 2.3480616666666667,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.05305629847938248,
      "repetition_stddev_ms": 0.07289247943603887,
      "measured_improvement_pct": 1.452364297705655,
      "regression": false
    },
    {
      "phase": "insert",
      "arm": "per_query",
      "baseline_mean_ms": 2.3683899999999998,
      "mean_ms": 2.283975,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.047468473485040796,
      "repetition_stddev_ms": 0.07045283475489102,
      "measured_improvement_pct": 3.564235619978129,
      "regression": false
    },
    {
      "phase": "insert",
      "arm": "indexpilot",
      "baseline_mean_ms": 2.3683899999999998,
      "mean_ms": 2.3189266666666666,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.047468473485040796,
      "repetition_stddev_ms": 0.009893220321681447,
      "measured_improvement_pct": 2.0884792341351432,
      "regression": false
    },
    {
      "phase": "read_mix",
      "arm": "per_query",
      "baseline_mean_ms": 0.36042166666666664,
      "mean_ms": 0.12093666666666665,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.018057254313248554,
      "repetition_stddev_ms": 0.0018550089847042001,
      "measured_improvement_pct": 66.4457834110972,
      "regression": false
    },
    {
      "phase": "read_mix",
      "arm": "indexpilot",
      "baseline_mean_ms": 0.36042166666666664,
      "mean_ms": 0.21170166666666668,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.018057254313248554,
      "repetition_stddev_ms": 0.00809731025299966,
      "measured_improvement_pct": 41.26278016952365,
      "regression": false
    },
    {
      "phase": "read_q0",
      "arm": "per_query",
      "baseline_mean_ms": 0.527495,
      "mean_ms": 0.14248,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.024835949750311552,
      "repetition_stddev_ms": 0.003406380043389168,
      "measured_improvement_pct": 72.98931743428848,
      "regression": false
    },
    {
      "phase": "read_q0",
      "arm": "indexpilot",
      "baseline_mean_ms": 0.527495,
      "mean_ms": 0.54151,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.024835949750311552,
      "repetition_stddev_ms": 0.0029266192099417416,
      "measured_improvement_pct": -2.6568972217746234,
      "regression": false
    },
    {
      "phase": "read_q1",
      "arm": "per_query",
      "baseline_mean_ms": 0.3086233333333333,
      "mean_ms": 0.112835,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.023295049009034802,
      "repetition_stddev_ms": 0.002075265043313748,
      "measured_improvement_pct": 63.439251730804536,
      "regression": false
    },
    {
      "phase": "read_q1",
      "arm": "indexpilot",
      "baseline_mean_ms": 0.3086233333333333,
      "mean_ms": 0.11329833333333333,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.023295049009034802,
      "repetition_stddev_ms": 0.0007626652826327763,
      "measured_improvement_pct": 63.28912266300883,
      "regression": false
    },
    {
      "phase": "update",
      "arm": "per_query",
      "baseline_mean_ms": 2.2787016666666666,
      "mean_ms": 2.3153900000000003,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.0477958042963325,
      "repetition_stddev_ms": 0.13756468742013703,
      "measured_improvement_pct": -1.61005426335612,
      "regression": false
    },
    {
      "phase": "update",
      "arm": "indexpilot",
      "baseline_mean_ms": 2.2787016666666666,
      "mean_ms": 5.344295,
      "repetitions": 3,
      "baseline_repetition_stddev_ms": 0.0477958042963325,
      "repetition_stddev_ms": 5.31789803416491,
      "measured_improvement_pct": -134.5324567132892,
      "regression": true
    }
  ],
  "warnings": [
    "Warm-cache measurements are local; no universal speedup is claimed.",
    "TPS/latency describe transactions, not isolated server query execution.",
    "Write probes are controlled orders-table operations, not production write rates.",
    "No WAL or cold-cache measurement; no statistical significance claim.",
    "Per-query union ignores the budget; actual storage fit is reported per arm."
  ],
  "error_code": null
}
```

## Warnings

- Recommendation snapshot: Planner costs and HypoPG bytes are estimates; execution performance is unmeasured\.
- Recommendation snapshot: Greedy search can miss complementary indexes and does not guarantee a global optimum\.
- Recommendation snapshot: Write penalty is a user\-configured heuristic, not measured write latency\.
- Recommendation snapshot: Candidate priority uses query coverage and structural heuristics, not measured benefit\.
- Recommendation snapshot: Storage, planner benefit and write overhead have not been evaluated\.
- Recommendation snapshot: Historical snapshot; current target schema/statistics were not rechecked\.
- Recommendation snapshot: Query contributions describe the final set, not independent index gains\.
- Recommendation snapshot: Execution/write performance is unmeasured; benchmark outcome is unavailable\.
- Frozen historical evidence; current target conditions were not rechecked\.
- Deployment SQL is for review only and was not executed on the monitored target\.
