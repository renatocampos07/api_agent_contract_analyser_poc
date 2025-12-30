import io
import datetime
import re
from docx import Document
from app.analysis.doc_parser import segment_document
from app.analysis.doc_parser import get_paragraph_raw_text, normalize_visible_text
from app.analysis.llm_provider import get_chat_llm
from app.analysis.prompts import get_clause_analysis_prompt, format_rules_prompt, get_rule_name_by_id
from app.analysis.docx_comments import add_error_comments_to_docx
from app.models.pydantic_models import RelatorioAnaliseJSON, AnaliseClausula, ErroContratual, ListaDeErros
from app.services.storage import AbstractStorage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Dict, Optional, Set
from docx.text.paragraph import Paragraph

PLACEHOLDER_QUOTE_RE = re.compile(r"'([^']+)'")
PLACEHOLDER_FALLBACK_RE = re.compile(
    r"(X{3,}|x{3,}|R\$x+[\d,\.]*|XX/XX/XXXX|INSERT [A-Z ]+|INDICAR [A-Z\u00C0-\u00DA ]+|\[[^\]]+\])"
)


def _refine_placeholder_snippet(erro: ErroContratual, clause_text: str) -> None:
    if erro.id_regra != "RBRA":
        return

    comentario = erro.comentario or ""
    trecho_atual = erro.trecho_exato or ""
    clause_normalized = normalize_visible_text(clause_text)

    candidate = None
    match = PLACEHOLDER_QUOTE_RE.search(comentario)
    if match:
        candidate = match.group(1).strip()

    if not candidate and trecho_atual:
        fallback = PLACEHOLDER_FALLBACK_RE.search(trecho_atual)
        if fallback:
            candidate = fallback.group(0).strip()

    if candidate:
        normalized_candidate = normalize_visible_text(candidate)
        if normalized_candidate and normalized_candidate in clause_normalized:
            erro.trecho_exato = candidate
            return

    if trecho_atual:
        normalized_trecho = normalize_visible_text(trecho_atual)
        if normalized_trecho and normalized_trecho in clause_normalized:
            return

    if candidate and not erro.trecho_exato:
        erro.trecho_exato = candidate

