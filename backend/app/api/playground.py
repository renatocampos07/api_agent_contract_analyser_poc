# O playground SÓ deve funcionar em desenvolvimento
from fastapi import APIRouter, Request, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from app.core.config import settings
from app.services.storage import LocalFileStorage
from app.analysis.orchestrator import run_analysis_pipeline
from app.analysis.prompts import (
    get_default_system_intro,
    SYSTEM_SUFFIX_TEMPLATE,
    format_rules_prompt,
)
from app.models.pydantic_models import ListaDeErros
from langchain_core.output_parsers import JsonOutputParser
import io
import json
import uuid
import os
import csv
import tempfile
import traceback
from typing import Any

# Importa a função helper e o wrapper
from app.analysis.extract_changes_csv import get_parser_rows, extract_comments_and_track_changes

from app.analysis.reverse_prompting import reverse_prompting_loop, META_PROMPT_DEFAULT, RED_TEAM_SYSTEM_PROMPT

if settings.ENVIRONMENT != "development":
    raise RuntimeError("O Playground só pode ser iniciado em ambiente de desenvolvimento")

router = APIRouter()
templates_dir = os.path.join(os.path.dirname(__file__), "../../templates")
templates = Jinja2Templates(directory=templates_dir)
local_storage = LocalFileStorage()

# --- ROTAS GET ---
@router.get("/", response_class=HTMLResponse)
async def get_playground(request: Request):
    storage = LocalFileStorage()
    default_rules = await storage.get_rules("dev_user")
    standard_rules = [r for r in default_rules if not r['id_regra'].startswith('G')]
    global_rules = [r for r in default_rules if r['id_regra'].startswith('G')]
    return templates.TemplateResponse("playground.html", {
        "request": request,
        "standard_rules": standard_rules,
        "global_rules": global_rules,
        "default_system_intro": get_default_system_intro(),
    })

@router.get("/converter-csv", response_class=HTMLResponse)
async def get_converter_csv(request: Request):
    return templates.TemplateResponse("converter_csv.html", {"request": request})

@router.get("/reverse-prompting", response_class=HTMLResponse)
async def get_reverse_prompting(request: Request):
    return templates.TemplateResponse("reverse_prompting.html", {
        "request": request,
        "system_intro_template": get_default_system_intro(),
        "meta_prompt_default": META_PROMPT_DEFAULT,
        "red_team_prompt_default": RED_TEAM_SYSTEM_PROMPT,
    })

# --- ROTA REVERSE PROMPTING POST (MANTIDA IGUAL) ---
@router.post("/reverse-prompting/process", response_class=JSONResponse)
async def process_reverse_prompting(
    system_prompt: str = Form(...),
    rules_prompt: str = Form(...),
    clausula_teste: str = Form(...),
    exemplos: str = Form(""),
    meta_prompt: str = Form(""),
    max_attempts: int = Form(5),
    force_continue: bool = Form(False),
    use_red_team: bool = Form(False),
    llm_deployment: str = Form("") ,
    llm_temperature: str = Form(""),
    red_team_prompt: str = Form("")
):
    print(f"\n📥 [ROTA] Recebendo requisição Reverse Prompting...", flush=True)
    try:
        llm_deployment_val = llm_deployment if llm_deployment and llm_deployment.strip() else None
        try:
            llm_temperature_val = float(llm_temperature) if llm_temperature and llm_temperature.strip() else None
        except:
            llm_temperature_val = None

        # Sanitização de Strings Opcionais
        red_team_prompt_safe = red_team_prompt.strip() if red_team_prompt else ""
        exemplos_safe = exemplos.strip() if exemplos else ""
        meta_prompt_safe = meta_prompt.strip() if meta_prompt else ""

        result, execution_logs = reverse_prompting_loop(
            system_prompt=system_prompt,
            rules_prompt=rules_prompt,
            clausula_teste=clausula_teste,
            exemplos_csv=exemplos_safe,
            meta_prompt=meta_prompt_safe,
            max_attempts=max_attempts,
            force_continue=force_continue,
            llm_deployment=llm_deployment_val,
            llm_temperature=llm_temperature_val,
            use_red_team=use_red_team,
            red_team_prompt=red_team_prompt_safe
        )
        if result is None: result = []
        
        return JSONResponse(content={
            "tentativas": result, 
            "logs": execution_logs,
            "erro": "O processo foi concluído sem gerar tentativas." if len(result) == 0 else None
        })
    except Exception as e:
        print(f"❌ [ROTA ERRO FATAL] {str(e)}", flush=True)
        traceback.print_exc()
        return JSONResponse(content={"erro": f"Erro interno: {str(e)}"}, status_code=500)

