import json
import re
import sys
import io
from typing import List, Dict, Any, Optional
from app.analysis.prompts import get_clause_analysis_prompt
from app.analysis.llm_provider import get_chat_llm
from langchain_core.output_parsers import JsonOutputParser

# --- NOVO: PROMPT DO AGENTE RED TEAM (VERSÃO FINAL COM REALISMO E RENDIÇÃO) ---
RED_TEAM_SYSTEM_PROMPT = """
Você é o **Advogado do Diabo**, especialista em "Red Teaming" de contratos corporativos.
Sua função é testar a robustez da Regra de Compliance, MAS mantendo os pés no chão da realidade jurídica.

ENTRADAS:
1. REGRA ATUAL: A lógica que está sendo testada.
2. CLÁUSULA ALVO (USUÁRIO): O texto original.
3. STATUS DA DETECÇÃO: Se a regra pegou ou não o erro.
4. GROUND TRUTH: A política real da empresa.

---
### SUA MISSÃO
Tente encontrar uma brecha na Regra Atual criando uma **Cláusula Armadilha**.

**CENÁRIO A (Ataque de Evasão):** Se a regra já detectou o erro do usuário, tente criar uma variação do texto que mantenha o risco jurídico mas **escape** da lógica da regra (ex: usando sinônimos complexos, mudando a estrutura frasal, escrevendo números por extenso).
**CENÁRIO B (Ataque de Óbvio):** Se a regra NÃO detectou, crie um caso ainda mais gritante para provar a falha.
**CENÁRIO C (RENDIÇÃO/APROVAÇÃO):**
Se você analisar a regra e concluir que ela é **ROBUSTA**, cobrindo bem os sinônimos e variações lógicas sem ser rígida demais, **NÃO INVENTE UM ATAQUE FORÇADO**.
Admitir que o Engenheiro fez um bom trabalho é parte da sua função.

---
### 🚫 RESTRIÇÕES DE REALISMO (Anti-Alucinação)
1. **Plausibilidade:** A cláusula armadilha deve parecer escrita por um advogado real ou um fornecedor tentando levar vantagem. Não crie textos poéticos ou informais.
2. **Contexto Jurídico:** Não invente Leis, Artigos ou Decretos que não existem. Use referências genéricas ("legislação aplicável", "Código Civil") se necessário.
3. **Foco no Risco:** Ataque a lógica do risco (prazos, valores, responsabilidades).
4. **Evite "Edge Cases" Matemáticos:** Não use números absurdos apenas para testar o limite da regra (ex: se o mínimo é 30 dias, **NÃO** use "29 dias"). Use prazos ruins comuns de mercado (ex: "5 dias", "imediato", "15 dias", "48 horas").

---
### SAÍDA OBRIGATÓRIA (JSON PURO)
{
    "raciocinio": "Explicação técnica da brecha encontrada (ou um elogio breve se a regra for aprovada).",
    "clausula_armadilha": "O texto da armadilha (ou escreva 'NENHUMA' se a regra for robusta)."
}
"""

def run_red_team_agent(llm, system_prompt, regra_atual, clausula_user, status_auditoria, ground_truth):
    """Executa o Agente Adversário. (Assume que system_prompt já vem sanitizado com {{ }})."""
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        # Monta o template. O system_prompt já deve vir com chaves escapadas {{ }}.
        # As chaves {regra}, {clausula}, etc. no final são as variáveis reais do LangChain.
        final_prompt_str = system_prompt + """
        \n--- DADOS DA RODADA ---
        REGRA ATUAL: {regra}
        CLÁUSULA ALVO (USUÁRIO): {clausula}
        STATUS DA DETECÇÃO (USUÁRIO): {status}
        GROUND TRUTH: {ground_truth}
        """
        prompt = ChatPromptTemplate.from_template(final_prompt_str)
        chain = prompt | llm | JsonOutputParser()
        result = chain.invoke({
            "regra": regra_atual,
            "clausula": clausula_user,
            "status": status_auditoria,
            "ground_truth": ground_truth or "Não fornecido (Deduza pelo contexto)."
        })
        return result
    except Exception as e:
        print(f"❌ [RED TEAM ERRO] {str(e)}", flush=True)
        return None

