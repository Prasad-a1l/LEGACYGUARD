from __future__ import annotations

import json
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .analysis import code_chunks
from .config import DATA_DIR
from .db import Incident, KnowledgeItem, SessionLocal

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, PointStruct, VectorParams
except Exception:  # pragma: no cover
    QdrantClient = None  # type: ignore


class VectorIndex:
    _instance: "VectorIndex | None" = None

    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self.vectorizer = TfidfVectorizer(max_features=4096, ngram_range=(1, 2))
        self.matrix = None
        self.qdrant = None

    @classmethod
    def instance(cls) -> "VectorIndex":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def rebuild(self) -> None:
        self.docs = []
        session = SessionLocal()
        try:
            for inc in session.query(Incident).all():
                payload = json.loads(inc.payload_json)
                text = " ".join(
                    [
                        inc.id,
                        inc.service,
                        inc.title,
                        inc.failure,
                        inc.root_cause,
                        inc.resolution,
                        payload.get("summary", ""),
                        payload.get("symptoms", ""),
                        payload.get("error_signature", ""),
                    ]
                )
                self.docs.append(
                    {
                        "id": inc.id,
                        "collection": "incidents",
                        "text": text,
                        "payload": payload,
                        "service": inc.service,
                        "error_signature": payload.get("error_signature", ""),
                        "architecture": payload.get("architecture", {}),
                        "verified": inc.verified,
                    }
                )
            for item in session.query(KnowledgeItem).all():
                self.docs.append(
                    {
                        "id": item.id,
                        "collection": "docs",
                        "text": f"{item.title} {item.body}",
                        "payload": {"title": item.title, "kind": item.kind},
                        "verified": item.verified,
                    }
                )
        finally:
            session.close()

        for chunk in code_chunks():
            self.docs.append(
                {
                    "id": f"code:{chunk['id']}",
                    "collection": "code_chunks",
                    "text": chunk["text"],
                    "payload": chunk,
                    "verified": True,
                }
            )

        self.by_collection: dict[str, list[dict]] = {}
        self.vectorizers: dict[str, TfidfVectorizer] = {}
        self.matrices: dict[str, Any] = {}
        for coll in ("incidents", "docs", "code_chunks"):
            subset = [d for d in self.docs if d["collection"] == coll]
            self.by_collection[coll] = subset
            corpus = [d["text"] for d in subset] or ["empty"]
            vec = TfidfVectorizer(max_features=2048, ngram_range=(1, 2), stop_words="english")
            self.vectorizers[coll] = vec
            self.matrices[coll] = vec.fit_transform(corpus)
        self.vectorizer = self.vectorizers.get("incidents", TfidfVectorizer())
        self.matrix = self.matrices.get("incidents")
        self._try_qdrant()

    def _try_qdrant(self) -> None:
        from .config import QDRANT_ENABLED, QDRANT_URL

        if not QDRANT_ENABLED or QdrantClient is None:
            return
        try:

            client = QdrantClient(url=QDRANT_URL, timeout=2.0)
            client.get_collections()
            dim = self.matrix.shape[1]
            for name in ("incidents", "docs", "code_chunks"):
                try:
                    client.recreate_collection(
                        collection_name=name,
                        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                    )
                except Exception:
                    pass
            points_by = {"incidents": [], "docs": [], "code_chunks": []}
            dense = self.matrix.toarray()
            for i, doc in enumerate(self.docs):
                coll = doc["collection"]
                vec = dense[i].astype(float).tolist()
                points_by[coll].append(
                    PointStruct(id=i, vector=vec, payload={"id": doc["id"], "text": doc["text"][:500]})
                )
            for coll, pts in points_by.items():
                if pts:
                    client.upsert(collection_name=coll, points=pts)
            self.qdrant = client
        except Exception:
            self.qdrant = None

    def search(self, query: str, collection: str | None = None, k: int = 5) -> list[dict]:
        if not self.docs:
            self.rebuild()
        coll = collection or "incidents"
        subset = self.by_collection.get(coll) or [d for d in self.docs if d["collection"] == coll]
        vec = self.vectorizers.get(coll)
        mat = self.matrices.get(coll)
        if vec is None or mat is None or not subset:
            return []
        sims = cosine_similarity(vec.transform([query]), mat)[0]
        ranked = np.argsort(-sims)
        out = []
        for idx in ranked[:k]:
            out.append({**subset[idx], "score": float(sims[idx])})
        return out

    def add_verified(self, doc: dict) -> None:
        """Only verified outcomes may enter organizational memory."""
        if not doc.get("verified"):
            return
        self.docs.append(doc)
        self.rebuild()
