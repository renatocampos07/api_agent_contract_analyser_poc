import sys
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET

def inspect(docx_path):
    p = Path(docx_path)
    if not p.exists():
        print('File not found:', docx_path)
        return
    with zipfile.ZipFile(p, 'r') as z:
        if 'word/comments.xml' not in z.namelist():
            print('No comments.xml present in', docx_path)
            return
        data = z.read('word/comments.xml')
    root = ET.fromstring(data)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    comments = root.findall('w:comment', ns)
    print(f'Found {len(comments)} comments in {docx_path}')
    for c in comments:
        cid = c.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id')
        # extract text inside comment (concatenate w:t)
        texts = []
        for t in c.findall('.//w:t', ns):
            texts.append(t.text or '')
        txt = ''.join(texts)
        author = c.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author')
        print('---')
        print('id:', cid, 'author:', author)
        print('text:', txt[:300])

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: inspect_comments.py <path_to_docx>')
        sys.exit(1)
    inspect(sys.argv[1])
