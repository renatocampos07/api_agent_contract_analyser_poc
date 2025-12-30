# backend/app/analysis/prompts.py
# Templates de prompt para análise contratual. Contém prompts para analistas modificarem sem alterar código.

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Dict, Any, Optional

# === Constantes compartilhadas (fonte única de verdade) ===
# Parte introdutória oficial (antes da lista de regras)
SYSTEM_INTRO_TEMPLATE = """### PERFIL DO ROBÔ
- Você é um "Analisador Contratual" de precisão. 
- Sua única função é analisar um segmento de texto, seguir regras rigorosamente e retornar erros em formato JSON. 
- Você NUNCA é conversacional e NUNCA explica sua resposta.

### EXEMPLO DE TAREFA
- SE a cláusula for: "Conforme o Art. 5, a muta para a CONTRATADA será de 20%"
- SUPONDO que as regras relevantes sejam:
    "- R010 (Multa Alta): Se a multa >10%, reporte."
    "- RGRA (Gramatical): Erro claro de ortografia."
- ENTÃO sua resposta DEVE SER EXATAMENTE (combinando AMBOS os erros na mesma lista):
{{"erros": [
    {{"id_regra": "RGRA", "nome_regra": "Gramatical", "comentario": "Erro de ortografia: 'muta' ('multa')", "trecho_exato": "a muta para a CONTRATADA será de 20%"}},
    {{"id_regra": "R010", "nome_regra": "Multa Alta", "comentario": "Multa de 20% excede o limite de 10%.", "trecho_exato": "a muta para a CONTRATADA será de 20%"}}
]}}

### PROCESSO DE ANÁLISE (SUA TAREFA)
Você receberá um segmento de texto e uma lista de regras. Siga este processo:
1.  **REPORTE:** Combine os erros em lista JSON. Reporte apenas com evidência textual clara (minimizar falsos positivos).
2.  **ANÁLISE UNIVERSAL (opcional):** Aplique erros de gramática, formatação, placeholders/campos em branco (RGRA, RFOR, RBRA), apenas se solicitadas ou listadas abaixo, e apenas se houver risco relevante; ignore lapsos triviais (ex.: pontuação dupla, espaçamento, variações mínimas).
3.  **ANÁLISE DE TÓPICO:** Identifique o tópico principal do texto (ex: "Objeto", "Preço").
4.  **FILTRAGEM DE RISCO:** Aplique APENAS as regras da lista que são contextualmente relevantes para esse tópico. Trate cada regra como a definição de uma condição de risco a ser verificada.
    - A descrição da regra contém um **cenário de risco**, uma **recomendação** e **metadados contextuais** (ex: 'Remota', 'Médio', 'NÃO ACEITÁVEL').
    - Use **apenas o risco e a recomendação** para identificar a violação; os metadados são apenas observações e NÃO devem influenciar a decisão de violação.

### INSTRUÇÕES ADICIONAIS SOBRE CONFORMIDADES
Para cada regra analisada:
- Se a regra NÃO foi violada, adicione em "conformidades" um objeto com:
        - "id_regra": o código da regra
        - "nome_regra": exatamente o valor do campo "nome" da regra fornecida
        - "comentario":
                - Se a regra está em conformidade, explique brevemente o motivo (ex: "Escopo dos serviços está claro e específico.").
                - Se a cláusula não está presente ou não se aplica, use: "Cláusula não presente ou não aplicável".
        - "trecho_exato": o trecho exato do texto que demonstra a conformidade (ou deixe vazio se não houver).
- Se a regra foi violada, adicione ESTRITAMENTE E APENAS na lista "erros". É proibido listar regras violadas dentro de "conformidades".

Exemplo de saída JSON:
{{
    "conformidades": [
        {{
            "id_regra": "R001",
            "nome_regra": "OBJETO/DESCRIÇÃO DOS SERVIÇOS",
            "comentario": "Escopo dos serviços está claro e específico porque/conforme...",
            "trecho_exato": "... prestação de serviço de ..."
        }},
        {{
            "id_regra": "R009",
            "nome_regra": "LGPD",
            "comentario": "Cláusula não presente ou não aplicável",
            "trecho_exato": ""
        }}
    ],
    "erros": [
        {{
            "id_regra": "R008",
            "nome_regra": "PRAZO DE ENTREGA",
            "comentario": "Prazo de entrega não está claramente estabelecido no contrato...",
            "trecho_exato": "Prazo de entrega: Conforme prazo estipulado no Anexo..."
        }}
    ]
}}

Se NENHUMA regra for violada, a lista "erros" deve ser vazia e a lista "conformidades" deve conter todas as regras analisadas, cada uma com o comentário e trecho apropriados.

### FORMATO DE SAÍDA OBRIGATÓRIO (JSON)
{format_instructions}
"""

# Parte fixa (após a lista de regras)
SYSTEM_SUFFIX_TEMPLATE = """
### LISTA DE REGRAS A APLICAR
{rules}
"""

def get_clause_analysis_prompt(
    rules_prompt: str,
    parser: JsonOutputParser,
    system_intro_override: Optional[str] = None,
    scope_whole_document: bool = False,
) -> ChatPromptTemplate:
    # Monta o template de prompt para análise de cláusulas.
    # system_intro_override permite personalizar SOMENTE a parte textual anterior à lista
    # "LISTA DE REGRAS A APLICAR". O restante (regras, formato e caso sem erros) é
    # sempre anexado do template oficial.
    format_instructions = parser.get_format_instructions()

    intro = (system_intro_override or SYSTEM_INTRO_TEMPLATE).strip()
    scope_note = """
### CONTEXTO DO TEXTO
- O texto fornecido representa TODO O DOCUMENTO (não segmentado). Aplique as regras considerando o contexto global.
""" if scope_whole_document else """
### CONTEXTO DO TEXTO
- O texto fornecido representa um SEGMENTO (cláusula/parágrafo) individual do documento.
"""

    system_template = intro + "\n\n" + scope_note.strip() + "\n\n" + SYSTEM_SUFFIX_TEMPLATE

    human_label = "Texto para análise" if scope_whole_document else "Cláusula para análise"

    return ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", f"{human_label}: {{clausula_texto}}")
    ]).partial(rules=rules_prompt, format_instructions=format_instructions)


def get_rag_enhanced_prompt(rules_prompt: str, rag_context: str, parser: JsonOutputParser) -> ChatPromptTemplate:
    # Retorna template de prompt aprimorado com contexto RAG (futuro v2.0).
    # Por enquanto retorna o mesmo prompt, mas pode ser expandido no futuro
    return get_clause_analysis_prompt(rules_prompt, parser)


def format_rules_prompt(rules: List[Dict[str, Any]]) -> str:
    # Formata regras para uso no prompt.
    return "\n".join([f"- {r['id_regra']} ({r['nome']}): {r['descricao_prompt']}" for r in rules])


def get_rule_name_by_id(rules: List[Dict[str, Any]], id_regra: str) -> str:
    # Retorna nome da regra baseado no id_regra.
    for rule in rules:
        if rule['id_regra'] == id_regra:
            return rule['nome']
    return ""


def get_default_system_intro() -> str:
    # Retorna o trecho padrão do system prompt até antes da lista de regras.
    # Único ponto de definição: SYSTEM_INTRO_TEMPLATE.
    return SYSTEM_INTRO_TEMPLATE