from docx import Document
from app.analysis.doc_parser import get_paragraph_raw_text
import sys

if len(sys.argv) < 3:
    print('Usage: find_trecho.py <docx> <trecho>')
    sys.exit(1)

path = sys.argv[1]
trecho = sys.argv[2].lower()

doc = Document(path)
count = 0
for i, p in enumerate(doc.paragraphs):
    raw = get_paragraph_raw_text(p).lower()
    if trecho in raw:
        count += 1
        print(i, raw[:300])

print('Total paragraphs with trecho:', count)
