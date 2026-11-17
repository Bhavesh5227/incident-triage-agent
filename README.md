# Self-Reflective Enterprise RAG & Incident Triage Agent

Autonomous incident-response agent built with **LangGraph**, **Qdrant (Hybrid BM25 + Dense Search)**, **FastAPI**, and **Arize Phoenix**.

## Quickstart (Docker)
```bash
docker build -t incident-triage-agent:v1 .
docker run -p 8080:8080 --env-file .env incident-triage-agent:v1
