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
        if 'word/document.xml' not in z.namelist():
            print('No document.xml present in', docx_path)
            return
        doc_xml = z.read('word/document.xml')
    root = ET.fromstring(doc_xml)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    # find all comment anchors/refs
    starts = root.findall('.//w:commentRangeStart', ns)
    ends = root.findall('.//w:commentRangeEnd', ns)
    refs = root.findall('.//w:commentReference', ns)
    counts = {}
    for el in starts+ends+refs:
        cid = el.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id')
        if cid is None:
            continue
        counts[cid] = counts.get(cid, 0) + 1
    print('Found comment anchors/refs counts (id: occurrences):')
    for cid, cnt in counts.items():
        print(cid, cnt)
    dup = {cid:cnt for cid,cnt in counts.items() if cnt>2}
    if dup:
        print('\nComment IDs with more than 2 anchors/refs (likely duplicate visible marks):')
        for cid,cnt in dup.items():
            print(cid, cnt)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: inspect_comment_anchors.py <path_to_docx>')
        sys.exit(1)
    inspect(sys.argv[1])
