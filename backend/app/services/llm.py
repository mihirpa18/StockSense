from mistralai.client import Mistral
from app.config import settings
from typing import List, Dict, Optional
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

client = Mistral(api_key=settings.mistral_api_key)
# We can use mistral-small-latest or open-mistral-nemo for fast RAG responses
MODEL = "mistral-small-latest"

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

@traceable(
    name="Get RAG Answer",
    run_type="llm",
    metadata={"ls_provider": "mistral", "ls_model_name": MODEL}
)
def get_rag_answer(question: str, chunks: List[Dict], history: List[dict] = None) -> str:
    """
    Sends the question + retrieved chunks + recent history to Gemini Flash.
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

    response = client.chat.complete(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Log token usage to LangSmith
    current_run = get_current_run_tree()
    if current_run and response.usage:
        current_run.set(usage_metadata={
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        })
        
    return response.choices[0].message.content

@traceable(
    name="Get Thesis Review",
    run_type="llm",
    metadata={"ls_provider": "mistral", "ls_model_name": MODEL}
)
def get_thesis_review(thesis: Dict, chunks: List[Dict], web_results: List[Dict] = None) -> Dict:
    """
    Compares the user's thesis assumptions against retrieved document chunks and/or web search results.
    Returns structured JSON matching the ReviewResult schema.
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
- "invalidated": report or web source clearly contradicts this assumption

Respond ONLY with valid JSON in this exact format:
{{
  "summary": "2-3 sentence overall thesis health assessment",
  "assumptions": [
    {{
      "assumption": "brief label of the assumption",
      "status": "supported|weakening|invalidated",
      "evidence": "specific evidence from context with page reference or web source title",
      "source_page": <page number as integer, or null if from web search>
    }}
  ]
}}"""

    response = client.chat.complete(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Log token usage to LangSmith
    current_run = get_current_run_tree()
    if current_run and response.usage:
        current_run.set(usage_metadata={
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        })
        
    import json
    # Strip markdown code fences if present
    text = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(text)

@traceable(
    name="Generate Thesis Draft",
    run_type="llm",
    metadata={"ls_provider": "mistral", "ls_model_name": MODEL}
)
def generate_thesis_draft(chunks: List[Dict], web_results: List[Dict], company_name: str, ticker: str) -> Dict:
    """
    Generates an initial thesis draft (why_interested, key_risks, expected_outcomes)
    based on document chunks and web search results.
    """
    context = build_context_string(chunks, web_results)

    prompt = f"""You are an investment research assistant for StockSense.
Your task is to generate a draft investment thesis for {company_name} ({ticker}) using only the provided document excerpts and web search context.

DOCUMENT EXCERPTS & WEB SEARCH CONTEXT:
{context}

Based on this context, draft an investment thesis containing three sections:
1. "why_interested": Why a retail investor should be interested in this company (its competitive advantages, growth drivers, and market position).
2. "key_risks": The main risks, headwinds, and threats identified for this company.
3. "expected_outcomes": Realistic, expected operational/financial outcomes and indicators that will show if this thesis is playing out (e.g. revenue target, margin improvement, key milestones).

STRICT RULES:
1. Use ONLY the provided document excerpts and web search results. Do not speculate or invent numbers/milestones.
2. Ground all points in direct facts from the context.
3. Keep the tone professional, objective, and retail-investor-friendly.
4. Respond ONLY with a valid JSON object in this exact format (no markdown code blocks, no trailing text):
{{
  "why_interested": "concise, bulleted points of the core opportunities and business drivers",
  "key_risks": "concise, bulleted points of key risks and headwinds",
  "expected_outcomes": "concise, bulleted list of milestones or indicators to track performance"
}}"""

    response = client.chat.complete(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Log token usage to LangSmith
    current_run = get_current_run_tree()
    if current_run and response.usage:
        current_run.set(usage_metadata={
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        })
        
    import json
    try:
        text = response.choices[0].message.content.strip()
        if "```" in text:
            # extract content between code fences
            parts = text.split("```")
            for part in parts:
                part_clean = part.strip()
                if part_clean.startswith("json"):
                    part_clean = part_clean[4:].strip()
                if part_clean.startswith("{") and part_clean.endswith("}"):
                    text = part_clean
                    break
        else:
            # find first '{' and last '}'
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                text = text[start:end+1]
        return json.loads(text)
    except Exception as e:
        return {
            "why_interested": "Failed to auto-draft. Please write manually.",
            "key_risks": "Failed to auto-draft. Please write manually.",
            "expected_outcomes": f"Error parsing LLM response: {str(e)}"
        }
