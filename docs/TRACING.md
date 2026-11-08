# Tracing

Every request leaves a trace: one timeline showing where the time went.

```
http.request  POST /chat                         9.8 s
├─ agent.corrector                               0.4 s
├─ retrieval.search                              0.1 s
├─ retrieval.rerank                              0.3 s
├─ llm.chat  (answerer)                          6.9 s
└─ llm.chat  (validator)                         1.9 s
```

Background uploads appear as their own `ingest.job` traces. Every response carries an `X-Trace-ID` header and
every request log line has the same `trace_id`, so a log line can be matched to its trace.

## Turn it on

Off by default (no cost, no network). To see traces locally:

```bash
docker compose -f docker-compose.tracing.yml up -d
echo "OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318" >> .env
# restart the app, ask a question, then open http://localhost:16686 and pick service "enterprise-knowledge-ai"
```

No Docker? Set `OTEL_CONSOLE=true` and spans print as JSON lines in the server terminal.

| Setting | Meaning |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Where to send spans (OTLP over HTTP). Empty = off. |
| `OTEL_EXPORTER_OTLP_HEADERS` | `key=value,key2=value2`, for a hosted backend that needs a token. |
| `OTEL_SERVICE_NAME` | Defaults to `enterprise-knowledge-ai`. |
| `OTEL_CONSOLE` | Print spans instead of, or as well as, sending them. |

## What a span may contain

Only ids, counts, status codes, model names and timings. **Never** a question, an answer, document text, a name or an
email: `tracing.safe_attributes` drops attributes with content-like names (`question`, `answer`, `text`, `content`,
`detail`, `prompt`, `email`, `name`, `query`, `title`, `body`) and anything that is not a number, a boolean or a short string.
The audit log keeps the agent step text for administrators; traces do not.

## Design notes

- The tracer is small and lives in `app/tracing.py`. It sends the standard OTLP/JSON format, so Jaeger, Grafana Tempo,
  or Azure Monitor through an OpenTelemetry Collector can read it. It does not use the OpenTelemetry SDK because the SDK's
  protobuf requirement conflicts with this project's pinned dependencies. Swapping in the SDK later would touch only that file.
- Spans are sent in batches by a background thread. If the backend is down or slow, spans are dropped (the queue is bounded);
  tracing never slows or breaks a request.
- The trace context travels across `await` points automatically. It does not cross process boundaries yet (the web process
  and the worker process each start their own traces).

## Known limits

- Tested: privacy filter, span linking, OTLP shape, off-switch (`tests/test_tracing.py`). Not tested against a live backend
  other than Jaeger locally.
- No sampling: every request is traced when tracing is on. For a busy deployment, sample in the collector.
