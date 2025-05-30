# Phoenix Tracing Configuration for Docker Deployment

This guide describes how to enable Phoenix tracing for both the AI-Q Research Assistant and RAG components in a Docker-based deployment.

## Deploy Phoenix Dashboard

Add the following service to your `deploy/compose/docker-compose.yaml`:

```yaml
services:
  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"  # UI and OTLP HTTP collector
      - "4317:4317"  # OTLP gRPC collector
    networks:
      - nvidia-rag
    profiles: ["aira"]
```

This will deploy a Phoenix server accessible at port 6006.

## Enable Phoenix Tracing in AI-Q Research Assistant

Update the AI-Q Research Assistant configuration file (`aira/configs/config.yml`) to include telemetry settings:

```yaml
general:
  use_uvloop: true

  telemetry:
    logging:
      console:
        _type: console
        level: WARN
    tracing:
      phoenix:
        _type: phoenix
        endpoint: http://phoenix:6006/v1/traces
        project: ai_researcher
```

## Enable Phoenix Tracing in RAG Server

Add the following environment variables to your RAG server deployment:

```yaml
APP_TRACING_OTLPHTTPENDPOINT: "http://phoenix:6006/v1/traces"
APP_TRACING_OTLPGRPCENDPOINT: "grpc://phoenix:4317"
```

Note: You can skip setting the gRPC endpoint (`APP_TRACING_OTLPGRPCENDPOINT`) as Phoenix dashboard is not compatible with OpenTelemetry's metrics export.

## Enable Phoenix Tracing in Ingest Server

Add the following environment variable to your ingest server deployment:

```yaml
OTEL_EXPORTER_OTLP_ENDPOINT: "phoenix:4317"
```

## Troubleshooting

If you encounter pydantic version errors, add `"pydantic==2.10.6"` to your `pyproject.toml`.

## Limitations

Traces from different services appear as separate traces in the dashboard:
- RAG server: "POST /generate"
- Ingest server: "http-submit-job"
- AgentIQ: function names (e.g., "generate_queries", "generate_summary")

This is being addressed with distributed tracing implementation.

