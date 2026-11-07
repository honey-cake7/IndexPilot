import uuid
from datetime import UTC, datetime, timedelta

import pytest
from indexpilot.workloads.deltas import snapshot_delta
from indexpilot.workloads.models import SnapshotView, StatementStats

START = datetime(2026, 1, 1, tzinfo=UTC)
WORKLOAD = uuid.uuid4()


def entry(**changes):
    return StatementStats(
        **dict(
            {
                "identity": "1:2:-3:1",
                "query": "SELECT $1",
                "queryid": -3,
                "userid": 2,
                "dbid": 1,
                "toplevel": True,
                "calls": 10,
                "total_exec_ms": 200,
                "mean_exec_ms": 20,
                "rows": 100,
                "buffers": {"shared_blks_hit": 50},
                "stats_since": START,
            },
            **changes,
        )
    )


def snapshot(second, entries=None, **changes):
    return SnapshotView(
        **dict(
            {
                "id": uuid.uuid4(),
                "workload_id": WORKLOAD,
                "started_at": START + timedelta(seconds=second),
                "observed_at": START + timedelta(seconds=second, milliseconds=1),
                "server_started_at": START,
                "stats_reset": START,
                "dealloc": 0,
                "dbid": 1,
                "extension_version": "1.12",
                "consistent": True,
                "truncated": False,
                "skipped_statements": 0,
                "warnings": [],
                "entries": [entry()] if entries is None else entries,
            },
            **changes,
        )
    )


def test_interval_mean_uses_deltas_not_cumulative_mean():
    result = snapshot_delta(
        snapshot(1),
        snapshot(
            2,
            [
                entry(
                    calls=12,
                    total_exec_ms=210,
                    mean_exec_ms=17.5,
                    rows=106,
                    buffers={"shared_blks_hit": 58},
                )
            ],
        ),
    )
    row = result.entries[0]
    assert row.usable and row.calls == 2 and row.total_exec_ms == 10
    assert row.mean_exec_ms == 5 and row.rows == 6 and row.buffers["shared_blks_hit"] == 8
    assert result.interval_seconds == 1


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"server_started_at": START + timedelta(seconds=1)}, "server_restarted"),
        ({"stats_reset": START + timedelta(seconds=1)}, "statistics_reset"),
        ({"dealloc": 1}, "eviction_ambiguity"),
        ({"extension_version": "1.13"}, "extension_version_changed"),
        ({"dbid": 999}, "database_identity_changed"),
        ({"consistent": False}, "collection_changed_during_read"),
        ({"truncated": True}, "truncated_collection"),
        ({"started_at": START}, "overlapping_or_unordered_collection"),
    ],
)
def test_global_changes_invalidate_interval(changes, reason):
    result = snapshot_delta(snapshot(1), snapshot(2, **changes))
    assert result.entries[0].reason == reason
    assert not result.entries[0].usable and result.entries[0].calls is None
    assert result.interval_seconds is None


def test_zero_calls_does_not_invent_mean():
    row = snapshot_delta(snapshot(1), snapshot(2)).entries[0]
    assert row.usable and row.calls == 0 and row.mean_exec_ms is None


def test_first_new_and_missing_entries_have_no_invented_history():
    first = snapshot_delta(None, snapshot(1)).entries[0]
    assert first.reason == "baseline_required" and first.calls is None
    new = snapshot_delta(snapshot(1, []), snapshot(2)).entries[0]
    assert new.reason == "new_entry_without_baseline" and new.calls is None
    missing = snapshot_delta(snapshot(1), snapshot(2, [])).entries[0]
    assert missing.reason == "entry_missing"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"stats_since": START + timedelta(seconds=1)}, "entry_reset"),
        ({"calls": 1}, "counter_decreased"),
        ({"buffers": {"shared_blks_hit": 1}}, "counter_decreased"),
        ({"total_exec_ms": 201}, "inconsistent_counters"),
        ({"buffers": {}}, "buffer_metrics_changed"),
    ],
)
def test_entry_resets_and_counter_anomalies(changes, reason):
    row = snapshot_delta(snapshot(1), snapshot(2, [entry(**changes)])).entries[0]
    assert row.reason == reason and not row.usable


def test_incompatible_workloads_are_not_compared():
    with pytest.raises(ValueError):
        snapshot_delta(snapshot(1), snapshot(2, workload_id=uuid.uuid4()))


def test_queryid_survives_json_without_javascript_precision_loss():
    queryid = -(2**63) + 123
    original = entry(queryid=queryid)
    encoded = original.model_dump(mode="json")
    assert encoded["queryid"] == str(queryid)
    assert StatementStats.model_validate(encoded).queryid == queryid


def test_adjacent_collection_boundaries_are_comparable():
    previous = snapshot(1)
    current = snapshot(2, started_at=previous.observed_at)
    assert snapshot_delta(previous, current).entries[0].usable
