from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from arq import ArqRedis
from arq.connections import RedisSettings
from app.core.config import settings
from app.api import endpoints, playground
import os
import redis.asyncio as redis

def create_app() -> FastAPI:
    app = FastAPI(title="Contrato Revisor API")

    # Configuração do CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"], # URL do React/Vite
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Conecta ao Redis na inicialização
    # @app.on_event("startup")
    # async def startup():
    #     try:
    #         app.state.redis_pool = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    #     except Exception as e:
    #         print(f"Redis não disponível: {e}. Usando stub.")
    #         app.state.redis_pool = None

    @app.on_event("shutdown")
    async def shutdown():
        # app.state.redis_pool may not exist if startup didn't create it
        redis_pool = getattr(app.state, "redis_pool", None)
        if redis_pool:
            await redis_pool.close()

    # Inclui as rotas da API
    app.include_router(endpoints.router, prefix="/api", tags=["API"])

    # Inclui o playground APENAS em desenvolvimento
    if settings.ENVIRONMENT == "development":
        app.include_router(playground.router, prefix="/playground", tags=["Playground"])
        
        # Serve arquivos estáticos locais (para downloads de teste)
        processed_dir = os.path.join(os.path.dirname(__file__), "../data/processed")
        os.makedirs(processed_dir, exist_ok=True)
        app.mount("/downloads", StaticFiles(directory=processed_dir), name="downloads")


    return app

app = create_app()