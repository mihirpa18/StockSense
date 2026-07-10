import asyncio
import os
import sys

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.llm import get_thesis_review
from app.services.web_researcher import search_web

async def test_modes():
    thesis = {
        "why_interested": "Expanding electric vehicle market share in India",
        "expected_outcomes": "TATAMOTORS EBITDA margin hits 10%",
        "key_risks": "High battery components cost"
    }
    
    print("Testing search_web execution...")
    # DuckDuckGo search for Tata Motors EV battery market share
    results = search_web("TATAMOTORS EV battery market share", max_results=2)
    print(f"Retrieved {len(results)} results.")
    for idx, r in enumerate(results):
        print(f"[{idx+1}] Title: {r.get('title')}")
        print(f"    Snippet: {r.get('snippet')[:100]}...")
    assert len(results) > 0, "Web search failed to return any results"

    print("\nTesting LLM Thesis Review Generation with Web Results...")
    review = get_thesis_review(thesis, chunks=[], web_results=results)
    print("Review output:")
    print(review)
    assert "summary" in review
    assert len(review["assumptions"]) > 0
    print("\nAll Backend Modes verified successfully!")

if __name__ == "__main__":
    asyncio.run(test_modes())
