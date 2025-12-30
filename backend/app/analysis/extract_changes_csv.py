import os
import csv
import zipfile
from lxml import etree
from typing import Optional, List, Dict

# Definição Completa de Namespaces
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
    'w16se': 'http://schemas.microsoft.com/office/word/2015/wordml/symex',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006'
}

def qn(tag):
    return f"{{{NAMESPACES['w']}}}{tag}"

# ==========================================
# MÉTODO 1: PADRÃO (Fragmentado/Linear)
# ==========================================
class DocxParserStandard:
    def __init__(self, docx_path: str, nome_arquivo: str):
        self.docx_path = docx_path
        self.filename = nome_arquivo
        self.comments_map = {}
        self.rows = []
        
        # Estado Global
        self.buffer_text = []
        self.current_context_type = 'texto' 
        self.current_tc_meta = {} 
        
        self.active_comments_stack = [] 
        self.captured_content_in_range = {}
        self.p_index = 0
        self.current_section_type = 'Body'

    def load_comments(self, zf: zipfile.ZipFile):
        if 'word/comments.xml' not in zf.namelist(): return
        try:
            xml_content = zf.read('word/comments.xml')
            tree = etree.fromstring(xml_content)
        except Exception: return
        
        for comment in tree.iter():
            if etree.QName(comment).localname == 'comment':
                c_id = self._get_safe_attrib(comment, 'id')
                c_text = "".join([t for t in comment.itertext()])
                self.comments_map[c_id] = {
                    'autor': self._get_safe_attrib(comment, 'author'),
                    'data': self._get_safe_attrib(comment, 'date'),
                    'texto': c_text
                }

    def _get_safe_attrib(self, elem, attr_name):
        val = elem.get(qn(attr_name))
        if val: return val
        val = elem.get(attr_name)
        if val: return val
        for key, value in elem.attrib.items():
            if key.endswith(f"}}{attr_name}") or key == attr_name:
                return value
        return ''

    def _find_tc_context(self, elem):
        for ancestor in elem.iterancestors():
            tag_name = etree.QName(ancestor).localname
            tc_type = None
            if tag_name in ['ins', 'moveTo']:
                tc_type = 'insert'
            elif tag_name in ['del', 'moveFrom']:
                tc_type = 'delete'
            
            if tc_type:
                return tc_type, {
                    'author': self._get_safe_attrib(ancestor, 'author'),
                    'date': self._get_safe_attrib(ancestor, 'date')
                }
            if tag_name in ['p', 'tbl', 'sectPr', 'body']:
                break
        return 'texto', {}

    def flush_buffer(self):
        text = "".join(self.buffer_text)
        if not text: return

        txt_orig = ""
        txt_modificado = ""
        trecho_comentado = ""
        tipo_change, autor, data = "", "", ""
        
        if self.current_context_type == 'insert':
            txt_modificado = text
            tipo_change = "Inserção"
            autor = self.current_tc_meta.get('author', '')
            data = self.current_tc_meta.get('date', '')
        elif self.current_context_type == 'delete':
            txt_orig = text
            tipo_change = "Exclusão"
            autor = self.current_tc_meta.get('author', '')
            data = self.current_tc_meta.get('date', '')
        else:
            txt_orig = text

        comentarios_finais = []
        has_comments = False
        for c_id in self.active_comments_stack:
            has_comments = True
            if c_id in self.comments_map:
                meta = self.comments_map[c_id]
                comentarios_finais.append(meta['texto'])
                if not autor: 
                    autor = meta['autor']
                    data = meta['data']
            self.captured_content_in_range[c_id] = True

        if has_comments:
            trecho_comentado = text

        def sanitize(val):
            if not isinstance(val, str): return val
            return val.replace('\n', ' ').replace('\r', ' ').replace('"', "'").strip()

        txt_orig = sanitize(txt_orig)
        txt_modificado = sanitize(txt_modificado)
        trecho_comentado = sanitize(trecho_comentado)
        comentario = sanitize(" | ".join(comentarios_finais))

        coluna_tipo = "Texto"
        if tipo_change in ["Inserção", "Exclusão"]:
            coluna_tipo = tipo_change
        elif has_comments:
            coluna_tipo = "Comentário"

        self.rows.append({
            'Nome_arquivo': self.filename,
            'Index_p': self.p_index,
            'tipo_secao': self.current_section_type,
            'trecho_texto_orig': txt_orig,
            'trecho_texto_modificado': txt_modificado,
            'trecho_comentado': trecho_comentado,
            'comentario': comentario,
            'tipo': coluna_tipo,
            'nome_usuario': autor,
            'data_hora': data
        })
        self.buffer_text = []

    def _handle_empty_comment(self, c_id):
        if c_id not in self.comments_map: return
        meta = self.comments_map[c_id]
        self.rows.append({
            'Nome_arquivo': self.filename,
            'Index_p': self.p_index,
            'tipo_secao': self.current_section_type,
            'trecho_texto_orig': "", 
            'trecho_texto_modificado': "", 
            'trecho_comentado': "",
            'comentario': meta['texto'],
            'tipo': 'Comentário',
            'nome_usuario': meta['autor'],
            'data_hora': meta['data']
        })

    def parse_xml_content(self, xml_bytes):
        try: tree = etree.fromstring(xml_bytes)
        except Exception: return

        for elem in tree.iter():
            tag_name = etree.QName(elem).localname
            
            if tag_name in ['t', 'delText']:
                texto_no = elem.text or ""
                novo_tipo, nova_meta = self._find_tc_context(elem)
                
                contexto_mudou = (novo_tipo != self.current_context_type)
                meta_mudou = False
                if novo_tipo != 'texto':
                    meta_mudou = (nova_meta != self.current_tc_meta)

                if contexto_mudou or meta_mudou:
                    self.flush_buffer()
                    self.current_context_type = novo_tipo
                    self.current_tc_meta = nova_meta
                
                self.buffer_text.append(texto_no)

            elif tag_name == 'commentRangeStart':
                self.flush_buffer()
                c_id = self._get_safe_attrib(elem, 'id')
                if c_id not in self.active_comments_stack:
                    self.active_comments_stack.append(c_id)
                    self.captured_content_in_range[c_id] = False

            elif tag_name == 'commentRangeEnd':
                self.flush_buffer()
                c_id = self._get_safe_attrib(elem, 'id')
                if c_id in self.captured_content_in_range:
                    if not self.captured_content_in_range[c_id]:
                        self._handle_empty_comment(c_id)
                    del self.captured_content_in_range[c_id]
                if c_id in self.active_comments_stack:
                    self.active_comments_stack.remove(c_id)
            
            elif tag_name == 'p':
                self.flush_buffer()
                self.current_context_type = 'texto'
                self.current_tc_meta = {}
                full_text = "".join(elem.itertext()).strip()
                if full_text:
                    self.p_index += 1

            elif tag_name in ['br', 'cr', 'tab']:
                self.flush_buffer()
                self.current_context_type = 'texto'
                self.current_tc_meta = {}

        self.flush_buffer()

    def process(self):
        with zipfile.ZipFile(self.docx_path) as zf:
            self.load_comments(zf)
            file_list = zf.namelist()
            self.current_section_type = 'Header'
            headers = sorted([f for f in file_list if f.startswith('word/header') and f.endswith('.xml')])
            for h in headers: self.parse_xml_content(zf.read(h))
            
            self.current_section_type = 'Body'
            if 'word/document.xml' in file_list:
                self.parse_xml_content(zf.read('word/document.xml'))
            
            self.current_section_type = 'Footer'
            footers = sorted([f for f in file_list if f.startswith('word/footer') and f.endswith('.xml')])
            for f in footers: self.parse_xml_content(zf.read(f))

    def get_rows(self):
        return self.rows


