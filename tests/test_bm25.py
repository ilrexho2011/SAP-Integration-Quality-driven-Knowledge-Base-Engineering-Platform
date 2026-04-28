from app.schemas.models import ChunkRecord
from app.services.indexing_service import BM25Index


def test_bm25_retrieves_expected_chunk():
    chunks = [
        ChunkRecord(chunk_id="1", document_id="A", document_type="runbook", title="HTTP 429", text="HTTP 429 receiver throttling retry backoff"),
        ChunkRecord(chunk_id="2", document_id="B", document_type="runbook", title="SFTP", text="SFTP authentication failure"),
    ]
    results = BM25Index().fit(chunks).search("receiver rate limit HTTP 429", top_k=1)
    assert results[0]["document_id"] == "A"
