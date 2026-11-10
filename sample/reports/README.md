# Actual saved report export

[local-report.json](local-report.json) and [local-report.md](local-report.md) are the backend's actual JSON/Markdown downloads for report `237c2186-be58-474c-b21d-a3d7369ca80d`, format `indexpilot-report-v1`. They were created from recommendation `74790511-99fe-4452-973c-df9eb247f670` and completed benchmark `38ced867-7cfc-429f-9a3a-bc4ee90e51d6`.

These retain the published M9 experiment: two queries at frequencies 100/25, 10,000 orders, seed 42, three rotated repetitions, one client, 200 transactions per phase, 54 measurements and 10,800 underlying transaction samples. The report contains measurement summaries/conditions and identifiers; individual transaction rows stay in metadata. It preserves the read/write regressions and variability documented in [the benchmark example](../benchmarks/README.md). It is not a new performance experiment.

Sanitization is the report's explicit field projection and saved inclusion policy: original sample SQL is included, representative bound SQL, typed parameter maps and raw plans are omitted. Connection credentials/hosts/raw connection settings are not exported. Local UUIDs, measured values, original sample literals, timestamps and units remain actual evidence, not invented replacements. The local report was also saved in metadata and remains available after application restart.

This sample is historical evidence, not a promise of performance on another system. Refer to [REPORTS.md](../../docs/REPORTS.md) for format, API, privacy policy and limitations.
