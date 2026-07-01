from mistralai.client import Mistral
from app.config import settings
from typing import List
import asyncio
from langsmith import traceable

client = Mistral(api_key=settings.mistral_api_key)

# mistral-embed produces 1024-dimensional vectors!
# Note: You must update your Supabase database schema to vector(1024)
EMBEDDING_MODEL = "mistral-embed"

def get_embedding(text: str) -> List[float]:
    """
    Returns a 1024-dimensional embedding vector for the given text.
    """
    truncated = text[:2000]  # token limit safety
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        inputs=[truncated]
    )
    return response.data[0].embedding

@traceable(name="Get Embeddings Batch", run_type="embedding")
def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Returns a list of 1024-dimensional embedding vectors for the given texts.
    Batching reduces API calls and avoids rate limits.
    """
    truncated_texts = [t[:2000] for t in texts]
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        inputs=truncated_texts
    )
    return [item.embedding for item in response.data]

@traceable(name="Get Query Embedding", run_type="embedding")
def get_query_embedding(text: str) -> List[float]:
    """
    Separate function for query embeddings.
    Mistral-embed doesn't distinguish between document and query tasks,
    so we just call the standard get_embedding logic.
    """
    truncated = text[:2000]
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        inputs=[truncated]
    )
    return response.data[0].embedding
