from docx import Document
import sys
from pathlib import Path
# Ensure backend package dir is on sys.path so we can import `app` when the
# script is executed from different working directories.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.analysis.doc_parser import get_paragraph_raw_text

if len(sys.argv) < 2:
    print('Usage: diagnose_runs.py <docx_path>')
    sys.exit(1)

path = Path(sys.argv[1])
if not path.exists():
    print('File not found:', path)
    sys.exit(1)

doc = Document(path)

# search terms to look for
terms = ['aviso prévio', 'vício', 'vício(s)', 'responsável', 'prazo', '10 (', '10 ', '60 dias', '10 05', 'dez', 'cinco']

def local_tag(tag):
    if isinstance(tag, str) and '}' in tag:
        return tag.rsplit('}', 1)[1]
    return tag

for pi, p in enumerate(doc.paragraphs):
    text = (p.text or '')
    low = text.lower()
    if any(t in low for t in terms):
        print('='*80)
        print('Paragraph index:', pi)
        print('Paragraph text:', repr(text))
        try:
            raw = get_paragraph_raw_text(p)
        except Exception as e:
            raw = f'<error calling get_paragraph_raw_text: {e}>'
        print('Reconstructed (get_paragraph_raw_text):', repr(raw))
        print('Runs count:', len(p.runs))
        for ri, r in enumerate(p.runs):
            rt = r.text or ''
            print(f'  Run {ri}: repr={repr(rt)}  bold={getattr(r, "bold", None)} italic={getattr(r, "italic", None)}')
            try:
                xml = r._r.xml
                # show only short xml
                print('    XML:', xml[:200].replace('\n',''))
            except Exception as e:
                print('    XML: <unavailable>', e)

        # print raw xml nodes in paragraph and which tag they are
        try:
            el = p._p
            print('\n  Paragraph XML nodes (tag -> text snippet):')
            for node in el.iter():
                t = node.text or ''
                print('    ', local_tag(node.tag), '->', repr(t)[:80])
        except Exception as e:
            print('  Could not access paragraph XML:', e)

print('\nDone.')
