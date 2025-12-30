import io
import json
from pathlib import Path
from docx import Document
from app.analysis.docx_comments import add_error_comments_to_docx
from app.analysis.doc_parser import get_paragraph_raw_text, segment_document

base = Path(__file__).parent.parent
uploads = base / 'data' / 'uploads'
processed_dir = base / 'data' / 'processed'
processed_dir.mkdir(parents=True, exist_ok=True)

files = list(uploads.glob('*.docx'))
if not files:
    print('Nenhum DOCX em uploads')
    raise SystemExit(1)

src = files[0]
print('Processando:', src.name)
file_bytes = src.read_bytes()

# Vamos tentar inserir erro 'R$xx,00' no título provável
clause_title = 'PREÇO E DESPESAS - Parágrafo 1'
errors_by_clause = {
    clause_title: [
        {
            'id_regra': 'R002',
            'comentario': "Erro Crítico: Placeholder 'R$xx,00' encontrado.",
            'trecho_exato': 'R$xx,00'
        }
    ]
}

res = add_error_comments_to_docx(file_bytes, errors_by_clause)
out_path = processed_dir / (f"test_processed_{src.name}")
out_path.write_bytes(res)
print('Arquivo salvo em', out_path)

# Inspeciona onde ficou o trecho
doc = Document(str(out_path))
norm = lambda s: (s or '').replace('\u00A0',' ').replace('\xa0',' ').strip()
search_norm = 'r$xx,00'
for p in doc.paragraphs:
    raw = get_paragraph_raw_text(p)
    if search_norm in raw.lower():
        print('\nParágrafo com trecho encontrado (raw):', p.text[:200])
        runs = [norm(r.text or '') for r in p.runs]
        combined = ''.join(runs)
        import re
        combined_search = re.sub(r"\s+", ' ', combined)
        idx = combined_search.lower().find(search_norm)
        print('Índice no combined:', idx)
        if idx>=0:
            acc=0
            for i, rt in enumerate(runs):
                start=acc
                end=acc+len(rt)
                if end>idx:
                    print('Run index', i, 'text repr:', repr(p.runs[i].text))
                    break
                acc=end
        else:
            print('Índice não encontrado — imprime runs:')
            for i, rr in enumerate(p.runs):
                print(i, repr(rr.text))
        break
else:
    print('trecho_exato não encontrado como raw no doc processado')