# 1. Pipeline de Análise (O "Cérebro")
async def run_analysis_pipeline(
    file_content: bytes, 
    user_id: str, 
    storage: AbstractStorage, 
    use_rag: bool = False,
    custom_rules: Optional[List[Dict]] = None,
    clausulas_alvo: Optional[Set[int]] = None,
    system_intro_override: Optional[str] = None,
    skip_segmentation: bool = False,
    llm_deployment_override: Optional[str] = None,
    llm_temperature_override: Optional[float] = None,
) -> tuple[bytes, RelatorioAnaliseJSON]:
    
    # Carrega documento e regras
    doc = Document(io.BytesIO(file_content))
    
    # Carregar regras padrão
    base_rules = await storage.get_rules(user_id)
    
    # Combinar com regras personalizadas se fornecidas
    if custom_rules:
        # Adicionar regras personalizadas às regras padrão
        rules = base_rules + custom_rules
    else:
        rules = base_rules
        
    rules_prompt = format_rules_prompt([r for r in rules if not r['id_regra'].startswith('G')])
    global_rules = [r for r in rules if r['id_regra'].startswith('G')]

    parser_only = clausulas_alvo is not None and len(clausulas_alvo) == 0

    # 2. Segmentação (Fase 1)
    report = RelatorioAnaliseJSON(
        nome_arquivo="contrato_revisado.docx",
        data_analise=datetime.datetime.now().isoformat(),
        clausulas=[],
        erros_globais=[]
    )
    
    # Dicionário para armazenar erros por cláusula para comentários
    errors_by_clause = {}
    
    # Permite pular a segmentação e analisar o documento inteiro como um único bloco
    if skip_segmentation:
        segmented_clauses = [("Documento inteiro", list(doc.paragraphs))]
    else:
        segmented_clauses = segment_document(doc)

    if parser_only:
        for i, (title, paragraphs) in enumerate(segmented_clauses):
            clausula_id = f"item_{i}"
            full_text = "\n".join([get_paragraph_raw_text(p) for p in paragraphs])
            analise_obj = AnaliseClausula(
                id_clausula=clausula_id,
                titulo=title,
                texto_original=full_text,
                erros_encontrados=[ErroContratual(id_regra="PULADO")],
            )
            report.clausulas.append(analise_obj)

        return file_content, report

    selecionar_alguma = clausulas_alvo is None or len(clausulas_alvo) > 0

    # Inicializa o LLM e o Parser de JSON somente quando necessário
    llm = get_chat_llm(llm_deployment_override, llm_temperature_override)
    parser = JsonOutputParser(pydantic_object=ListaDeErros)

    # Monta o Prompt usando o template do módulo prompts
    prompt_template = get_clause_analysis_prompt(
        rules_prompt,
        parser,
        system_intro_override=system_intro_override,
        scope_whole_document=skip_segmentation,
    )

    # Se RAG estiver habilitado (v2.0), injetar contexto aqui
    if use_rag:
        # rag_context = await rag_search(clausula_texto)
        # prompt_template = ... (injetar rag_context no prompt)
        pass

    chain = prompt_template | llm | parser
    
    # 3. Análise Local (Fase 2 - Cláusula por Cláusula)
    # Coletar erros e conformidades por regra
    conformidades = {}
    erros_encontrados_ids = set()
    for i, (title, paragraphs) in enumerate(segmented_clauses):
        clausula_id = f"item_{i}"
        full_text = "\n".join([get_paragraph_raw_text(p) for p in paragraphs])
        analise_obj = AnaliseClausula(id_clausula=clausula_id, titulo=title, texto_original=full_text, erros_encontrados=[])

        regras_ja_analisadas = set()
        if clausulas_alvo is None or i in clausulas_alvo:
            try:
                resultado_parser = await chain.ainvoke({"clausula_texto": full_text})
                if resultado_parser and "erros" in resultado_parser:
                    erros_list = resultado_parser["erros"]
                    for erro_dict in erros_list:
                        if not erro_dict:
                            continue
                        erro_dict['nome'] = get_rule_name_by_id(rules, erro_dict.get('id_regra', ''))
                        try:
                            erro_obj = ErroContratual(**erro_dict)
                            _refine_placeholder_snippet(erro_obj, full_text)
                            is_dup = any(
                                (e.id_regra == erro_obj.id_regra and
                                 ((e.trecho_exato or '').strip() == (erro_obj.trecho_exato or '').strip()) and
                                 e.comentario == erro_obj.comentario)
                                for e in analise_obj.erros_encontrados
                            )
                            if is_dup:
                                print(f"Aviso: erro duplicado ignorado para cláusula '{title}': {erro_obj.id_regra} / {erro_obj.trecho_exato}")
                            else:
                                analise_obj.erros_encontrados.append(erro_obj)
                                erros_encontrados_ids.add(erro_obj.id_regra)
                                regras_ja_analisadas.add(erro_obj.id_regra)
                            bucket = errors_by_clause.setdefault(title, [])
                            entry = {
                                'id_regra': erro_obj.id_regra,
                                'comentario': erro_obj.comentario,
                                'trecho_exato': erro_obj.trecho_exato
                            }
                            if not any((e.get('id_regra') == entry['id_regra'] and (e.get('trecho_exato','').strip() == entry['trecho_exato'].strip()) and e.get('comentario') == entry['comentario']) for e in bucket):
                                bucket.append(entry)
                        except Exception as pyd_err:
                            print(f"Erro ao validar ErroContratual para cláusula '{title}': {pyd_err} - dados: {erro_dict}")
                # Coletar conformidades (casos em que a IA analisou e não gerou erro)
                if resultado_parser and "conformidades" in resultado_parser:
                    for conf in resultado_parser["conformidades"]:
                        id_regra = conf.get("id_regra")
                        if id_regra and id_regra not in erros_encontrados_ids:
                            nome_regra = get_rule_name_by_id(rules, id_regra)
                            conformidades[id_regra] = {
                                "id_regra": id_regra,
                                "nome_regra": nome_regra,
                                "comentario": conf.get("comentario") or conf.get("motivo") or "Em conformidade com a regra.",
                                "trecho_exato": conf.get("trecho_exato") or conf.get("trecho", "")
                            }
                            regras_ja_analisadas.add(id_regra)
                # # Para cada regra do prompt, se não está em erro nem em conformidades, adiciona como "analisada sem erro explícito"
                # for r in rules:
                #     rid = r.get('id_regra')
                #     if rid and rid not in erros_encontrados_ids and rid not in conformidades and rid not in regras_ja_analisadas:
                #         conformidades[rid] = {
                #             "id_regra": rid,
                #             "nome_regra": r.get('nome'),
                #             "comentario": "LLM analisou a cláusula, mas não retornou erro nem conformidade explícita.",
                #             "trecho_exato": ""
                #         }
            except Exception as e:
                print(f"Erro ao analisar cláusula {title}: {e}")
                bucket = errors_by_clause.setdefault(title, [])
                bucket.append({
                    'id_regra': 'ERRO_IA',
                    'comentario': f"[ERRO IA] {e}",
                    'trecho_exato': None
                })
        else:
            analise_obj.erros_encontrados.append(ErroContratual(id_regra="PULADO"))
        report.clausulas.append(analise_obj)

    # 4. Análise Global (Fase 3 - Cláusulas Ausentes)
    # Construir lista de textos pesquisáveis: título + texto da cláusula (lowercased)
    clause_texts = [f"{c.titulo or ''}\n{c.texto_original or ''}".lower() for c in report.clausulas]

    if selecionar_alguma:
        for rule in global_rules:
            if "keywords" not in rule or not rule["keywords"]:
                continue
            keywords_da_regra = [k.lower() for k in rule['keywords']]
            encontrado = False
            for keyword in keywords_da_regra:
                if any(keyword in t for t in clause_texts):
                    encontrado = True
                    break
            if not encontrado:
                erro_global = ErroContratual(
                    id_regra=rule['id_regra'],
                    nome=rule['nome'],
                    comentario=f"Ausência: {rule['nome']}.",
                    trecho_exato="N/A (Documento Inteiro)"
                )
                # report.erros_globais.append(erro_global)
                # # Se não está em erros nem em conformidades, adiciona como não encontrada
                # if rule['id_regra'] not in erros_encontrados_ids and rule['id_regra'] not in conformidades:
                #     conformidades[rule['id_regra']] = {
                #         "id_regra": rule['id_regra'],
                #         "nome_regra": rule['nome'],
                #         "comentario": "Cláusula não encontrada/Não aplicável",
                #         "trecho_exato": ""
                #     }
                # Também adicionar como comentário no DOCX: anexa ao início (primeira cláusula)
                # para que o revisor veja a ausência diretamente no arquivo.
                if report.clausulas:
                    first_title = report.clausulas[0].titulo
                    bucket = errors_by_clause.setdefault(first_title, [])
                    entry = {
                        'id_regra': rule['id_regra'],
                        'comentario': erro_global.comentario,
                        'trecho_exato': None
                    }
                    # evitar duplicates
                    if not any((e.get('id_regra') == entry['id_regra'] and (e.get('trecho_exato','').strip() == (entry['trecho_exato'] or '').strip()) and e.get('comentario') == entry['comentario']) for e in bucket):
                        bucket.append(entry)
                

    # 5. Aplica comentários
    docx_content = add_error_comments_to_docx(file_content, errors_by_clause)

    # 5.1 Propaga trecho_marcado (preenchido em errors_by_clause) para os objetos ErroContratual
    for clausula in report.clausulas:
        bucket = errors_by_clause.get(clausula.titulo) or []
        for erro in clausula.erros_encontrados:
            for e_dict in bucket:
                if (
                    e_dict.get("id_regra") == erro.id_regra
                    and (e_dict.get("comentario") or "") == (erro.comentario or "")
                    and (e_dict.get("trecho_exato") or "").strip() == (erro.trecho_exato or "").strip()
                ):
                    if "trecho_marcado" in e_dict:
                        erro.trecho_marcado = e_dict["trecho_marcado"]
                    break

    # Adiciona sessão de conformidades após erros_globais
    report.conformidades = list(conformidades.values()) if conformidades else None
    return docx_content, report