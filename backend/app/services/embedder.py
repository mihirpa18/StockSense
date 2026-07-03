import tiktoken
from langchain_mistralai import MistralAIEmbeddings
from app.config import settings
from app.utils.logger import logger
from typing import List
from langsmith import traceable
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception, before_sleep_log
import logging

# mistral-embed produces 1024-dimensional vectors!
# Note: You must update your Supabase database schema to vector(1024)
EMBEDDING_MODEL = "mistral-embed"
MAX_INPUT_TOKENS = 8000  # mistral-embed's context limit is 8192; leave headroom

embeddings_client = MistralAIEmbeddings(model=EMBEDDING_MODEL, api_key=settings.mistral_api_key)

# Same tokenizer used in chunker.py. Not Mistral's exact tokenizer, but a close-enough
# approximation for a safety truncation — the goal is just to never silently clip a chunk
# whose content is well under the limit, which the previous text[:2000] (character-based)
# truncation could do since 500-token chunks can exceed 2000 characters.
_enc = tiktoken.get_encoding("cl100k_base")

def _truncate_to_tokens(text: str, max_tokens: int = MAX_INPUT_TOKENS) -> str:
    tokens = _enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _enc.decode(tokens[:max_tokens])

def _is_rate_limit_or_transient(exc: BaseException) -> bool:
    """Retry on 429 / rate-limit / transient network errors, not on auth or bad-input errors."""
    msg = str(exc).lower()
    return any(term in msg for term in ["429", "rate limit", "too many requests", "timeout", "timed out", "connection"])

_retry_config = dict(
    retry=retry_if_exception(_is_rate_limit_or_transient),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=15),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

@retry(**_retry_config)
def get_embedding(text: str) -> List[float]:
    """
    Returns a 1024-dimensional embedding vector for the given text.
    """
    truncated = _truncate_to_tokens(text)
    return embeddings_client.embed_documents([truncated])[0]

@traceable(name="Get Embeddings Batch", run_type="embedding")
@retry(**_retry_config)
def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Returns a list of 1024-dimensional embedding vectors for the given texts.
    Batching reduces API calls and avoids rate limits.
    Retries with exponential backoff on 429 / transient errors (up to 3 attempts).
    """
    truncated_texts = [_truncate_to_tokens(t) for t in texts]
    return embeddings_client.embed_documents(truncated_texts)

@traceable(name="Get Query Embedding", run_type="embedding")
@retry(**_retry_config)
def get_query_embedding(text: str) -> List[float]:
    """
    Separate function for query embeddings.
    Mistral-embed doesn't distinguish between document and query tasks,
    so embed_query() and embed_documents() are functionally equivalent here.
    """
    truncated = _truncate_to_tokens(text)
    return embeddings_client.embed_query(truncated)
