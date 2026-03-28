# Spike Findings — ids_ml_new-yyi

## Question

Can v1 implement a micro-batch runner with only existing Python dependencies such that mixed valid/invalid flow events do not stall the pipeline, and the runner always flushes the last partial batch on shutdown/end-of-stream?

## Result

YES

## Findings

- A JSONL-based micro-batch runner is feasible with the current Python stack; no new dependency is required for the v1 proof path.
- Mixed input can be handled safely if batch assembly is separated from record validation and the runner flushes valid records while quarantining invalid ones inside the same batch cycle.
- Final partial batches can be preserved by forcing a drain on end-of-stream or shutdown before process exit.
- Deterministic behavior is achievable when the runner uses explicit `max_batch_size` and `flush_interval_seconds` controls.

## Operational Constraints

- Validation must happen per record before model scoring.
- Flush must trigger on either `max_batch_size`, timer expiry, or explicit end-of-stream/shutdown.
- Shutdown handling must always attempt one final drain of buffered valid records.
- Invalid records must not block valid records in the same buffered window.
- The first implementation should stay on `stdin`/file-path JSONL input to keep the runtime deterministic and locally testable.

## Why This Is Sufficient

An inline proof showed a mixed batch preserving valid records, quarantining invalid records, and flushing the trailing partial batch. The remaining work is implementation detail, not feasibility risk.