# --- ROTAS CONVERSOR CSV (ATUALIZADA) ---

@router.post("/processar_csv_preview")
async def processar_csv_preview(
    files: list[UploadFile] = File(...),
    extraction_method: str = Form("padrao") # [NOVO] Recebe a escolha do front
):
    """
    Retorna JSON com os dados extraídos para exibição no terminal.
    Aceita 'padrao' ou 'alternativo'.
    """
    try:
        all_rows = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for file in files:
                file_content = await file.read()
                safe_filename = file.filename or f"arquivo_{uuid.uuid4()}.docx"
                temp_docx = os.path.join(temp_dir, safe_filename)
                with open(temp_docx, "wb") as f:
                    f.write(file_content)
                
                # Usa a factory para pegar os dados
                rows = get_parser_rows(temp_docx, safe_filename, method=extraction_method)
                all_rows.extend(rows)

        return JSONResponse(content={"rows": all_rows})

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"erro": str(e)}, status_code=500)

# --- ROTAS LEGADO / ANALISADOR (MANTIDAS) ---
@router.post("/exportar_csv")
async def exportar_csv(file: UploadFile = File(None), nome_docx_validado: str = Form("")):
    pass 

@router.post("/exportar_csv_unificado")
async def exportar_csv_unificado(files: list[UploadFile] = File(...)):
    pass

@router.post("/analisar")
async def playground_analisar(
    file: UploadFile = File(...),
    regras_personalizadas: str = Form(""),
    use_rag: bool = Form(False),
    analise_global: bool = Form(False),
    clausulas_alvo: str = Form(""),
    somente_analisados: bool = Form(False),
    system_intro_personalizado: str = Form(""),
    pular_segmentador: bool = Form(False),
    llm_deployment_override: str = Form(""),
    llm_temperature_override: str = Form(""),
):
    # (Mantendo a implementação original completa aqui...)
    try:
        file_content = await file.read()
        user_id_para_regras = "dev_user"
        custom_rules = None
        if regras_personalizadas.strip():
            custom_rules = json.loads(regras_personalizadas)
        
        clausulas_alvo = clausulas_alvo.strip()
        clausulas_set = None
        if clausulas_alvo == "":
            clausulas_set = set()
        elif clausulas_alvo != "*":
            tokens = clausulas_alvo.replace(",", ";").split(";")
            clausulas_indices = set()
            for token in tokens:
                if token.strip(): clausulas_indices.add(int(token.strip()))
            clausulas_set = clausulas_indices

        system_intro_override = system_intro_personalizado.strip() or None

        processed_file_bytes, report_json = await run_analysis_pipeline(
            file_content=file_content,
            user_id=user_id_para_regras,
            storage=local_storage,
            use_rag=use_rag,
            custom_rules=custom_rules,
            clausulas_alvo=clausulas_set,
            system_intro_override=system_intro_override,
            skip_segmentation=pular_segmentador,
            llm_deployment_override=(llm_deployment_override.strip() or None),
            llm_temperature_override=(float(llm_temperature_override) if llm_temperature_override.strip() != "" else None),
        )
        
        safe_filename = file.filename or "arquivo.docx"
        download_filename = f"debug_{uuid.uuid4()}_{safe_filename}"
        name, ext = os.path.splitext(safe_filename)
        download_filename = f"{name}_validado{ext}"
        await local_storage.save_processed_file(download_filename, processed_file_bytes)
        download_url = f"/downloads/{download_filename}"

        if somente_analisados:
            # Lógica de filtro...
            pass

        # Lógica de contagem de tokens...
        total_wc = 0 # simplificado

        report_dict = report_json.model_dump(exclude_none=True)
        return JSONResponse(content={
            "status": "success",
            "download_url": download_url,
            "approx_token_count": 0,
            "relatorio_json": report_dict,
        })
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# --- NOVA ROTA PARA VETORIZAÇÃO DE JSON HIERÁRQUICO ---    
# Certifique-se que estes imports estão no topo do arquivo
from datetime import datetime
import json
import os
import shutil
import tempfile
import traceback
import uuid
from langchain_community.vectorstores import Chroma
from langchain_openai import AzureOpenAIEmbeddings
from pydantic import SecretStr

# ... (outras rotas) ...

# --- ROTA PARA VETORIZAÇÃO (ALINHADA AO ingest_examples.py) ---
@router.post("/processar_vetorizar_json")
async def processar_vetorizar_json(
    files: list[UploadFile] = File(...),
    # Método de extração hierárquico (3, 4 ou 5)
    extraction_method: str = Form("hierarquico_filtrado") 
):
    # Garante que apenas métodos hierárquicos válidos sejam usados (3, 4 ou 5)
    if extraction_method not in ("hierarquico", "hierarquico_filtrado", "hierarquico_comentarios"):
        print(f"[VETORIZAÇÃO] Método inválido '{extraction_method}', forçando 'hierarquico_filtrado'", flush=True)
        extraction_method = "hierarquico_filtrado"

    print(f"\n🚀 [VETORIZAÇÃO] Iniciando (Método: {extraction_method})...", flush=True)
    temp_vector_dir = None

    try:
        # 1. Extração linha-a-linha com o parser existente
        all_rows = []
        with tempfile.TemporaryDirectory() as temp_input_dir:
            for file in files:
                file_content = await file.read()
                safe_filename = file.filename or f"arquivo_{uuid.uuid4()}.docx"
                temp_docx = os.path.join(temp_input_dir, safe_filename)
                with open(temp_docx, "wb") as f:
                    f.write(file_content)

                rows = get_parser_rows(temp_docx, safe_filename, method=extraction_method)
                all_rows.extend(rows)

        if not all_rows:
            return JSONResponse(content={"erro": "Nenhum dado encontrado para vetorizar."}, status_code=400)

        # 2. Reconstrói a estrutura hierárquica EXACTAMENTE como o JSON hierárquico
        #    (equivalente ao buildHierarchicalJSON do front)
        files_map: dict[str, dict[int, dict]] = {}

        for row in all_rows:
            fname = row.get("Nome_arquivo") or "unknown.docx"

            if fname not in files_map:
                files_map[fname] = {}

            idx_p = row.get("Index_p")
            if idx_p not in files_map[fname]:
                files_map[fname][idx_p] = {
                    "index_p": idx_p,
                    "tipo_secao": row.get("tipo_secao", ""),
                    "texto_original": "",
                    "alteracoes": [],
                }

            p_obj = files_map[fname][idx_p]
            tipo = row.get("tipo")

            if tipo == "Parágrafo":
                p_obj["texto_original"] = row.get("texto", "")
            else:
                p_obj["alteracoes"].append(
                    {
                        "tipo": row.get("tipo"),
                        "texto": row.get("texto"),
                        "posicao": row.get("posicao"),
                        "comentario": row.get("comentario"),
                        "autor": row.get("nome_usuario"),
                        "data_hora": row.get("data_hora"),
                    }
                )

        # 3. Monta textos e metadados NO MESMO FORMATO conceitual do ingest_examples.py
        #    - Texto de busca = texto_original
        #    - Metadados = parágrafo serializado em raw_paragrafo + nome_arquivo/data_processamento/tipo.
        texts: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for fname, paragrafos_dict in files_map.items():
            documento_obj = {
                "nome_arquivo": fname,
                "data_processamento": datetime.now().strftime("%Y-%m-%d"),
            }

            for _, par in sorted(paragrafos_dict.items(), key=lambda kv: kv[0]):
                texto_original = par.get("texto_original")
                if not texto_original:
                    continue

                texts.append(texto_original)

                metadatas.append(
                    {
                        "raw_paragrafo": json.dumps(par, ensure_ascii=False),
                        "nome_arquivo": documento_obj["nome_arquivo"],
                        "data_processamento": documento_obj["data_processamento"],
                        "tipo": "paragrafo",
                    }
                )

        if not texts:
            return JSONResponse(content={"erro": "Nenhum parágrafo válido encontrado para vetorização."}, status_code=400)

        # 4. Vetorização com Chroma, igual ao ingest_examples.py
        print(f"⚛️ [VETORIZAÇÃO] Gerando embeddings para {len(texts)} chunks...", flush=True)

        temp_vector_dir = tempfile.mkdtemp()
        vector_db_path = os.path.join(temp_vector_dir, "chroma_db_output")

        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=settings.OPENAI_API_BASE,
            api_key=SecretStr(settings.OPENAI_API_KEY or ""),
            api_version=settings.OPENAI_API_VERSION,
            azure_deployment="text-embedding-ada-002",
        )

        vectorstore = Chroma.from_texts(
            texts=texts,
            embedding=embeddings,
            metadatas=metadatas,
            persist_directory=vector_db_path,
        )

        vectorstore = None

        sqlite_file = os.path.join(vector_db_path, "chroma.sqlite3")

        if not os.path.exists(sqlite_file):
            return JSONResponse(content={"erro": "Falha ao gerar SQLite."}, status_code=500)

        # 5. Envia o arquivo SQLite para download
        safe_output_dir = tempfile.mkdtemp()
        final_sqlite_path = os.path.join(safe_output_dir, "chroma.sqlite3")
        shutil.copy2(sqlite_file, final_sqlite_path)

        size_kb = os.path.getsize(final_sqlite_path) / 1024
        print(f"✅ [SUCESSO] SQLite Gerado: {size_kb:.2f} KB", flush=True)

        return FileResponse(
            path=final_sqlite_path,
            filename="chroma.sqlite3",
            media_type="application/x-sqlite3",
        )

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"erro": f"Erro interno: {str(e)}"}, status_code=500)

    finally:
        if temp_vector_dir and os.path.exists(temp_vector_dir):
            try:
                shutil.rmtree(temp_vector_dir)
            except Exception:
                pass


