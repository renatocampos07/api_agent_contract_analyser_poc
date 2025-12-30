import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def collect_spans(doc_path: Path):
    with zipfile.ZipFile(doc_path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))

    active: list[int] = []
    captured: dict[int, list[str]] = {}

    for element in root.iter():
        tag = element.tag
        if tag == f"{{{NAMESPACE}}}commentRangeStart":
            cid = int(element.attrib[f"{{{NAMESPACE}}}id"])
            active.append(cid)
        elif tag == f"{{{NAMESPACE}}}commentRangeEnd":
            cid = int(element.attrib[f"{{{NAMESPACE}}}id"])
            if cid in active:
                active.remove(cid)
        elif tag == f"{{{NAMESPACE}}}t":
            text = element.text or ""
            if not text:
                continue
            for cid in active:
                captured.setdefault(cid, []).append(text)
    return {cid: "".join(parts) for cid, parts in captured.items()}


def main():
    doc_path = Path(
        "backend/data/processed/CONTRATO COM MARCA DE COMENTÁRIOS 1_validado.docx"
    )
    spans = collect_spans(doc_path)

    for cid in sorted(spans):
        snippet = spans[cid]
        print(f"{cid}: {snippet[:80]!r}")


if __name__ == "__main__":
    main()
