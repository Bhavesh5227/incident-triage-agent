import os
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_TELEMETRY_INITIALIZED = False


def init_telemetry():
    global _TELEMETRY_INITIALIZED
    if _TELEMETRY_INITIALIZED:
        return

    if os.getenv("ENABLE_PHOENIX", "true").lower() == "true":
        endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://127.0.0.1:6006/v1/traces")
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(tracer_provider)

    LangChainInstrumentor().instrument()
    _TELEMETRY_INITIALIZED = True


def estimate_groq_cost(input_tokens: int, output_tokens: int) -> float:
    return round((input_tokens * 0.59e-6) + (output_tokens * 0.79e-6), 6)
