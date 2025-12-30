import sys
from pathlib import Path
import zipfile

if len(sys.argv) < 3:
    print('Usage: view_comment_anchors.py <docx> <comment_id>')
    sys.exit(1)

p = Path(sys.argv[1])
cid = sys.argv[2]
with zipfile.ZipFile(p, 'r') as z:
    doc_xml = z.read('word/document.xml').decode('utf-8')

# find all occurrences of commentRangeStart/commentRangeEnd/commentReference with id
import re
pattern = re.compile(r'(<w:(commentRangeStart|commentRangeEnd|commentReference)[^>]*w:id="'+re.escape(cid)+r'"[^>]*>)')
for m in pattern.finditer(doc_xml):
    start = max(0, m.start()-120)
    end = min(len(doc_xml), m.end()+120)
    snippet = doc_xml[start:end]
    print('--- Occurrence at', m.start())
    print(snippet)

# Also print context around the paragraph that contains the target text
if len(sys.argv) >=4:
    text = sys.argv[3]
    ti = doc_xml.lower().find(text.lower())
    if ti>=0:
        start = max(0, ti-200)
        end = min(len(doc_xml), ti+200)
        print('\n--- Paragraph context around text:')
        print(doc_xml[start:end])
