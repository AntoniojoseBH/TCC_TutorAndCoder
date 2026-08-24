"""
Endpoints dedicados para análise de código pelo tutor.
- POST /analysis/project  → analisa consistência entre todos os arquivos
- POST /analysis/file     → revisa um arquivo específico
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json, os

from backend.db.connection import get_db
from backend.db.models import Student
from backend.api.routes.auth import get_current_student
from backend.config import settings
from backend.tools.file_editor import get_project_summary, read_file, list_files, PROJECTS_ROOT
from pydantic import BaseModel

router = APIRouter()


def get_model():
    from agno.models.anthropic import Claude
    api_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    return Claude(id=settings.LLM_MODEL, api_key=api_key)


class FileAnalysisRequest(BaseModel):
    path: str


@router.post("/project")
async def analyze_project(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Analisa consistência entre todos os arquivos do projeto.
    Detecta: imports quebrados, funções chamadas que não existem,
    assinaturas incompatíveis, variáveis não definidas entre arquivos.
    """
    student_id = current_student.id

    async def generate():
        yield f"data: {json.dumps({'type': 'status', 'message': 'Lendo todos os arquivos do projeto...'})}\n\n"

        summary = get_project_summary(student_id)

        if "nenhum arquivo" in summary.lower() or "projeto vazio" in summary.lower():
            yield f"data: {json.dumps({'type': 'done', 'message': '⚠️ Projeto vazio — crie alguns arquivos primeiro.'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        yield f"data: {json.dumps({'type': 'status', 'message': 'Analisando dependências e inconsistências...'})}\n\n"

        prompt = f"""Você é um revisor de código experiente. Analise o projeto abaixo e identifique:

1. **Inconsistências entre arquivos**:
   - Funções importadas que não existem no módulo de origem
   - Funções chamadas com número errado de argumentos
   - Nomes de funções/classes/variáveis que foram renomeados em um arquivo mas não em outros
   - Imports de módulos que não existem no projeto

2. **Erros lógicos e semânticos em cada arquivo**:
   - Lógica incorreta (ex: condição sempre verdadeira/falsa, loop infinito)
   - Variáveis usadas antes de serem definidas
   - Retorno em função que deveria retornar mas não retorna em todos os caminhos
   - Divisão por zero potencial
   - Comparações incorretas (ex: == None em vez de is None)
   - Variáveis definidas mas nunca usadas
   - Funções definidas mas nunca chamadas

3. **Problemas de boas práticas**:
   - Funções muito longas (mais de 20 linhas)
   - Nomes de variáveis não descritivos (x, y, a, b)
   - Ausência de docstrings em funções públicas
   - Código duplicado entre arquivos

Para cada problema encontrado, informe:
- 📄 Arquivo afetado
- 🔴 Tipo do erro (inconsistência / erro lógico / semântico / boas práticas)
- 📍 Linha aproximada (se identificável)
- 💬 Descrição clara do problema
- 💡 Como corrigir

Se não houver problemas, diga claramente que o projeto está consistente.

=== PROJETO ===
{summary}
"""

        try:
            from agno.agent import Agent
            agent = Agent(
                name="ProjectAnalyzer",
                model=get_model(),
                instructions=[
                    "Você é um revisor de código especialista.",
                    "Analise projetos completos identificando inconsistências entre arquivos e erros lógicos.",
                    "Seja específico: indique arquivo, linha aproximada e como corrigir cada problema.",
                    "Use markdown com emojis para organizar o relatório.",
                    "Responda em português.",
                ],
            )

            response = await agent.arun(prompt, stream=False)
            result = response.content if response and response.content else "Não foi possível analisar o projeto."

            yield f"data: {json.dumps({'type': 'done', 'message': result})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Erro ao analisar: {str(e)}'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/file")
async def analyze_file(
    request: FileAnalysisRequest,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Revisa um arquivo específico buscando erros lógicos, semânticos e boas práticas.
    """
    student_id = current_student.id

    async def generate():
        yield f"data: {json.dumps({'type': 'status', 'message': f'Lendo {request.path}...'})}\n\n"

        file_result = read_file(student_id, request.path)
        if not file_result.success:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Arquivo não encontrado: {request.path}'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Lê também outros arquivos para contexto de dependências
        all_files = list_files(student_id)
        context_files = ""
        if all_files.content and all_files.content != "(projeto vazio)":
            context_files = f"\n\nArquivos no projeto (para contexto de imports): {all_files.content}"

        yield f"data: {json.dumps({'type': 'status', 'message': 'Analisando erros e inconsistências...'})}\n\n"

        prompt = f"""Você é um revisor de código especialista. Analise o arquivo abaixo em detalhes.

Arquivo: {request.path}
{context_files}

=== CONTEÚDO DO ARQUIVO ===
{file_result.content}

Identifique e reporte:

**1. Erros de sintaxe ou estrutura**
- Indentação incorreta
- Parênteses/colchetes não fechados
- Uso incorreto de palavras-chave

**2. Erros lógicos**
- Condições sempre verdadeiras ou sempre falsas
- Loops que nunca terminam ou nunca executam
- Lógica invertida (ex: sinal errado numa comparação)
- Algoritmo que não resolve o problema proposto

**3. Erros semânticos**
- Variável usada antes de ser definida
- Tipo errado de dado (ex: somar string com número)
- Função retorna tipo inconsistente
- Retorno faltando em algum caminho da função
- Divisão por zero potencial
- Índice fora do intervalo potencial

**4. Inconsistências com outros arquivos do projeto**
- Funções importadas que podem não existir
- Nomes que diferem de outros arquivos do mesmo projeto

**5. Boas práticas**
- Nomes não descritivos
- Funções muito longas
- Código duplicado
- Ausência de docstrings
- Variáveis definidas mas não usadas

Para cada problema:
- Indique a linha exata
- Explique o problema de forma educativa
- Mostre como corrigir com exemplo de código

Se o arquivo estiver correto, elogie os pontos positivos e sugira melhorias opcionais.
Responda em português.
"""

        try:
            from agno.agent import Agent
            agent = Agent(
                name="FileReviewer",
                model=get_model(),
                instructions=[
                    "Você é um revisor de código especialista e professor.",
                    "Analise código identificando todos os tipos de erros.",
                    "Seja educativo: explique o porquê de cada erro.",
                    "Mostre exemplos de código corrigido.",
                    "Use markdown com emojis para organizar o relatório.",
                    "Responda em português.",
                ],
            )

            response = await agent.arun(prompt, stream=False)
            result = response.content if response and response.content else "Não foi possível revisar o arquivo."

            yield f"data: {json.dumps({'type': 'done', 'message': result, 'file': request.path})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Erro ao revisar: {str(e)}'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
