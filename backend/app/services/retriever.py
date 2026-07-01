from app.db.supabase import get_supabase
from app.services.embedder import get_query_embedding
from typing import List, Dict, Optional
from langsmith import traceable

TOP_K = 5  # retrieve top 5 most similar chunks

# WHY TOP_K = 5:
# Too few (1-2): Not enough context, AI may miss the answer
# Too many (10+): Context window fills up, irrelevant chunks dilute the answer
# 5 is the standard starting point — retrieves ~2500 tokens of context

@traceable(name="Retrieve Relevant Chunks", run_type="retriever")
def retrieve_relevant_chunks(
    question: str,
    company_id: str,
    user_id: str,
    document_id: Optional[str] = None
) -> List[Dict]:
    """
    1. Embed the user question (task_type=retrieval_query)
    2. Run cosine similarity search against chunks for this company + user
    3. Optionally scope to a single document (critical for thesis review)
    4. Return top-k chunks ordered by similarity

    IMPORTANT: When document_id is None, chunks from ALL uploaded documents
    for this company are searched. This can cause data contamination if
    multiple reports exist (e.g. FY23 + FY24 chunks mixed together).
    Always pass document_id when reviewing a thesis or when the user
    selects a specific document in the chat UI.
    """
    supabase = get_supabase()
    query_embedding = get_query_embedding(question)

    # pgvector cosine similarity search combined with FTS keyword search (RRF Hybrid Search)
    # We use a raw RPC call because Supabase Python SDK doesn't expose vector/RRF operations directly
    params = {
        "query_embedding": query_embedding,
        "query_text": question,                 # Passed for full-text search index
        "company_id_filter": company_id,
        "user_id_filter": user_id,
        "match_count": TOP_K
    }
    if document_id:
        params["document_id_filter"] = document_id

    result = supabase.rpc("match_chunks", params).execute()

    return result.data if result.data else []
