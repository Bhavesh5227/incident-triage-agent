import time
from fastapi import FastAPI
from pydantic import BaseModel
from app.graph import triage_agent
from app.telemetry import estimate_groq_cost, init_telemetry

init_telemetry()

app = FastAPI(
    title="Self-Reflective Enterprise Incident Triage Agent",
    description="Hybrid RAG + SQL Telemetry + LangGraph Self-Reflection",
    version="1.0.0",
)


class IncidentRequest(BaseModel):
    alert: str = "Checkout page is throwing 502 Bad Gateway errors for customers"


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/triage")
def triage_incident(req: IncidentRequest):
    start_time = time.perf_counter()

    result = triage_agent.invoke(
        {
            "incident_alert": req.alert,
            "retries": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
    )

    total_latency_sec = max(time.perf_counter() - start_time, 1e-6)
    in_tok = result.get("input_tokens", 0)
    out_tok = result.get("output_tokens", 0)
    rca = result["rca_report"]

    return {
        "incident_alert": req.alert,
        "final_search_query": result["search_query"],
        "rca": {
            "root_cause": rca["root_cause"],
            "affected_services": rca["affected_services"],
            "remediation_steps": rca["remediation_steps"],
        },
        "telemetry": {
            "retrieval_retries": result["retries"],
            "initial_relevance_score": result["initial_score"],
            "final_relevance_score": result["relevance_score"],
            "groundedness_score": rca["groundedness_score"],
            "end_to_end_latency_ms": round(total_latency_sec * 1000, 2),
            "throughput_tokens_per_sec": round(out_tok / total_latency_sec, 1),
            "estimated_cost_usd": estimate_groq_cost(in_tok, out_tok),
        },
    }