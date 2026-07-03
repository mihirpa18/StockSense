from langchain_mistralai import ChatMistralAI
from app.config import settings
from app.models.schemas import ReviewResult, ThesisDraft
from typing import List, Dict, Optional
from langsmith import traceable

# We can use mistral-small-latest or open-mistral-nemo for fast RAG responses
MODEL = "mistral-small-latest"

# .with_retry() wraps every call with exponential backoff + jitter, retrying on any exception
# (including 429s) up to 3 attempts total — Mistral calls previously had no retry handling at
# all, unlike the yfinance retry-with-backoff pattern elsewhere in this codebase.
_base_llm = ChatMistralAI(model=MODEL, api_key=settings.mistral_api_key, temperature=0.7)
_retry_kwargs = dict(stop_after_attempt=3, wait_exponential_jitter=True)
llm = _base_llm.with_retry(**_retry_kwargs)

# Structured-output variants: these force the model to return data matching the given
# Pydantic schema (via Mistral's native tool-calling), instead of us asking for "valid JSON"
# in the prompt and then hand-parsing/repairing the response text.
# with_structured_output() must be called on the base model (RunnableRetry doesn't expose it),
# then the resulting runnable is wrapped with retry.
review_llm = _base_llm.with_structured_output(ReviewResult).with_retry(**_retry_kwargs)
draft_llm = _base_llm.with_structured_output(ThesisDraft).with_retry(**_retry_kwargs)

RAG_SYSTEM_PROMPT = """You are an investment research assistant for StockSense.
You help retail investors understand companies by answering questions about uploaded documents.

STRICT RULES:
1. Answer ONLY using information from the provided document excerpts below.
2. If the answer is not in the excerpts, say "I couldn't find information about this in the uploaded documents."
3. Always cite which excerpt(s) you used by mentioning the page number: e.g. "(Page 47)"
4. Be concise and factual. Do not speculate beyond what the documents say.
5. Use bullet points for lists of risks, growth drivers, or multiple points.
6. Never make up financial figures — only quote numbers directly from the excerpts.
7. When excerpts from MULTIPLE documents contain conflicting data (e.g. different revenue figures),
   ALWAYS prefer the most recent document. State which document you are citing and its fiscal year.
8. If asked about "current" or "latest" figures, use ONLY the most recent document's excerpts.
"""

def build_context_string(chunks: List[Dict], web_results: List[Dict] = None) -> str:
    """Format retrieved chunks and web search results into a readable context block."""
    context_parts = []
    if chunks:
        for i, chunk in enumerate(chunks, 1):
            doc_label = chunk.get('document_name', 'Unknown Document')
            fiscal_yr = chunk.get('fiscal_year', '')
            fiscal_tag = f" ({fiscal_yr})" if fiscal_yr else ""
            context_parts.append(
                f"[Excerpt {i} — {doc_label}{fiscal_tag} — Page {chunk.get('page_number', '?')}]\n{chunk['content']}"
            )
    if web_results:
        for i, item in enumerate(web_results, 1):
            title = item.get("title", "Web Source")
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            context_parts.append(
                f"[Web Source {i} — {title} — URL: {url}]\n{snippet}"
            )
    return "\n\n---\n\n".join(context_parts)

@traceable(name="Get RAG Answer", run_type="chain")
def get_rag_answer(question: str, chunks: List[Dict], history: List[dict] = None) -> str:
    """
    Sends the question + retrieved chunks + recent history to Mistral.
    Returns the model's answer string.
    """
    context = build_context_string(chunks)

    # Take only the last 4 messages to prevent context exhaustion
    recent_history = ""
    if history:
        last_few = history[-4:]
        for msg in last_few:
            role = "USER" if msg.get("role") == "user" else "ASSISTANT"
            recent_history += f"{role}: {msg.get('content', '')}\n"

    prompt = f"""{RAG_SYSTEM_PROMPT}

DOCUMENT EXCERPTS:
{context}

RECENT CONVERSATION HISTORY:
{recent_history if recent_history else "No previous history."}

USER QUESTION: {question}

ANSWER:"""

    response = llm.invoke(prompt)
    return response.content

@traceable(name="Get Thesis Review", run_type="chain")
def get_thesis_review(thesis: Dict, chunks: List[Dict], web_results: List[Dict] = None) -> Dict:
    """
    Compares the user's thesis assumptions against retrieved document chunks and/or web search results.
    Returns a dict matching the ReviewResult schema, guaranteed valid by LangChain's structured output
    (no more manual JSON parsing / code-fence stripping).
    """
    context = build_context_string(chunks, web_results)

    prompt = f"""You are reviewing an investor's thesis against reports and/or web search news articles.

INVESTOR'S THESIS:
Why interested: {thesis.get('why_interested')}
Expected outcomes: {thesis.get('expected_outcomes')}
Key risks identified: {thesis.get('key_risks')}

CONTEXT EXCERPTS (Documents and/or Web Articles):
{context}

Analyse each assumption in the thesis against the report and web evidence.
For each assumption, determine status:
- "supported": evidence in the report or web source confirms this assumption
- "weakening": partial evidence or contradictory signals
- "invalidated": report or web source clearly contradicts this assumption"""

    result: ReviewResult = review_llm.invoke(prompt)
    return result.model_dump()

@traceable(name="Generate Thesis Draft", run_type="chain")
def generate_thesis_draft(chunks: List[Dict], web_results: List[Dict], company_name: str, ticker: str) -> Dict:
    """
    Generates an initial thesis draft (why_interested, key_risks, expected_outcomes)
    based on document chunks and web search results. Returns a dict matching the ThesisDraft
    schema, guaranteed valid by LangChain's structured output.
    """
    context = build_context_string(chunks, web_results)

    prompt = f"""You are an investment research assistant for StockSense.
Your task is to generate a draft investment thesis for {company_name} ({ticker}) using only the provided document excerpts and web search context.

DOCUMENT EXCERPTS & WEB SEARCH CONTEXT:
{context}

Based on this context, draft an investment thesis containing three sections: why a retail investor
should be interested, the main risks/headwinds, and realistic expected outcomes/milestones to track.

STRICT RULES:
1. Use ONLY the provided document excerpts and web search results. Do not speculate or invent numbers/milestones.
2. Ground all points in direct facts from the context.
3. Keep the tone professional, objective, and retail-investor-friendly."""

    result: ThesisDraft = draft_llm.invoke(prompt)
    return result.model_dump()
