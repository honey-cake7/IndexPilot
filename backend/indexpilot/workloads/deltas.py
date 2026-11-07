"""Counter arithmetic independent of PostgreSQL connections and HTTP routes."""

from indexpilot.workloads.models import DeltaEntry, SnapshotDelta, SnapshotView


def snapshot_delta(previous: SnapshotView | None, current: SnapshotView) -> SnapshotDelta:
    warnings = []
    global_reason = None
    interval = None
    if previous is None:
        global_reason = "baseline_required"
    else:
        if previous.workload_id != current.workload_id:
            raise ValueError("Cannot compare snapshots from different workloads")
        interval = (current.observed_at - previous.observed_at).total_seconds()
        if interval <= 0 or previous.observed_at > current.started_at:
            global_reason = "overlapping_or_unordered_collection"
        elif previous.dbid != current.dbid:
            global_reason = "database_identity_changed"
        elif previous.server_started_at != current.server_started_at:
            global_reason = "server_restarted"
        elif previous.extension_version != current.extension_version:
            global_reason = "extension_version_changed"
        elif previous.stats_reset != current.stats_reset:
            global_reason = "statistics_reset"
        elif previous.dealloc != current.dealloc:
            global_reason = "eviction_ambiguity"
    if not current.consistent or (previous and not previous.consistent):
        global_reason = "collection_changed_during_read"
    if current.truncated or (previous and previous.truncated):
        global_reason = "truncated_collection"
    if global_reason:
        warnings.append(global_reason)
    old = {row.identity: row for row in previous.entries} if previous else {}
    new = {row.identity: row for row in current.entries}
    entries = []
    for identity in sorted(old.keys() | new.keys()):
        before, after = old.get(identity), new.get(identity)
        reason = global_reason
        if reason is None:
            if after is None:
                reason = "entry_missing"
            elif before is None:
                reason = "new_entry_without_baseline"
            elif before.stats_since != after.stats_since:
                reason = "entry_reset"
            elif before.buffers.keys() != after.buffers.keys():
                reason = "buffer_metrics_changed"
        if reason is not None:
            entries.append(DeltaEntry(identity=identity, usable=False, reason=reason))
            continue
        calls, total, rows = (
            after.calls - before.calls,
            after.total_exec_ms - before.total_exec_ms,
            after.rows - before.rows,
        )
        buffers = {name: value - before.buffers[name] for name, value in after.buffers.items()}
        if min(calls, total, rows, *buffers.values()) < 0:
            entries.append(DeltaEntry(identity=identity, usable=False, reason="counter_decreased"))
        elif calls == 0 and (total > 0 or rows > 0 or any(buffers.values())):
            entries.append(
                DeltaEntry(identity=identity, usable=False, reason="inconsistent_counters")
            )
        else:
            entries.append(
                DeltaEntry(
                    identity=identity,
                    usable=True,
                    calls=calls,
                    total_exec_ms=total,
                    mean_exec_ms=total / calls if calls else None,
                    rows=rows,
                    buffers=buffers,
                )
            )
    return SnapshotDelta(
        previous_id=previous.id if previous else None,
        current_id=current.id,
        interval_seconds=interval if not global_reason else None,
        entries=entries,
        warnings=warnings,
    )
