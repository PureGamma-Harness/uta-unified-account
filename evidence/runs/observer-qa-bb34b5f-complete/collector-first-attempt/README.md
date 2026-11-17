# Collector error, not a product result

The first report-only archive collector expected `testsRun`/`successful` fields. The actual installed report has `run`, `failures`, `errors`, and `skipped`. It stopped before writing any archive members. The corrected collector checks the complete actual field mapping and wrote the separate complete archive. It did not rerun CI, SQL, services or tests. This transcription records the terminal exception; the original terminal output remains in the session history.
