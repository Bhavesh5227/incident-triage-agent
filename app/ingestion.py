import glob
import os
import sqlite3
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient, models

QDRANT_PATH = "data/qdrant_storage"
SQL_PATH = "data/telemetry.db"
COLLECTION_NAME = "enterprise_runbooks"
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"


def build_sql_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(SQL_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS service_metrics")
    cur.execute("DROP TABLE IF EXISTS recent_deployments")

    cur.execute(
        """
        CREATE TABLE service_metrics(
            service TEXT PRIMARY KEY,
            error_rate_pct REAL,
            p99_latency_ms INTEGER,
            status TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE recent_deployments(
            service TEXT,
            version TEXT,
            deployed_mins_ago INTEGER,
            author TEXT
        )
        """
    )

    cur.executemany(
        "INSERT INTO service_metrics VALUES (?, ?, ?, ?)",
        [
            ("payment-service", 18.4, 4200, "CRITICAL_ERR_PG_53300"),
            ("checkout-api", 12.1, 3100, "DEGRADED_UPSTREAM_TIMEOUT"),
            ("recommendation-worker", 9.8, 1850, "WARN_EXIT_CODE_137"),
            ("catalog-service", 4.3, 940, "WARN_ERR_REDIS_OOM"),
            ("order-fulfillment-consumer", 6.5, 5100, "DEGRADED_CONSUMER_LAG"),
            ("auth-service", 0.2, 45, "HEALTHY"),
        ],
    )

    cur.executemany(
        "INSERT INTO recent_deployments VALUES (?, ?, ?, ?)",
        [
            ("payment-service", "v2.14.2", 8, "ci-deploy-bot"),
            ("recommendation-worker", "v4.1.0", 22, "ci-deploy-bot"),
            ("catalog-service", "v3.8.1", 45, "ci-deploy-bot"),
            ("order-fulfillment-consumer", "v1.12.0", 190, "ci-deploy-bot"),
            ("auth-service", "v1.9.0", 1440, "ci-deploy-bot"),
        ],
    )

    conn.commit()
    conn.close()
    print(f"✅ Built SQLite telemetry DB at {SQL_PATH}")


def build_vector_store():
    dense_encoder = TextEmbedding(model_name=DENSE_MODEL)
    sparse_encoder = SparseTextEmbedding(model_name=SPARSE_MODEL)

    client = QdrantClient(path=QDRANT_PATH)
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    # Create a Hybrid Collection supporting both Dense (384-dim BGE) and Sparse (BM25) vectors
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(size=384, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )

    docs, sources = [], []
    for filepath in sorted(glob.glob("data/runbooks/*.md")):
        with open(filepath, "r", encoding="utf-8") as f:
            docs.append(f.read())
            sources.append(os.path.basename(filepath))

    dense_vectors = list(dense_encoder.embed(docs))
    sparse_vectors = list(sparse_encoder.embed(docs))

    points = [
        models.PointStruct(
            id=idx,
            vector={
                "dense": dense_vectors[idx].tolist(),
                "sparse": sparse_vectors[idx].as_object(),
            },
            payload={"document": docs[idx], "source": sources[idx]},
        )
        for idx in range(len(docs))
    ]

    client.upsert(collection_name=COLLECTION_NAME, points=points)
    client.close()
    print(f"✅ Indexed {len(docs)} runbooks into Qdrant Hybrid Store at {QDRANT_PATH}")


if __name__ == "__main__":
    build_sql_db()
    build_vector_store()