# --- TEMPLATE REFATORADO COM TABELA E ESTRATÉGIA GRADUAL ---
META_PROMPT_DEFAULT = """
### META PROMPT (JSON AGENT) – RegraBuilder-AI

Você é o **RegraBuilder-AI**, engenheiro especialista em regras para o "Robô Analisador JSON".
Sua função é refinar a **definição textual** de uma regra de compliance, ajustando-a conforme a fase da tentativa atual ({{tentativa_atual}} de {{max_tentativas}}).

**Restrição de Integridade:**
Os campos `id_regra` (R0xx) e `nome` [Título] são chaves de identificação do sistema. **Você deve mantê-los estritamente idênticos aos valores de entrada em todas as tentativas**, sem correções, expansões ou alterações criativas. Sua evolução deve ocorrer exclusivamente no campo `descricao_prompt`.

O Agente que lerá sua regra é um ROBÔ LÓGICO E NÃO CONVERSACIONAL.
Ele precisa de instruções do tipo: **"SE [condição no texto] ENTÃO [reporte erro] COM [recomendação]."**

---
### 1. ESTRATÉGIA EVOLUTIVA (O Segredo do Ritmo)

#### Tentativas Iniciais (1 → ~30%)
Estilo: **MACRO-ESTRUTURAL / (ESCOPO/CONCISA)**
Objetivo: Garantir que o contrato aborda o tema, sem validar detalhes finos.
• **Mentalidade:** "A cláusula existe e faz sentido juridicamente?"
• **Formato:** "Verifique a cláusula de [Objeto]. Se ela estiver ausente, vaga ou tratar de assunto divergente, reporte erro."
• **O que evitar:** Não aplique restrições numéricas rígidas ou proibições de palavras específicas nesta fase.

#### Tentativas Intermediárias (~30% → ~70%)
Estilo: **VALIDAÇÃO DE NEGÓCIO (LÓGICA/ELABORADA)**
Objetivo: Aplicar a regra de negócio (Golden Values).
• **Mentalidade:** "A cláusula respeita os limites da empresa?"
• **Formato:** "Analise os valores e condições. Se o prazo for inferior a [X] ou se a multa exceder [Y], reporte erro."
• **Ação:** Agora insira os **números-chave** e lógicas de "Contratante vs Contratada".

#### Tentativas Finais (~70% → 100%)
Estilo: **LÓGICA LITERAL (OVERFITTING/EXAUSTIVA)**
Objetivo: Caça-palavras de tolerância zero.
• **Mentalidade:** "O texto contém a frase proibida exata?"
• **Formato:** "ATENÇÃO: Busque exatamente as strings [Frase 1] ou [Frase 2]. Se encontrar, reporte erro crítico imediatamente."
• **Ação:** Hardcoding de termos do Ground Truth.

---
### 2. COMO PROCESSAR OS DADOS
1.  **Histórico:** Se a tentativa anterior falhou em detectar (Falso Negativo), avance a lógica de "Estrutural" para "Validação de Valor".
2.  **Ground Truth:** Use para calibrar a severidade da recomendação no texto descritivo.
3.  **Cláusula Teste ({{exemplo_texto_original}}):** Use para testar mentalmente se sua lógica "SE" seria ativada.

---
---
### 3. FORMATO OBRIGATÓRIO DE SAÍDA (JSON)

Você deve retornar **EXCLUSIVAMENTE** um objeto JSON.
O campo `descricao_prompt` deve conter a regra completa em texto corrido (sem Markdown, sem bullets).

'''
{
    "id_regra": "{{id_regra}}",
    "nome": "{{titulo_regra}}",
    "descricao_prompt": "Escreva aqui a definição lógica da regra conforme a fase. Ex: 'Analise a cláusula de Pagamento. Se o prazo for inferior a 30 dias (ex. ilustrativo) ou omitido, reporte erro de Fluxo de Caixa. Recomendação: Ajustar para 30 dias (ex. ilustrativo).'"
}
'''

**Regras para o campo descricao_prompt:**
1.  Deve ser uma frase imperativa ou condicional.
2.  Deve incluir a **Condição de Erro** (Risco) e a **Recomendação** (Ação).
3.  Não use quebras de linha excessivas, o Robô JSON processa melhor parágrafos densos.
4.  Não use estruturas A/B/C/D. Se houver múltiplas lógicas, escreva: "Se X, erro A. Se Y, erro B." na mesma string.

### **4. DADOS BRUTOS**

Regra Atual:
{{json_rule}}

Histórico:
{{tabela_historico}}

Cláusula Teste:
{{exemplo_texto_original}}

Ground Truth:
{{exemplo_comentario}}

### **SUA SAÍDA: APENAS O JSON**
"""

def extrair_json_robusto(texto: str) -> str:
    """Encontra o primeiro '{' e o último '}' para isolar o JSON."""
    if not texto: return "{}"
    texto = texto.replace("```json", "").replace("```", "")
    idx_inicio = texto.find("{")
    idx_fim = texto.rfind("}")
    if idx_inicio != -1 and idx_fim != -1:
        return texto[idx_inicio : idx_fim + 1]
    return texto.strip()

def reverse_prompting_loop(
    system_prompt: str,
    rules_prompt: str,
    clausula_teste: str,
    exemplos_csv: str, 
    meta_prompt: str,
    max_attempts: int = 5,
    llm_deployment: Optional[str] = None,
    llm_temperature: Optional[float] = None,
    force_continue: bool = False,
    use_red_team: bool = False,
    red_team_prompt: str = '',
):
    # --- CONFIG DE CAPTURA DE LOGS ---
    log_capture_string = io.StringIO()
    class Tee(object):
        def __init__(self, *files): self.files = files
        def write(self, obj):
            for f in self.files: f.write(obj); f.flush()
        def flush(self):
            for f in self.files: f.flush()
    original_stdout = sys.stdout
    sys.stdout = Tee(sys.stdout, log_capture_string)

    try:
        # --- CONFIGURAÇÃO VISUAL ---
        # tr: usado apenas para resumos curtos de uma linha (status, regras curtas)
        tr = lambda s, l=150: str(s).replace('\n', ' ').replace('\r', '').strip()[:l] + "..." if len(str(s)) > l else str(s).replace('\n', ' ').strip()
        sep = f"\n   {'-'*60}" 

        # --- TRAVA DE SEGURANÇA ---
        LIMITE_MAXIMO_BACKEND = 10
        if max_attempts > LIMITE_MAXIMO_BACKEND: max_attempts = LIMITE_MAXIMO_BACKEND

        tentativas = []
        red_team_alerts = []
        parser = JsonOutputParser()

        if not clausula_teste or not clausula_teste.strip():
            clausula_teste = "[ERRO: Cláusula vazia]"
        if not red_team_prompt or not red_team_prompt.strip():
            red_team_prompt = RED_TEAM_SYSTEM_PROMPT

        print(f"\n🔌 [INIT] Conectando ao LLM...", flush=True)
        try:
            llm = get_chat_llm(llm_deployment, llm_temperature)
        except Exception as e:
            print(f"❌ [ERRO CRÍTICO] {str(e)}", flush=True)
            raise RuntimeError(f"Erro LLM: {str(e)}")

        meta_rule = None 
        metadados_regra = None

        print("\n" + "="*80)
        print(f"🚀 INICIANDO PIPELINE DE REFINAMENTO (Máx: {max_attempts})")
        print("="*80)

        for attempt in range(1, max_attempts + 1):
            print(f"\n🔸 [TENTATIVA {attempt}/{max_attempts}] ================================================")

            # --- FASE 1: DEFINIÇÃO ---
            if attempt == 1:
                rules_current = rules_prompt.strip() or "Regra Genérica"
                metadados_regra = {"origem": "Input Usuário"}
            else:
                rules_current = meta_rule if meta_rule else rules_prompt
                metadados_regra = {"origem": "Meta Prompt"}

            # --- FASE 2: AUDITOR (Análise) ---
            print(sep)
            print(f"   🔍 [AUDITOR] Analisando...", flush=True)
            
            rules_safe = rules_current.replace("{", "{{").replace("}", "}}")
            system_safe = system_prompt.replace("{", "{{").replace("}", "}}")
            red_team_safe = red_team_prompt.replace("{", "{{").replace("}", "}}")

            try:
                prompt_template = get_clause_analysis_prompt(rules_safe, parser, system_intro_override=system_safe)
                prompt_final = prompt_template.format_prompt(clausula_texto=clausula_teste).to_string()
                
                # LOG: Prompt com quebras reais
                print(f"      ➤ INPUT PROMPT COMPLETO:\n{prompt_final.strip()}\n")

                resp_obj = llm.invoke(prompt_final)
                resp_texto = resp_obj.content if hasattr(resp_obj, 'content') else str(resp_obj)
                
                resp_texto_clean = resp_texto.replace('```json', '').replace('```', '').strip()
                lista_erros: list[Any] = []
                try: data_resp = json.loads(resp_texto_clean)
                except: data_resp = None

                if isinstance(data_resp, dict):
                    if "erros" in data_resp and data_resp["erros"]: lista_erros = data_resp["erros"]
                    elif "comments" in data_resp and data_resp["comments"]: lista_erros = data_resp["comments"]
                    elif "error" in data_resp and data_resp["error"]: lista_erros = [data_resp["error"]]
                else:
                    if "erros" in resp_texto_clean.lower() and "[" in resp_texto_clean and not re.search(r'\[\s*\]', resp_texto_clean):
                        lista_erros = ["_json_broken_but_detected_"]

                icone_res = "✅ DETECTOU" if lista_erros else "❌ PASSOU"
                print(f"      📊 DECISÃO: {icone_res}")

            except Exception as e:
                print(f"      ❌ [ERRO AUDITOR] {e}", flush=True)
                resp_texto = "{}"
                lista_erros = []
                prompt_final = "Erro"

            status = "✅ Detectou" if lista_erros else "❌ Falhou"
            tentativa_atual_dict = {
                "tentativa": attempt,
                "prompt_usado": prompt_final,
                "resposta_ia": resp_texto,
                "status": status,
                "regras_aplicadas_texto": rules_current,
                "regras_metadados": metadados_regra or {},
                "red_team_data": None
            }

            # --- FASE 3: RED TEAM (Desafiante) ---
            if use_red_team:
                print(sep)
                print(f"   ⚔️ [DESAFIANTE] Testando robustez...", flush=True)
                status_logico = "DETECTOU" if lista_erros else "NÃO DETECTOU"
                
                # Monta visualmente o prompt (simulação para log com quebras reais)
                debug_rt_prompt = red_team_safe + \
                    f"\n\n--- DADOS (INJETADOS) ---\nREGRA: {rules_current}\nCLÁUSULA: {clausula_teste}\nSTATUS: {status_logico}\nGROUND TRUTH: {exemplos_csv}"
                
                print(f"      ➤ INPUT PROMPT COMPLETO:\n{debug_rt_prompt.strip()}\n")

                attack_data = run_red_team_agent(
                    llm=llm,
                    system_prompt=red_team_safe,
                    regra_atual=rules_current,
                    clausula_user=clausula_teste,
                    status_auditoria=status_logico,
                    ground_truth=exemplos_csv
                )
                
                if attack_data:
                    clausula_arm = attack_data.get('clausula_armadilha', 'N/A')
                    if "NENHUMA" in clausula_arm.upper():
                        print(f"      🛡️ DECISÃO: REGRA APROVADA")
                    else:
                        print(f"      💣 DECISÃO: ATAQUE GERADO")

                    tentativa_atual_dict["red_team_data"] = attack_data
                    alert_msg = json.dumps(attack_data, ensure_ascii=False)
                    # CORREÇÃO DE NOME NO HISTÓRICO
                    red_team_alerts.append(f"Feedback Desafiante (T{attempt}): {alert_msg}")

            tentativas.append(tentativa_atual_dict)

            # --- FASE 4: DECISÃO ---
            if lista_erros and not force_continue:
                print(f"\n✨ SUCESSO! Regra detectou o erro na tentativa {attempt}.", flush=True)
                break
            if attempt == max_attempts:
                print(f"\n🛑 FIM (Limite alcançado).", flush=True)
                break

            # --- FASE 5: ENGENHEIRO (Meta Prompt) ---
            print(sep)
            print(f"   🧠 [ENGENHEIRO] Refinando regra...", flush=True)
            
            tabela_historico = ""
            for t in tentativas:
                tabela_historico += f"#### TENTATIVA {t['tentativa']} ({t['status']})\nRegra: {t['regras_aplicadas_texto']}\n---\n"
            
            # CORREÇÃO DE NOME NO CABEÇALHO DO HISTÓRICO
            if red_team_alerts:
                tabela_historico += "\n=== HISTÓRICO DESAFIANTE ===\n" + "\n".join(red_team_alerts)

            exemplos_str = exemplos_csv if exemplos_csv else "Nenhum."
            
            meta_prompt_final = meta_prompt.replace("{{json_rule}}", rules_current) \
                .replace("{{exemplo_texto_original}}", clausula_teste) \
                .replace("{{tabela_historico}}", tabela_historico) \
                .replace("{{exemplo_comentario}}", exemplos_str) \
                .replace("{{tentativa_atual}}", str(attempt)) \
                .replace("{{max_tentativas}}", str(max_attempts))

            print(f"      ➤ INPUT PROMPT COMPLETO:\n{meta_prompt_final.strip()}\n")

            try:
                meta_resp = llm.invoke(meta_prompt_final)
                meta_raw = meta_resp.content if hasattr(meta_resp, 'content') else str(meta_resp)
                meta_clean = meta_raw.replace("```json", "").replace("```", "").strip()
                meta_rule = meta_clean
                
                # Output removido do log

            except Exception as e:
                print(f"      ❌ [ERRO ENGENHEIRO] {e}", flush=True)
                meta_rule = rules_current

    finally:
        sys.stdout = original_stdout
    
    logs_texto = log_capture_string.getvalue()
    log_capture_string.close()
    return tentativas, logs_texto