# ==========================================
# MÉTODO 2: ALTERNATIVO (Parágrafo/Consolidado)
# ==========================================
class DocxParserParagraph:
    def __init__(self, docx_path: str, nome_arquivo: str):
        self.docx_path = docx_path
        self.filename = nome_arquivo
        self.comments_map = {}
        self.rows = []
        self.current_p_data = {
            'full_text_orig': [], 
            'full_text_final': [], 
            'interventions': [] 
        }
        self.p_index = 0
        self.current_section_type = 'Body'

    def load_comments(self, zf: zipfile.ZipFile):
        if 'word/comments.xml' not in zf.namelist(): return
        try:
            xml_content = zf.read('word/comments.xml')
            tree = etree.fromstring(xml_content)
        except Exception: return
        
        for comment in tree.iter():
            if etree.QName(comment).localname == 'comment':
                c_id = self._get_safe_attrib(comment, 'id')
                c_text = "".join([t for t in comment.itertext()])
                self.comments_map[c_id] = {
                    'autor': self._get_safe_attrib(comment, 'author'),
                    'data': self._get_safe_attrib(comment, 'date'),
                    'texto': c_text
                }

    def _get_safe_attrib(self, elem, attr_name):
        val = elem.get(qn(attr_name))
        if val: return val
        val = elem.get(attr_name)
        if val: return val
        for key, value in elem.attrib.items():
            if key.endswith(f"}}{attr_name}") or key == attr_name:
                return value
        return ''

    def _find_tc_context(self, elem):
        for ancestor in elem.iterancestors():
            tag_name = etree.QName(ancestor).localname
            tc_type = None
            if tag_name in ['ins', 'moveTo']:
                tc_type = 'insert'
            elif tag_name in ['del', 'moveFrom']:
                tc_type = 'delete'
            
            if tc_type:
                return tc_type, {
                    'author': self._get_safe_attrib(ancestor, 'author'),
                    'date': self._get_safe_attrib(ancestor, 'date')
                }
            if tag_name in ['p', 'tbl', 'sectPr', 'body']:
                break
        return 'texto', {}

    def _add_intervention(self, tipo, autor, data, texto_afetado):
        if not texto_afetado.strip(): return
        texto_limpo = texto_afetado.replace('\n', ' ').replace('\r', ' ').replace('"', "'").strip()
        timestamp = f" [{data}]" if data else ""
        user_stamp = f"[{autor}{timestamp}]" if autor else "[Desconhecido]"
        log_entry = f"{user_stamp} {tipo}: '{texto_limpo}'"
        self.current_p_data['interventions'].append(log_entry)

    def _commit_paragraph(self):
        txt_orig = "".join(self.current_p_data['full_text_orig']).strip()
        txt_final = "".join(self.current_p_data['full_text_final']).strip()
        has_content = bool(txt_orig or txt_final)
        has_changes = bool(self.current_p_data['interventions'])
        
        if not has_content and not has_changes:
            self.current_p_data = {'full_text_orig': [], 'full_text_final': [], 'interventions': []}
            return
        
        self.p_index += 1
        log_consolidado = "\n".join(self.current_p_data['interventions'])
        
        self.rows.append({
            'Nome_arquivo': self.filename,
            'Index_p': self.p_index,
            'tipo_secao': self.current_section_type,
            'Texto_Original': txt_orig,
            'Texto_Final': txt_final,
            'Log_Intervencoes': log_consolidado
        })
        self.current_p_data = {'full_text_orig': [], 'full_text_final': [], 'interventions': []}

    def parse_xml_content(self, xml_bytes):
        try: tree = etree.fromstring(xml_bytes)
        except Exception: return
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        for p_elem in tree.xpath('//w:p', namespaces=namespaces):
            for child in p_elem.iter():
                tag_name = etree.QName(child).localname
                if tag_name in ['t', 'delText']:
                    text = child.text or ""
                    if not text: continue
                    tc_type, meta = self._find_tc_context(child)
                    if tc_type == 'delete':
                        self.current_p_data['full_text_orig'].append(text)
                        self._add_intervention("DELETOU", meta.get('author'), meta.get('date'), text)
                    elif tc_type == 'insert':
                        self.current_p_data['full_text_final'].append(text)
                        self._add_intervention("INSERIU", meta.get('author'), meta.get('date'), text)
                    else:
                        self.current_p_data['full_text_orig'].append(text)
                        self.current_p_data['full_text_final'].append(text)
                elif tag_name == 'commentRangeStart':
                    c_id = self._get_safe_attrib(child, 'id')
                    if c_id in self.comments_map:
                        meta = self.comments_map[c_id]
                        self._add_intervention("COMENTOU", meta['autor'], meta['data'], meta['texto'])
            self._commit_paragraph()

    def process(self):
        with zipfile.ZipFile(self.docx_path) as zf:
            self.load_comments(zf)
            file_list = zf.namelist()
            self.current_section_type = 'Header'
            headers = sorted([f for f in file_list if f.startswith('word/header') and f.endswith('.xml')])
            for h in headers: self.parse_xml_content(zf.read(h))
            
            self.current_section_type = 'Body'
            if 'word/document.xml' in file_list:
                self.parse_xml_content(zf.read('word/document.xml'))
            
            self.current_section_type = 'Footer'
            footers = sorted([f for f in file_list if f.startswith('word/footer') and f.endswith('.xml')])
            for f in footers: self.parse_xml_content(zf.read(f))

    def get_rows(self):
        return self.rows

