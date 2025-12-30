## Backend Python (FastAPI) — Guia Rápido

> Backend em `apps/prototype/backend`. Foco: execução local, rotas principais e fluxos Playground, Conversor CSV e Reverse Prompting.

### Requisitos
- Windows + PowerShell
- Python 3.10+

### Setup
```powershell
cd .\apps\prototype\backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# .env: copie e ajuste conforme exemplo abaixo
```

### Como rodar o Playground
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Playground: http://127.0.0.1:8000/playground/
- Docs: http://127.0.0.1:8000/docs

---

## Soluções Disponíveis

### 1. Playground (principal)
- Upload de `.docx`, análise de regras, download de validados.
- Rota: `/playground/`
- Link: http://127.0.0.1:8000/playground/
- Como usar: acesse a URL, envie o documento, ajuste regras se necessário, clique em “Analisar Documento”. Resultado: JSON e `.docx` validado para download.
  </details>
  <details><summary>Demonstração</summary>
  <img width="1435" height="758" alt="image" src="https://github.com/user-attachments/assets/322f3831-a8fa-4e36-8626-58579d71224c" />
  </details>

### 2. Conversor CSV
- Extrai comentários/alterações de `.docx` para CSV (ground truth).
- Rotas:
  - `GET /playground/converter-csv` — interface web.
  - `POST /playground/processar_csv_preview` — preview JSON.
  - `POST /playground/exportar_csv` — exporta CSV.
- Link: http://127.0.0.1:8000/playground/converter-csv
- Como usar: acesse a URL, faça upload do `.docx`, visualize/baixe CSV.
  </details>
  <details><summary>Demonstração</summary>
  <img width="413" height="269" alt="image" src="https://github.com/user-attachments/assets/e45aafd1-5c62-473a-aa2d-247410e392fe" />
  </details>

### 3. Reverse Prompting
- Refina regras de compliance via LLM, simula ataques (Red Team), gera histórico de tentativas.
- Rotas:
  - `GET /playground/reverse-prompting` — interface web.
  - `POST /playground/reverse-prompting/process` — executa pipeline.
- Link: http://127.0.0.1:8000/playground/reverse-prompting
- Como usar: acesse a URL, preencha prompts, regras e exemplos, execute e analise logs/resultados.
  </details>
  <details><summary>Demonstração</summary>
  <img width="1908" height="902" alt="image" src="https://github.com/user-attachments/assets/1c7c4383-a9d1-43d2-8beb-5ac4a9fd1890" />
  <img width="1872" height="691" alt="image" src="https://github.com/user-attachments/assets/b299adf7-db68-47db-8c4b-d84521578605" />
  </details>

---

## Docker (opcional)
```powershell
cd .\apps\prototype
docker compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

---

## Estrutura
- `app/api/playground.py` — rotas playground, conversor, reverse prompting.
- `app/analysis/reverse_prompting.py` — lógica reverse prompting.
- `app/analysis/extract_changes_csv.py` — extração CSV.
- `templates/` — HTML das interfaces.

---

## Observações
- Playground só funciona com `ENVIRONMENT=development` no `.env`.
- Dados locais: `app/data/{uploads,processed,rules}`.
- Troubleshooting: veja dicas no final do arquivo.


