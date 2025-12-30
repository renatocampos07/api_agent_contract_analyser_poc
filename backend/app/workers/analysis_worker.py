import redis
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import settings
from app.services.storage import get_storage_service
from app.analysis.orchestrator import run_analysis_pipeline
import uuid

# Esta é a tarefa que será executada pelo worker
async def analisar_documento_task(ctx, user_id: str, file_name: str, file_path_original: str, use_rag: bool):
    """
    Tarefa ARQ para processar o documento em segundo plano.
    """
    print(f"Iniciando job {ctx['job_id']} para {file_name}...")
    storage = get_storage_service()
    
    try:
        # 1. Ler o arquivo original do storage
        file_content = await storage.get_file_content(file_path_original)
        
        # 2. Rodar o pipeline de análise (a parte lenta)
        processed_file_bytes, report_json, _ = await run_analysis_pipeline(
            file_content, user_id, storage, use_rag
        )
        
        # 3. Salvar os dois artefatos (docx e json)
        processed_file_name = f"revisado_{file_name}"
        report_file_name = f"relatorio_{uuid.uuid4()}.json"

        processed_docx_path = await storage.save_processed_file(processed_file_name, processed_file_bytes)
        report_json_path = await storage.save_processed_file(
            report_file_name,
            report_json.model_dump_json(exclude_none=True).encode('utf-8')
        )

        print(f"Job {ctx['job_id']} concluído. Arquivo em: {processed_docx_path}")
        
        # Retorna os caminhos para o status do job
        return {
            "docx_path": processed_docx_path,
            "report_path": report_json_path,
            "report_data": report_json.model_dump(exclude_none=True),
        }

    except Exception as e:
        print(f"Erro no job {ctx['job_id']}: {e}")
        raise

# Configurações do ARQ
REDIS_SETTINGS = RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

async def get_redis_pool():
    return await create_pool(REDIS_SETTINGS)

# Classe para ser usada pelo worker
class WorkerSettings:
    functions = [analisar_documento_task]
    redis_settings = REDIS_SETTINGS