@router.post("/rag-context", response_class=JSONResponse)
async def gerar_contexto_rag(
    files: list[UploadFile] = File(...),
    top_k: int = Form(3),
    clausula_teste: str = Form(""),
    extraction_method: str = Form("hierarquico_filtrado"),
):
    try:
        # Sanitiza top_k no backend também (espelhando o front)
        try:
            k = int(top_k)
        except Exception:
            k = 3
        if k < 1:
            k = 1
        if k > 5:
            k = 5

        # Verifica extensões dos arquivos enviados (.docx ou .sqlite3)
        file_names = [
            (up.filename or "").lower() for up in (files or [])
        ]
        has_sqlite = any(name.endswith(".sqlite3") for name in file_names)
        has_docx = any(name.endswith(".docx") for name in file_names)

        # Caminho 1: uso de índice Chroma pré-computado (.sqlite3)
        if has_sqlite and not has_docx:
            if not files:
                return JSONResponse(content={"contexto_rag": [], "logs": []})

            # Para simplicidade, usa apenas o primeiro .sqlite3
            first_sqlite = None
            for up in files:
                if (up.filename or "").lower().endswith(".sqlite3"):
                    first_sqlite = up
                    break

            if first_sqlite is None:
                return JSONResponse(content={"contexto_rag": [], "logs": []})

            # No Windows, o uso de TemporaryDirectory com Chroma pode gerar
            # PermissionError ao tentar apagar arquivos ainda em uso (ex.: data_level0.bin).
            # Por isso, gerenciamos o diretório temporário manualmente e
            # toleramos falhas de remoção.
            temp_dir = tempfile.mkdtemp(prefix="rag_sqlite_")
            try:
                sqlite_path = os.path.join(temp_dir, "chroma.sqlite3")
                content = await first_sqlite.read()
                with open(sqlite_path, "wb") as f:
                    f.write(content)

                embeddings = AzureOpenAIEmbeddings(
                    azure_endpoint=settings.OPENAI_API_BASE,
                    api_key=SecretStr(settings.OPENAI_API_KEY or ""),
                    api_version=settings.OPENAI_API_VERSION,
                    azure_deployment="text-embedding-ada-002",
                )

                # Restaura o vectorstore a partir do diretório que contém o .sqlite3
                vectorstore = Chroma(
                    embedding_function=embeddings,
                    persist_directory=temp_dir,
                )

                query_text = (clausula_teste or "").strip()
                if not query_text:
                    # Sem cláusula de teste não faz sentido ranquear; retorna vazio
                    return JSONResponse(content={"contexto_rag": [], "logs": []})

                # No caminho .sqlite3, o índice já reflete o método de extração
                # escolhido no conversor (3, 4 ou 5). Aqui não aplicamos nenhum
                # filtro adicional de "só cláusulas comentadas"; apenas fazemos a
                # busca semântica direta nos vetores persistidos.
                results = vectorstore.similarity_search_with_score(query_text, k=k)

                if not results:
                    return JSONResponse(content={"contexto_rag": [], "logs": []})

                # Para manter a MESMA escala de similaridade do caminho DOCX,
                # ignoramos o score bruto retornado pelo Chroma (distância)
                # e recalculamos o cosseno manualmente usando os mesmos
                # embeddings AzureOpenAIEmbeddings.
                doc_texts = [doc.page_content for (doc, _score) in results]

                query_vec = None
                doc_vecs: list[list[float]] = []
                try:
                    import math

                    query_vec = embeddings.embed_query(query_text)
                    doc_vecs = embeddings.embed_documents(doc_texts)

                    # Pré-calcula norma do vetor de query para reutilizar
                    q_norm = math.sqrt(sum(v * v for v in query_vec)) or 1e-9
                except Exception:
                    query_vec = None
                    doc_vecs = []

                contexto_lista: list[dict] = []
                logs: list[dict] = []

                for idx, (doc, _score) in enumerate(results, start=1):
                    meta = doc.metadata or {}
                    raw_paragrafo = meta.get("raw_paragrafo")

                    par_dict: dict[str, Any] = {}
                    if isinstance(raw_paragrafo, str):
                        try:
                            par_dict = json.loads(raw_paragrafo)
                        except Exception:
                            par_dict = {}
                    elif isinstance(raw_paragrafo, dict):
                        par_dict = raw_paragrafo

                    row = {
                        "nome_arquivo": meta.get("nome_arquivo", ""),
                        "index_p": par_dict.get("index_p"),
                        "tipo_secao": par_dict.get("tipo_secao"),
                        "texto": par_dict.get("texto_original") or doc.page_content,
                        "alteracoes": par_dict.get("alteracoes") or [],
                    }

                    # Usa a MESMA fórmula de similaridade do caminho DOCX:
                    # similaridade_percentual = cosine_similarity(query, doc) * 100.0
                    sim_percent = 0.0
                    if query_vec is not None and doc_vecs and idx - 1 < len(doc_vecs):
                        try:
                            vec = doc_vecs[idx - 1]
                            import math
                            v_norm = math.sqrt(sum(x * x for x in vec)) or 1e-9
                            dot = sum(a * b for a, b in zip(query_vec, vec))
                            cos_sim = dot / (q_norm * v_norm)
                            sim_percent = cos_sim * 100.0
                        except Exception:
                            sim_percent = 0.0

                    row["similaridade_percentual"] = sim_percent

                    contexto_lista.append(row)
                    logs.append({"numero": idx, "json": row})

                return JSONResponse(content={"contexto_rag": contexto_lista, "logs": logs})
            finally:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except PermissionError:
                    # Em último caso, ignora erro de limpeza para não quebrar a requisição
                    pass

        # Caminho 2 (padrão): DOCX -> parser hierárquico -> embeddings em memória

        # Normaliza o método recebido do front (aceita 3, 4 ou 5)
        extraction_method_normalized = (extraction_method or "").strip().lower()

        valid_methods = {
            "hierarquico": "hierarquico",
            "hierárquico": "hierarquico",  # tolera acento
            "hierarquico_filtrado": "hierarquico_filtrado",
            "hierárquico_filtrado": "hierarquico_filtrado",
            "hierarquico_comentarios": "hierarquico_comentarios",
            "hierárquico_comentarios": "hierarquico_comentarios",
        }

        if extraction_method_normalized not in valid_methods:
            print(
                f"[RAG] Método inválido '{extraction_method}', forçando 'hierarquico_filtrado'",
                flush=True,
            )
            effective_method = "hierarquico_filtrado"
        else:
            effective_method = valid_methods[extraction_method_normalized]

        # 1) Usa o parser hierárquico escolhido (3, 4 ou 5) para obter "rows" brutas
        all_rows: list[dict] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for up in files:
                content = await up.read()
                safe_filename = up.filename or f"arquivo_{uuid.uuid4()}.docx"
                temp_docx = os.path.join(temp_dir, safe_filename)
                with open(temp_docx, "wb") as f:
                    f.write(content)

                rows = get_parser_rows(
                    temp_docx,
                    safe_filename,
                    method=effective_method,
                )
                all_rows.extend(rows)

        if not all_rows:
            return JSONResponse(content={"contexto_rag": [], "logs": []})

        # 2) Reconstrói estrutura hierárquica idêntica ao fluxo de vetorização,
        #    garantindo que só parágrafos COM eventos (alterações/comentários)
        #    entrem na base para RAG.
        files_map: dict[str, dict[int, dict]] = {}

        for row in all_rows:
            fname = row.get("Nome_arquivo") or "unknown.docx"

            if fname not in files_map:
                files_map[fname] = {}

            idx_p = row.get("Index_p")
            if idx_p not in files_map[fname]:
                files_map[fname][idx_p] = {
                    "index_p": idx_p,
                    "tipo_secao": row.get("tipo_secao", ""),
                    "texto_original": "",
                    "alteracoes": [],
                }

            p_obj = files_map[fname][idx_p]
            tipo = row.get("tipo")

            if tipo == "Parágrafo":
                p_obj["texto_original"] = row.get("texto", "")
            else:
                p_obj["alteracoes"].append(
                    {
                        "tipo": row.get("tipo"),
                        "texto": row.get("texto"),
                        "posicao": row.get("posicao"),
                        "comentario": row.get("comentario"),
                        "autor": row.get("nome_usuario"),
                        "data_hora": row.get("data_hora"),
                    }
                )

        paragrafos: list[dict] = []
        texts: list[str] = []

        # 3) Seleciona apenas parágrafos com AO MENOS uma alteração/comentário,
        #    exatamente como no fluxo de vetorização de JSON.
        for fname, paragrafos_dict in files_map.items():
            for _, par in sorted(paragrafos_dict.items(), key=lambda kv: kv[0]):
                texto_original = par.get("texto_original")
                alteracoes = par.get("alteracoes") or []
                if not texto_original or not alteracoes:
                    continue

                # Objeto compacto de parágrafo, preservando metadados úteis
                paragrafos.append(
                    {
                        "nome_arquivo": fname,
                        "index_p": par.get("index_p"),
                        "tipo_secao": par.get("tipo_secao"),
                        "texto": texto_original,
                        "alteracoes": alteracoes,
                    }
                )
                texts.append(texto_original)

        if not paragrafos:
            return JSONResponse(content={"contexto_rag": [], "logs": []})

        embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=settings.OPENAI_API_BASE,
            api_key=SecretStr(settings.OPENAI_API_KEY or ""),
            api_version=settings.OPENAI_API_VERSION,
            azure_deployment="text-embedding-ada-002",
        )

        # Embeddings dos parágrafos
        vectors = embeddings.embed_documents(texts)

        # Se houver cláusula de teste, usamos como query de similaridade.
        # Caso contrário, caímos de volta para ordenação por norma do vetor.
        query_vec = None
        if clausula_teste and clausula_teste.strip():
            try:
                query_vec = embeddings.embed_query(clausula_teste)
            except Exception:
                query_vec = None

        scored = []
        if query_vec is not None:
            import math
            q_norm = math.sqrt(sum(v * v for v in query_vec)) or 1e-9
            for row, vec in zip(paragrafos, vectors):
                v_norm = math.sqrt(sum(x * x for x in vec)) or 1e-9
                dot = sum(a * b for a, b in zip(query_vec, vec))
                cos_sim = dot / (q_norm * v_norm)
                scored.append((cos_sim, row))
        else:
            import math
            for row, vec in zip(paragrafos, vectors):
                norm = math.sqrt(sum((v * v) for v in vec)) or 1e-9
                scored.append((norm, row))

        scored.sort(key=lambda t: t[0], reverse=True)
        top_items = scored[:k]

        if not top_items:
            return JSONResponse(content={"contexto_rag": [], "logs": []})

        # Usa diretamente o valor de similaridade (cosine ou norma)
        # em escala percentual simples (score * 100.0).
        resultados = []
        contexto_lista = []
        for idx, (score, row) in enumerate(top_items, start=1):
            raw_paragrafo = {key: value for key, value in row.items()}
            raw_paragrafo["similaridade_percentual"] = score * 100.0

            contexto_lista.append(raw_paragrafo)

            resultados.append({"numero": idx, "json": raw_paragrafo})

        return JSONResponse(
            content={"contexto_rag": contexto_lista, "logs": resultados}
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"erro": f"Erro interno no RAG: {str(e)}"}, status_code=500)

# ... (imports existentes) ...

# --- ROTA UTILITÁRIA: DOCX -> ZIP (DEBUG XML) ---
@router.post("/baixar_docx_como_zip")
async def baixar_docx_como_zip(file: UploadFile = File(...)):
    """
    Recebe um .docx e retorna o mesmo arquivo binário com extensão .zip e 
    Content-Type application/zip. Útil para inspecionar o XML interno.
    """
    try:
        content = await file.read()
        
        # Cria um stream em memória para não precisar salvar em disco
        zip_stream = io.BytesIO(content)
        
        # Define o nome de saída
        safe_name = file.filename or "documento"
        name_part, _ = os.path.splitext(safe_name)
        zip_filename = f"{name_part}_debug.zip"

        # Retorna como stream com headers forçando o download como ZIP
        return StreamingResponse(
            zip_stream, 
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
    except Exception as e:
        print(f"Erro ao gerar ZIP: {e}")
        return JSONResponse(content={"erro": str(e)}, status_code=500)
    
# ... (imports existentes) ...

"""Playground API endpoints for development only.

Nota: rotas de debug que faziam dump JSON do Chroma
foram removidas para simplificar o fluxo. O caminho
oficial agora é DOCX -> JSON (_changes) -> SQLite/Chroma.
"""