# ==========================================
# MÉTODO 3: HIERÁRQUICO (Lógica "Texto Original Base")
# ==========================================
class DocxParserHierarchical:
    def __init__(self, docx_path: str, nome_arquivo: str):
        self.docx_path = docx_path
        self.filename = nome_arquivo
        self.comments_map = {}
        self.rows = []
        
        self.p_index = 0
        self.current_section_type = 'Body'
        
        self.paragraph_full_text = [] # Reconstrói o texto ORIGINAL (sem inserções)
        self.paragraph_changes = []   
        self.char_cursor = 0          # Cursor relativo ao texto ORIGINAL

    def load_comments(self, zf: zipfile.ZipFile):
        if 'word/comments.xml' not in zf.namelist(): return
        try:
            xml_content = zf.read('word/comments.xml')
            tree = etree.fromstring(xml_content)
        except Exception: return
        
        for comment in tree.iter():
            if etree.QName(comment).localname == 'comment':
                c_id = self._get_safe_attrib(comment, 'id')
                c_text = "".join([t for t in comment.itertext()])
                self.comments_map[c_id] = {
                    'autor': self._get_safe_attrib(comment, 'author'),
                    'data': self._get_safe_attrib(comment, 'date'),
                    'texto': c_text
                }

    def _get_safe_attrib(self, elem, attr_name):
        val = elem.get(qn(attr_name))
        if val: return val
        val = elem.get(attr_name)
        if val: return val
        for key, value in elem.attrib.items():
            if key.endswith(f"}}{attr_name}") or key == attr_name:
                return value
        return ''

    def _find_tc_context(self, elem):
        for ancestor in elem.iterancestors():
            tag_name = etree.QName(ancestor).localname
            tc_type = None
            if tag_name in ['ins', 'moveTo']:
                tc_type = 'insert'
            elif tag_name in ['del', 'moveFrom']:
                tc_type = 'delete'
            
            if tc_type:
                return tc_type, {
                    'author': self._get_safe_attrib(ancestor, 'author'),
                    'date': self._get_safe_attrib(ancestor, 'date')
                }
            if tag_name in ['p', 'tbl', 'sectPr', 'body']:
                break
        return 'texto', {}

    def _commit_paragraph_hierarchical(self):
        # Texto Original reconstruído (contém o que foi deletado, ignora o que foi inserido)
        full_text_str = "".join(self.paragraph_full_text).strip()
        
        if not full_text_str and not self.paragraph_changes:
            self.paragraph_full_text = []
            self.paragraph_changes = []
            self.char_cursor = 0
            return

        self.p_index += 1

        # Linha MÃE (Texto Original Puro)
        self.rows.append({
            'Nome_arquivo': self.filename,
            'Index_p': self.p_index,
            'tipo_secao': self.current_section_type,
            'texto': full_text_str,
            'tipo': 'Parágrafo',
            'posicao': '',
            'comentario': '',
            'nome_usuario': '',
            'data_hora': ''
        })

        # Linhas FILHAS (Alterações)
        for ch in self.paragraph_changes:
            self.rows.append({
                'Nome_arquivo': self.filename,
                'Index_p': self.p_index,
                'tipo_secao': self.current_section_type,
                'texto': ch['texto'],
                'tipo': ch['tipo'],
                'posicao': ch['posicao'],
                'comentario': ch.get('comentario', ''),
                'nome_usuario': ch.get('autor', ''),
                'data_hora': ch.get('data', '')
            })

        self.paragraph_full_text = []
        self.paragraph_changes = []
        self.char_cursor = 0

    def parse_xml_content(self, xml_bytes):
        try: tree = etree.fromstring(xml_bytes)
        except Exception: return
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        for p_elem in tree.xpath('//w:p', namespaces=namespaces):
            # Reseta cursor para cada parágrafo novo
            # Nota: O cursor aqui é relativo ao início do texto deste parágrafo
            
            for child in p_elem.iter():
                tag_name = etree.QName(child).localname
                
                # Texto (Normal, Inserido ou Deletado)
                if tag_name in ['t', 'delText']:
                    text = child.text or ""
                    if not text: continue
                    
                    tc_type, meta = self._find_tc_context(child)
                    
                    if tc_type == 'insert':
                        # INSERÇÃO: Não soma no texto original.
                        # A posição é o ponto exato onde o cursor está agora.
                        # Ex: Texto Original "Casa [azul] bonita" -> Azul inserido na pos 5
                        self.paragraph_changes.append({
                            'tipo': 'Inserção',
                            'texto': text,
                            'posicao': f"{self.char_cursor}-{self.char_cursor}", # Ponto de inserção
                            'autor': meta.get('author', ''),
                            'data': meta.get('date', ''),
                            'comentario': ''
                        })
                        # NÃO avança o char_cursor nem adiciona ao paragraph_full_text
                        
                    elif tc_type == 'delete':
                        # EXCLUSÃO: Faz parte do texto original (foi deletado depois).
                        # Soma no buffer e avança cursor.
                        start_pos = self.char_cursor
                        end_pos = start_pos + len(text)
                        
                        self.paragraph_full_text.append(text)
                        self.char_cursor = end_pos
                        
                        self.paragraph_changes.append({
                            'tipo': 'Exclusão',
                            'texto': text,
                            'posicao': f"{start_pos}-{end_pos}",
                            'autor': meta.get('author', ''),
                            'data': meta.get('date', ''),
                            'comentario': ''
                        })
                    
                    else:
                        # TEXTO NORMAL: Faz parte do original.
                        start_pos = self.char_cursor
                        end_pos = start_pos + len(text)
                        
                        self.paragraph_full_text.append(text)
                        self.char_cursor = end_pos
                        
                # Comentários
                elif tag_name == 'commentRangeStart':
                    c_id = self._get_safe_attrib(child, 'id')
                    if c_id in self.comments_map:
                        meta = self.comments_map[c_id]
                        # Comentário ancorado na posição atual do cursor original
                        pos_str = f"{self.char_cursor}-{self.char_cursor}" 
                        self.paragraph_changes.append({
                            'tipo': 'Comentário',
                            'texto': '', 
                            'posicao': pos_str,
                            'autor': meta['autor'],
                            'data': meta['data'],
                            'comentario': meta['texto']
                        })

            self._commit_paragraph_hierarchical()

    def process(self):
        with zipfile.ZipFile(self.docx_path) as zf:
            self.load_comments(zf)
            file_list = zf.namelist()
            self.current_section_type = 'Header'
            headers = sorted([f for f in file_list if f.startswith('word/header') and f.endswith('.xml')])
            for h in headers: self.parse_xml_content(zf.read(h))
            
            self.current_section_type = 'Body'
            if 'word/document.xml' in file_list:
                self.parse_xml_content(zf.read('word/document.xml'))
            
            self.current_section_type = 'Footer'
            footers = sorted([f for f in file_list if f.startswith('word/footer') and f.endswith('.xml')])
            for f in footers: self.parse_xml_content(zf.read(f))

    def get_rows(self):
        return self.rows

