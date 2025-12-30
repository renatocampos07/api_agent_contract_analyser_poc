#!/usr/bin/env python3
"""
Script rápido para testar a integração com a API LLM.
"""

import asyncio
from app.analysis.llm_provider import get_chat_llm

async def test_llm():
    try:
        llm = get_chat_llm()
        print(f"LLM configurado: {type(llm).__name__}")

        # Teste simples
        response = await llm.ainvoke("Olá, você é um assistente de análise de contratos?")
        print("Resposta da LLM:")
        print(response.content)

    except Exception as e:
        print(f"Erro ao testar LLM: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm())