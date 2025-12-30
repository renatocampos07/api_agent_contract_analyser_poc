from app.core.config import settings
import json
import os
from pathlib import Path

# Define o diretório base de dados local
LOCAL_DATA_PATH = Path(__file__).parent.parent.parent / "data"
LOCAL_RULES_PATH = LOCAL_DATA_PATH / "rules"
LOCAL_UPLOADS_PATH = LOCAL_DATA_PATH / "uploads"
LOCAL_PROCESSED_PATH = LOCAL_DATA_PATH / "processed"

class AbstractStorage:
    async def get_rules(self, user_id: str) -> list:
        raise NotImplementedError
    async def save_rules(self, user_id: str, rules: dict):
        raise NotImplementedError
    async def save_upload_file(self, file_name: str, file_content: bytes) -> str:
        raise NotImplementedError
    async def save_processed_file(self, file_name: str, file_content: bytes) -> str:
        raise NotImplementedError
    async def get_file_content(self, file_path: str) -> bytes:
        raise NotImplementedError

class LocalFileStorage(AbstractStorage):
    def __init__(self):
        LOCAL_RULES_PATH.mkdir(parents=True, exist_ok=True)
        LOCAL_UPLOADS_PATH.mkdir(parents=True, exist_ok=True)
        LOCAL_PROCESSED_PATH.mkdir(parents=True, exist_ok=True)

    async def get_rules(self, user_id: str) -> list:
        # Tenta carregar regras do usuário, senão, carrega as padrão
        user_rules_file = LOCAL_RULES_PATH / f"{user_id}.json"
        if user_rules_file.exists():
            with open(user_rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Carrega regras padrão
        default_rules_file = LOCAL_DATA_PATH / "regras_padrao.json"
        if default_rules_file.exists():
            with open(default_rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    async def save_upload_file(self, file_name: str, file_content: bytes) -> str:
        file_path = LOCAL_UPLOADS_PATH / file_name
        with open(file_path, 'wb') as f:
            f.write(file_content)
        return str(file_path) # Retorna o caminho absoluto

    async def save_processed_file(self, file_name: str, file_content: bytes) -> str:
        file_path = LOCAL_PROCESSED_PATH / file_name
        with open(file_path, 'wb') as f:
            f.write(file_content)
        return str(file_path)

    async def get_file_content(self, file_path: str) -> bytes:
        with open(file_path, 'rb') as f:
            return f.read()

class AzureBlobStorage(AbstractStorage):
    # STUB para produção
    async def get_rules(self, user_id: str) -> list:
        print("LÓGICA DO AZURE BLOB: Buscando regras...")
        # Lógica para baixar 'rules/user_id.json' ou 'rules/regras_padrao.json'
        return await LocalFileStorage().get_rules(user_id) # Simula por enquanto

    async def save_upload_file(self, file_name: str, file_content: bytes) -> str:
        print("LÓGICA DO AZURE BLOB: Salvando upload...")
        # Lógica para salvar em 'uploads/{file_name}'
        return f"azure://uploads/{file_name}" # Retorna o URI do Blob

    # ... (Implementar outros métodos)

def get_storage_service() -> AbstractStorage:
    if settings.ENVIRONMENT == "development" or settings.STORAGE_TYPE == "local":
        return LocalFileStorage()
    else:
        return AzureBlobStorage()