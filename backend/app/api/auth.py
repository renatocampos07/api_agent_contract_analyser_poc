from fastapi import Depends, HTTPException, status
from app.core.config import settings
from app.models.pydantic_models import User

# --- Lógica de Produção (Stub) ---
async def get_current_user_production(token: str = Depends(...)): # Substituir '...' pelo OAuht2 scheme
    # raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    # Lógica real de validação do token do Azure AD (MSAL) aqui
    return User(id="user_from_token", name="Usuário Real")

# --- Lógica de Desenvolvimento (Stub) ---
async def get_current_user_development():
    # Retorna um usuário falso sem checagem
    return User(id="dev_user_123", name="Usuário de Teste")

# --- A FÁBRICA ---
def get_auth_dependency():
    """Retorna a dependência de autenticação correta."""
    if settings.ENVIRONMENT == "development" or settings.AUTH_TYPE == "none":
        return get_current_user_development
    else:
        return get_current_user_production