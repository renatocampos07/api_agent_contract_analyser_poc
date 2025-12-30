from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class User(BaseModel):
    id: str = "poc_user"
    name: str = "Usuário PoC"

class ErroContratual(BaseModel):
    id_regra: str
    nome: Optional[str] = None
    comentario: Optional[str] = None
    trecho_exato: Optional[str] = None
    trecho_marcado: Optional[str] = None

class AnaliseClausula(BaseModel):
    id_clausula: str
    titulo: str
    erros_encontrados: List[ErroContratual] = []
    texto_original: str

class RelatorioAnaliseJSON(BaseModel):
    nome_arquivo: str
    data_analise: str
    erros_globais: List[ErroContratual] = []
    clausulas: List[AnaliseClausula] = []
    conformidades: Optional[List[Dict]] = None  # Sessão de conformidades IA (debug/playground)

class ListaDeErros(BaseModel):
    erros: List[ErroContratual] = Field(description="Uma lista de todos os erros encontrados na cláusula.")

class JobStatus(BaseModel):
    status: str
    job_id: str
    resultado: Optional[RelatorioAnaliseJSON] = None
    download_url: Optional[str] = None