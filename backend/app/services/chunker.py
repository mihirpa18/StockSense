import tiktoken
from typing import List, Dict

# CHUNKING STRATEGY EXPLANATION (important for interviews):
# Chunk size: 500 tokens
#   - Small enough to represent a single idea/paragraph
#   - Large enough to contain meaningful context
#   - Tested range: 256 (too granular), 512 (good), 1024 (too dilute)
# Overlap: 50 tokens
#   - Prevents losing context at chunk boundaries
#   - If a sentence spans two chunks, both chunks contain it
#   - 10% overlap is the standard starting point

CHUNK_SIZE = 500    # tokens per chunk
OVERLAP    = 50     # overlapping tokens between consecutive chunks

enc = tiktoken.get_encoding("cl100k_base")  # same tokenizer as GPT-4 / Gemini approximation

def chunk_page_texts(pages: List[Dict]) -> List[Dict]:
    """
    Input:  [{page_number, text}]
    Output: [{chunk_index, page_number, content, token_count}]

    Strategy: sliding window over tokens, tracking which page each token came from.
    """
    # Flatten all pages into a single token stream with page tracking
    all_tokens = []
    token_page_map = []   # index i → page_number of token i

    for page in pages:
        tokens = enc.encode(page["text"])
        all_tokens.extend(tokens)
        token_page_map.extend([page["page_number"]] * len(tokens))

    chunks = []
    chunk_index = 0
    start = 0

    while start < len(all_tokens):
        end = min(start + CHUNK_SIZE, len(all_tokens))
        chunk_tokens = all_tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)

        # Assign page number from the first token of this chunk
        page_num = token_page_map[start] if start < len(token_page_map) else 1

        chunks.append({
            "chunk_index":  chunk_index,
            "page_number":  page_num,
            "content":      chunk_text,
            "token_count":  len(chunk_tokens)
        })

        chunk_index += 1
        start += (CHUNK_SIZE - OVERLAP)   # slide forward, leaving overlap behind

    return chunks
