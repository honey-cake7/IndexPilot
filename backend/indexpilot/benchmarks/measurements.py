import math
import re
import statistics

from indexpilot.errors import DomainError


def invalid():
    return DomainError(
        "invalid_pgbench_output", "pgbench output is incomplete or unsuccessful.", 503
    )


def parse_log(raw, *, clients, transactions, scripts):
    rows = []
    seen = set()
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 6 or any(not part.isdecimal() for part in parts):
            raise invalid()
        client, sequence, latency, script, epoch, fraction = map(int, parts)
        if not (
            0 <= client < clients
            and 1 <= sequence <= transactions
            and 0 <= script < scripts
            and 0 <= fraction < 1000000
        ):
            raise invalid()
        if (client, sequence) in seen:
            raise invalid()
        seen.add((client, sequence))
        rows.append((client, sequence, latency, script))
    if len(rows) != clients * transactions:
        raise invalid()
    return rows


def parse_summary(stdout, expected):
    processed = re.search(r"number of transactions actually processed: (\d+)/(\d+)", stdout)
    failed = re.search(r"number of failed transactions: (\d+)", stdout)
    tps = re.search(r"^tps = ([0-9.]+) \(without initial connection time\)", stdout, re.M)
    if not processed or not failed or not tps:
        raise invalid()
    if tuple(map(int, processed.groups())) != (expected, expected) or int(failed[1]) != 0:
        raise invalid()
    value = float(tps[1])
    if not math.isfinite(value) or value <= 0:
        raise invalid()
    return value


def statistics_ms(rows):
    values = sorted(row[2] / 1000 for row in rows)
    if not values:
        return {"samples": 0, "mean_ms": None, "median_ms": None, "p95_ms": None}
    return dict(
        samples=len(values),
        mean_ms=statistics.fmean(values),
        median_ms=statistics.median(values),
        p95_ms=values[math.ceil(0.95 * len(values)) - 1],
    )


def compare(measurements, threshold):
    comparisons = []
    phases = sorted({row["phase"] for row in measurements})
    for phase in phases:
        baseline = [
            row["metrics"]["mean_ms"]
            for row in measurements
            if row["arm"] == "baseline" and row["phase"] == phase
        ]
        for arm in ("per_query", "indexpilot"):
            values = [
                row["metrics"]["mean_ms"]
                for row in measurements
                if row["arm"] == arm and row["phase"] == phase
            ]
            if len(baseline) != len(values) or not baseline:
                raise invalid()
            before, after = statistics.fmean(baseline), statistics.fmean(values)
            improvement = 100 * (1 - after / before) if before > 0 else None
            comparisons.append(
                dict(
                    phase=phase,
                    arm=arm,
                    baseline_mean_ms=before,
                    mean_ms=after,
                    repetitions=len(values),
                    baseline_repetition_stddev_ms=statistics.stdev(baseline)
                    if len(baseline) > 1
                    else None,
                    repetition_stddev_ms=statistics.stdev(values) if len(values) > 1 else None,
                    measured_improvement_pct=improvement,
                    regression=(after > before * (1 + threshold / 100)) if before > 0 else None,
                )
            )
    return comparisons