# ... (Classe DocxParserHierarchical anterior mantida igual) ...

# ==============================================================================
# MÉTODO 4: HIERÁRQUICO FILTRADO (Herança para evitar código duplicado)
# ==============================================================================
class DocxParserHierarchicalFiltered(DocxParserHierarchical):
    """
    Herda 100% da lógica de parsing e cálculo de posição do Método 3.
    Única diferença: Intercepta o momento de salvar (_commit) para filtrar
    parágrafos que não sofreram intervenções.
    """
    def _commit_paragraph_hierarchical(self):
        # Se tiver alterações (lista não vazia), processa normalmente (chama o pai)
        if self.paragraph_changes:
            super()._commit_paragraph_hierarchical()
        else:
            # Se não tiver alterações, apenas avança o índice (para manter consistência)
            # e limpa os buffers, sem gerar linhas no CSV.
            full_text = "".join(self.paragraph_full_text).strip()
            if full_text: 
                self.p_index += 1
            
            self.paragraph_full_text = []
            self.paragraph_changes = []
            self.char_cursor = 0

# ==============================================================================
# MÉTODO 5: HIERÁRQUICO FILTRADO POR COMENTÁRIOS (Novo)
# ==============================================================================
class DocxParserHierarchicalCommentsOnly(DocxParserHierarchical):
    """
    Herda do Hierárquico base.
    Filtro: Só exporta o parágrafo se houver pelo menos um item 
    na lista de alterações cujo 'tipo' seja 'Comentário'.
    """
    def _commit_paragraph_hierarchical(self):
        # Verifica se existe alguma alteração do tipo 'Comentário'
        has_comments = any(ch['tipo'] == 'Comentário' for ch in self.paragraph_changes)
        
        if has_comments:
            # Se tiver comentário, processa normalmente (salva parágrafo + filhos)
            super()._commit_paragraph_hierarchical()
        else:
            # Se não tiver, apenas avança o índice e limpa buffers
            full_text = "".join(self.paragraph_full_text).strip()
            if full_text: 
                self.p_index += 1
            
            self.paragraph_full_text = []
            self.paragraph_changes = []
            self.char_cursor = 0

