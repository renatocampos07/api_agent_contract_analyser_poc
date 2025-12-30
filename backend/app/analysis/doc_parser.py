from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
import re
from typing import Iterable, Optional

ZERO_WIDTH_CHARACTERS = {
    '\u200b',  # zero width space
    '\u200c',  # zero width non-joiner
    '\u200d',  # zero width joiner
    '\u200e',  # left-to-right mark
    '\u200f',  # right-to-left mark
    '\u202a',  # left-to-right embedding
    '\u202c',  # pop directional formatting
    '\u2060',  # word joiner
    '\ufeff',  # byte order mark
    '\u00ad',  # soft hyphen
}

_ZERO_WIDTH_TRANSLATION = str.maketrans('', '', ''.join(ZERO_WIDTH_CHARACTERS))

NON_BREAKING_SPACES = {
    '\u00a0',  # non-breaking space
    '\u202f',  # narrow no-break space
    '\u2007',  # figure space
}

_NBSP_TO_SPACE_TRANSLATION = str.maketrans({ch: ' ' for ch in NON_BREAKING_SPACES})

# Pre-compiled regex patterns for performance
MANUAL_NUMBERING_PATTERN = re.compile(r'^\s*\d+(\.\d+)+\s+')
CLAUSE_TITLE_PATTERN = re.compile(r'^(CLÁUSULA \w+)|(CAPÍTULO \w+)|(Art\.)', re.IGNORECASE)
SUBCLAUSE_PATTERN = re.compile(r'^\s*\d+(\.\d+)+\s+')


def _local_name(tag: str) -> str:
    if isinstance(tag, str) and '}' in tag:
        return tag.rsplit('}', 1)[1]
    return tag


def _has_ancestor(node, names: set[str]) -> bool:
    parent = node
    while parent is not None:
        if _local_name(parent.tag) in names:
            return True
        parent = parent.getparent()
    return False


def normalize_visible_text(text: str) -> str:
    text = (text or '').translate(_ZERO_WIDTH_TRANSLATION)
    text = text.translate(_NBSP_TO_SPACE_TRANSLATION)
    text = re.sub(r"\s+", ' ', text).strip()
    text = re.sub(r'(?<!\.)\.\.(?!\.)', '.', text)
    text = re.sub(r',\s*,', ', ', text)
    return text.replace(',,', ',')


def _create_sub_title(title: str, paragraphs: list[Paragraph], part_index: Optional[int] = None, start_idx: int = 0, max_len: int = 80) -> str:
    if len(paragraphs) == 1:
        return f"{title} - {paragraphs[start_idx].text.strip()[:max_len]}..."
    if part_index is not None:
        return f"{title} (Parte {part_index})"
    return f"{title} - {paragraphs[start_idx].text.strip()[:max_len]}..."


def get_paragraph_raw_text(p: Paragraph) -> str:
    # Extrai texto original ignorando sugestões e mantendo deletes.
    try:
        el = p._p
    except Exception:
        return normalize_visible_text(p.text or "")

    parts: list[str] = []
    for node in el.iter():
        local = _local_name(node.tag)

        if local in ('t', 'instrText'):
            if _has_ancestor(node, {'ins'}):
                continue
            parts.append(node.text or '')
        elif local == 'delText':
            parts.append(node.text or '')

    combined = normalize_visible_text(''.join(parts))
    if not combined:
        combined = normalize_visible_text(p.text or "")
    return combined

def is_new_clause(p: Paragraph) -> bool:
    # Verifica se parágrafo é início de nova cláusula (estilo, maiúsculas, regex, negrito).
    text = p.text.strip()
    
    # Se o parágrafo estiver totalmente vazio, não é uma nova cláusula.
    if not text:
        return False
    
    # ---
    # REGRA 1: Pelo estilo do Word (APENAS HEADINGS PRINCIPAIS)
    # ---
    try:
        if p.style and hasattr(p.style, 'name') and p.style.name:
            style_name = p.style.name.lower()
            if (style_name.startswith('heading') or 
                style_name.startswith('título')):  # REMOVIDO: style_name == 'syngenta title 12 pt after'
                return True
    except:
        pass
    
    # ---
    # REGRA 2: Pelo formato (TODO EM MAIÚSCULAS) - PRIORIDADE PARA TÍTULOS
    # ---
    # Só considera como cláusula se for TODO maiúsculo, curto, e não começar com pontuação
    if all([
        text.isupper(),
        len(text) > 3,  # REDUZIDO de 5 para 3
        1 <= len(text.split()) <= 12,  # AUMENTADO de 8 para 12 palavras
        not text.startswith(('.', ','))
    ]):
        normalized_token = re.sub(r'[^A-Z0-9]', '', text)
        if len(normalized_token) >= 3 and len(set(normalized_token)) == 1:
            return False
        return True
        
    # ---
    # REGRA 3: Padrão de Regex para cláusulas numeradas
    # ---
    # "CLÁUSULA X", "CAPÍTULO Y", "Art.", ou numeração manual como 1.1, 15.11, etc.
    
    if CLAUSE_TITLE_PATTERN.match(text) or MANUAL_NUMBERING_PATTERN.match(text):
        return True
    
    # ---
    # REGRA 4: Pelo formato (negrito) - apenas títulos curtos em negrito
    # ---
    if (p.runs and p.runs[0].bold and 
        len(text) < 50 and 
        len(text.split()) <= 5):
        return True
            
    return False

def subdivide_large_clause(title: str, paragraphs: list[Paragraph], max_paragraphs: int = 10, max_chars: int = 4000) -> list[tuple[str, list[Paragraph]]]:
    # Subdivide cláusula grande em sub-cláusulas menores para análise eficiente.
    visible_paragraphs = [p for p in paragraphs if get_paragraph_raw_text(p)]
    if not visible_paragraphs:
        return []

    paragraphs = visible_paragraphs
    full_text = "\n".join([p.text for p in paragraphs])
    
    # Se não exceder os limites, mas houver subcláusulas numeradas, ainda assim separa
    # Identifica índices de início das subcláusulas numeradas
    subclause_indices = [i for i, p in enumerate(paragraphs) if SUBCLAUSE_PATTERN.match(p.text.strip())]
    # Se não houver subcláusulas numeradas, separa cada parágrafo como subcláusula
    if not subclause_indices:
        subclauses = []
        for idx, p in enumerate(paragraphs, 1):
            sub_title = f"{title} - Parágrafo {idx}"
            subclauses.append((sub_title, [p]))
        return subclauses

    # Se houver subcláusulas numeradas, separa cada uma como subitem
    if subclause_indices:
        subclauses = []
        subclause_indices.append(len(paragraphs))  # Para pegar o último bloco
        for idx in range(len(subclause_indices)-1):
            start = subclause_indices[idx]
            end = subclause_indices[idx+1]
            sub_paragraphs = paragraphs[start:end]
            sub_title = paragraphs[start].text.strip().split()[0]  # Usa o número como título
            # Opcional: pode incluir parte do texto para contexto
            sub_title_full = _create_sub_title(title, sub_paragraphs, start_idx=0, max_len=60)
            subclauses.append((sub_title_full, sub_paragraphs))
        return subclauses

    subclauses = []
    current_subparagraphs = []
    sub_index = 1
    for p in paragraphs:
        current_subparagraphs.append(p)
        current_text = "\n".join([sp.text for sp in current_subparagraphs])
        should_split = (
            len(current_subparagraphs) >= max_paragraphs or
            len(current_text) >= max_chars or
            (p.text.strip() and len(p.text.strip()) < 100 and not p.text.isupper())  # Possível subtítulo
        )
        if should_split and current_subparagraphs:
            sub_title = _create_sub_title(title, current_subparagraphs, part_index=sub_index if len(current_subparagraphs) > 1 else None)
            subclauses.append((sub_title, current_subparagraphs))
            current_subparagraphs = []
            sub_index += 1
    if current_subparagraphs:
        sub_title = _create_sub_title(title, current_subparagraphs, part_index=sub_index if len(current_subparagraphs) > 1 else None)
        subclauses.append((sub_title, current_subparagraphs))
    return subclauses

def is_document_title(p: Paragraph) -> bool:
    # Verifica se parágrafo é título principal do documento (não cláusula).
    text = p.text.strip()
    
    # Só considera título de documento se for muito curto e específico
    if (len(text) > 10 and len(text) < 100 and  # Tamanho específico
        text.isupper() and  # Deve ser maiúsculo
        any(word in text for word in ['CONTRATO', 'ACORDO', 'TERMO']) and  # Palavras específicas
        len(text.split()) <= 10):  # Não muito longo
        return True
    
    # Estilo específico de título (se existir)
    try:
        if p.style and hasattr(p.style, 'name') and p.style.name:
            style_name = p.style.name.lower()
            if 'title' in style_name or 'título' in style_name:
                return True
    except:
        pass
        
    return False

def is_subclause(p: Paragraph) -> bool:
    # Verifica se parágrafo é subcláusula numerada (ex.: 1.1, 15.11).
    text = p.text.strip()
    return bool(SUBCLAUSE_PATTERN.match(text))

def iter_document_paragraphs(doc: Document) -> Iterable[Paragraph]:
    """Itera parágrafos do corpo do documento preservando a ordem, incluindo tabelas."""
    body = doc.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            seen_cells = set()
            for row in table.rows:
                for cell in row.cells:
                    cell_id = id(cell._tc)
                    if cell_id in seen_cells:
                        continue
                    seen_cells.add(cell_id)
                    for paragraph in cell.paragraphs:
                        yield paragraph

def segment_document(doc: Document) -> list[tuple[str, list[Paragraph]]]:
    logical_clauses = []
    current_paragraphs = []
    current_title = "Preâmbulo" # Cláusulas antes do primeiro título
    found_first_clause = False

    for p in iter_document_paragraphs(doc):
        if is_document_title(p):
            # Pula títulos principais do documento - não os trata como cláusulas
            continue
        elif is_subclause(p):
            # Subcláusula: adiciona ao conteúdo da cláusula atual (não cria nova cláusula)
            if get_paragraph_raw_text(p):
                current_paragraphs.append(p)
        elif is_new_clause(p):
            # Salva a cláusula anterior se ela tiver conteúdo (incluindo o preâmbulo)
            if current_paragraphs:
                logical_clauses.append((current_title, current_paragraphs))
            
            # Inicia a nova cláusula (NÃO inclui o parágrafo do título no conteúdo)
            current_title = p.text.strip()
            current_paragraphs = []  # NÃO adiciona [p] aqui - o título não deve ser analisado
            found_first_clause = True
        else:
            # Continua a cláusula atual
            if get_paragraph_raw_text(p):
                current_paragraphs.append(p)
    
    # Salva a última cláusula
    if current_paragraphs:
        logical_clauses.append((current_title, current_paragraphs))
    
    # Agora subdivide cláusulas muito grandes
    final_clauses = []
    for title, paragraphs in logical_clauses:
        # Não subdivide o preâmbulo - mantém como uma única cláusula
        if "Preâmbulo" in title:
            final_clauses.append((title, paragraphs))
        else:
            subdivided = subdivide_large_clause(title, paragraphs)
            final_clauses.extend(subdivided)
        
    return final_clauses