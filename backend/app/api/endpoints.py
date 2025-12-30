from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, Request
from app.models.pydantic_models import User, JobStatus, RelatorioAnaliseJSON
from app.services.storage import get_storage_service, AbstractStorage
from app.api.auth import get_auth_dependency
import uuid

router = APIRouter()
auth_dependency = Depends(get_auth_dependency())

@router.post("/iniciar_analise", response_model=JobStatus)
async def iniciar_analise(
    request: Request,
    file: UploadFile = File(...),
    use_rag: bool = File(False),
    current_user: User = auth_dependency,
    storage: AbstractStorage = Depends(get_storage_service)
):
    try:
        file_content = await file.read()
        file_name = file.filename or f"{uuid.uuid4()}.docx"
        
        # 1. Salva o arquivo original
        original_path = await storage.save_upload_file(file_name, file_content)
        
        # 2. Enfileira a tarefa
        redis = request.app.state.redis_pool
        job = await redis.enqueue_job(
            "analisar_documento_task",
            user_id=current_user.id,
            file_name=file_name,
            file_path_original=original_path,
            use_rag=use_rag
        )
        
        return JobStatus(status="enqueued", job_id=job.job_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(
    job_id: str, 
    request: Request,
    current_user: User = auth_dependency,
    storage: AbstractStorage = Depends(get_storage_service)
):
    redis = request.app.state.redis_pool
    job = await redis.job_result(job_id)
    
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    status = job.status.value
    
    if status == "complete":
        result = await job.result()
        # Em dev, criamos um link de download local
        # Em prod, 'docx_path' seria uma URL do Azure Blob
        download_url = f"/downloads/{result['docx_path'].split('/')[-1]}" if settings.ENVIRONMENT == "development" else result['docx_path']

        return JobStatus(
            status="complete",
            job_id=job_id,
            resultado=RelatorioAnaliseJSON(**result['report_data']),
            download_url=download_url
        )
    elif status in ["queued", "in_progress"]:
        return JobStatus(status=status, job_id=job_id)
    elif status == "failed":
        return JobStatus(status=f"failed: {job.result_info}", job_id=job_id)
        
    return JobStatus(status=status, job_id=job_id)