# ==========================================
# FUNÇÃO UNIFICADA (Factory Otimizada)
# ==========================================
def extract_comments_and_track_changes(docx_path: str, csv_path: str, nome_arquivo: Optional[str] = None, method: str = 'padrao'):
    if not os.path.exists(docx_path): return
    if nome_arquivo is None: nome_arquivo = os.path.basename(docx_path)

    parser = None
    colunas = []

    # Roteamento Inteligente
    if method == 'alternativo':
        parser = DocxParserParagraph(docx_path, nome_arquivo)
        colunas = ['Nome_arquivo', 'Index_p', 'tipo_secao', 'Texto_Original', 'Texto_Final', 'Log_Intervencoes']
    
    # Agrupa M3, M4 e M5 (mesma estrutura de colunas)
    elif method.startswith('hierarquico'):
        colunas = ['Nome_arquivo', 'Index_p', 'tipo_secao', 'texto', 'tipo', 'posicao', 'comentario', 'nome_usuario', 'data_hora']
        
        if method == 'hierarquico_filtrado':
            parser = DocxParserHierarchicalFiltered(docx_path, nome_arquivo)
        elif method == 'hierarquico_comentarios':
            parser = DocxParserHierarchicalCommentsOnly(docx_path, nome_arquivo)
        else:
            parser = DocxParserHierarchical(docx_path, nome_arquivo)
    
    else: # Padrão
        parser = DocxParserStandard(docx_path, nome_arquivo)
        colunas = ['Nome_arquivo', 'Index_p', 'tipo_secao', 'trecho_texto_orig', 'trecho_texto_modificado', 
                   'trecho_comentado', 'comentario', 'tipo', 'nome_usuario', 'data_hora']

    parser.process()
    rows = parser.get_rows()

    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=colunas, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Sucesso! CSV gerado: {len(rows)} linhas. (Método: {method})")
    except Exception as e:
        print(f"Erro ao salvar CSV: {e}")

# Helper de memória atualizado
def get_parser_rows(docx_path: str, nome_arquivo: str, method: str = 'padrao') -> List[Dict]:
    if method == 'alternativo': 
        parser = DocxParserParagraph(docx_path, nome_arquivo)
    elif method == 'hierarquico_filtrado': 
        parser = DocxParserHierarchicalFiltered(docx_path, nome_arquivo)
    elif method == 'hierarquico_comentarios':
        parser = DocxParserHierarchicalCommentsOnly(docx_path, nome_arquivo)
    elif method == 'hierarquico': 
        parser = DocxParserHierarchical(docx_path, nome_arquivo)
    else: 
        parser = DocxParserStandard(docx_path, nome_arquivo)
    
    parser.process()
    return parser.get_rows()