import sqlite3
from typing import List, TypedDict
from dotenv import load_dotenv
from fastembed import SparseTextEmbedding, TextEmbedding
from langchain_community.callbacks.manager import get_openai_callback
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models

load_dotenv()

QDRANT_PATH = "data/qdrant_storage"
SQL_PATH = "data/telemetry.db"
COLLECTION_NAME = "enterprise_runbooks"

# Initializing LLM and hybrid embedding encoders once at module load
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
dense_encoder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
sparse_encoder = SparseTextEmbedding(model_name="Qdrant/bm25")

# --- Structured Output Schemas ---
class GradeOutput(BaseModel):
    score: float = Field(description="Relevance score between 0.0 and 1.0")
    reasoning: str = Field(description="Why the retrieved runbooks match or miss the incident")
    rewritten_query:str = Field(description="A sharper technical search query incorporating service names or error codes if score < 0.7")

class RCAOutput(BaseModel):
    root_cause: str = Field(description="Consice technical root cause supported by SQL and runbooks")
    affected_services: List[str]
    remediation_steps: List[str]
    groundedness_score: float = Field(description="Self audit score (0.0 to 1.0) measuring how strictly every claim is backed by retrived context")

# --- LangGraph Shared State ---
class AgentState(TypedDict):
    incident_alert: str
    search_query: str
    sql_context: str
    retrieved_docs: List[str]
    initial_score: float
    relevance_score: float
    retries: int
    rca_report: dict
    input_tokens: int
    output_tokens: int

# --- Helper & Graph Nodes ---
def _query_sql_telemetry() -> str:
    conn = sqlite3.connect(SQL_PATH)
    metrics = conn.execute("SELECT * FROM service_metrics").fetchall()
    deploys = conn.execute("SELECT * FROM recent_deployments").fetchall()
    conn.close()
    return f"Service Metrics: {metrics}\nRecent Deployments: {deploys}"

def retrieve_node(state: AgentState) -> dict:
    query = state.get("search_query") or state["incident_alert"]
    sql_context = state.get("sql_context") or _query_sql_telemetry()

    dense_q = next(dense_encoder.embed([query])).tolist()
    sparse_q = next(sparse_encoder.embed([query])).as_object()

    client = QdrantClient(path=QDRANT_PATH)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(query=dense_q, using="dense", limit=4),
            models.Prefetch(query=models.SparseVector(**sparse_q), using="sparse", limit=4),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=2,
    )
    docs = [f"[{p.payload['source']}] {p.payload['document']}" for p in results.points]
    client.close()

    return {
        "search_query": query,
        "sql_context": sql_context,
        "retrieved_docs": docs,
    }

def grade_and_reflect_node(state: AgentState) -> dict:
    grader = llm.with_structured_output(GradeOutput)
    prompt = (
        f"Incident Alert: {state['incident_alert']}\n"
        f"Current Search Query: {state['search_query']}\n"
        f"SQL Telemetry:\n{state['sql_context']}\n\n"
        f"Retrieved Runbooks:\n{chr(10).join(state['retrieved_docs'])}\n\n"
        "Evaluate if the retrieved runbooks directly explain the root cause and fix for this incident. "
        "If the alert is vague (e.g., generic 502 error) and score < 0.7, rewrite the query using specific error codes "
        "or service names spotted in the SQL Telemetry."
    )
    with get_openai_callback() as cb:
        grade: GradeOutput = grader.invoke(prompt)

    retries = state.get("retries", 0)
    initial_score = state.get("initial_score", grade.score)
    next_query = grade.rewritten_query if grade.score < 0.7 else state["search_query"]

    return {
        "initial_score": initial_score,
        "relevance_score": grade.score,
        "search_query": next_query,
        "retries": retries + (1 if grade.score < 0.7 else 0),
        "input_tokens": state.get("input_tokens", 0) + cb.prompt_tokens,
        "output_tokens": state.get("output_tokens", 0) + cb.completion_tokens,
    }

def route_after_grading(state: AgentState) -> str:
    if state["relevance_score"] < 0.7 and state["retries"] <= 2:
        return "retrieve"
    return "generate_rca"

def generate_rca_node(state: AgentState) -> dict:
    generator = llm.with_structured_output(RCAOutput)
    prompt = (
        f"Incident Alert: {state['incident_alert']}\n"
        f"SQL Telemetry:\n{state['sql_context']}\n\n"
        f"Verified Runbooks:\n{chr(10).join(state['retrieved_docs'])}\n\n"
        "Produce a precise Root Cause Analysis (RCA) and remediation steps strictly grounded in the evidence above."
    )
    with get_openai_callback() as cb:
        rca: RCAOutput = generator.invoke(prompt)

    return {
        "rca_report": rca.model_dump(),
        "input_tokens": state.get("input_tokens", 0) + cb.prompt_tokens,
        "output_tokens": state.get("output_tokens", 0) + cb.completion_tokens,
    }


# --- Compile the Graph ---
workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("grade", grade_and_reflect_node)
workflow.add_node("generate_rca", generate_rca_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade")
workflow.add_conditional_edges(
    "grade",
    route_after_grading,
    {"retrieve": "retrieve", "generate_rca": "generate_rca"},
)
workflow.add_edge("generate_rca", END)

triage_agent = workflow.compile()