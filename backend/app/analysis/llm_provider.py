
from app.core.config import settings
from langchain_openai import AzureChatOpenAI
from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

def get_chat_llm(deployment_override: str | None = None, temperature_override: float | None = None):
    provider = settings.LLM_PROVIDER
    
    if provider == "azure":
        if not all([settings.OPENAI_API_BASE, settings.OPENAI_API_KEY, settings.OPENAI_API_DEPLOYMENT_NAME]):
            raise ValueError("Credenciais Azure OpenAI não configuradas no .env")
        deployment = (deployment_override or settings.OPENAI_API_DEPLOYMENT_NAME)
        # Nota: alguns modelos (ex.: gpt-5-mini) não aceitam temperature. Incluímos apenas quando apropriado.
        if (deployment or "").lower().startswith("gpt-5"):
            return AzureChatOpenAI(
                api_version=settings.OPENAI_API_VERSION,
                azure_endpoint=settings.OPENAI_API_BASE,
                api_key=SecretStr(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None,
                azure_deployment=deployment,
            )
        else:
            # Respeita override quando fornecido; caso contrário, usa 0 (determinístico)
            temp = 0 if temperature_override is None else float(temperature_override)
            return AzureChatOpenAI(
                api_version=settings.OPENAI_API_VERSION,
                azure_endpoint=settings.OPENAI_API_BASE,
                api_key=SecretStr(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None,
                azure_deployment=deployment,
                temperature=temp,
            )
    
    elif provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("Chave ANTHROPIC_API_KEY não configurada no .env")
        return ChatAnthropic(
            model_name="claude-3-5-sonnet-20240620",
            api_key=SecretStr(settings.ANTHROPIC_API_KEY or ""),
            timeout=None,
            stop=None,
        )
    
    raise ValueError(f"LLM Provider '{provider}' não suportado")
