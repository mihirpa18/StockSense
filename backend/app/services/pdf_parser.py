import fitz  # PyMuPDF
from typing import List, Dict

def extract_text_by_page(pdf_bytes: bytes) -> List[Dict]:
    """
    Returns a list of dicts: [{page_number: int, text: str}]
    Cleans up hyphenation, extra whitespace, and form-feed characters.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        # Clean up common PDF extraction artifacts
        text = text.replace('\x0c', ' ')   # form feed
        text = text.replace('-\n', '')     # hyphenated line breaks
        text = text.replace('\n', ' ')     # normalize newlines
        text = ' '.join(text.split())      # collapse whitespace
        if len(text.strip()) > 50:         # skip nearly-empty pages
            pages.append({
                "page_number": page_num + 1,  # 1-indexed for human readability
                "text": text.strip()
            })
    doc.close()
    return pages
