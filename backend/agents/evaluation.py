"""
Agente de Avaliação e Feedback

Responsabilidades:
- Executar o código do estudante em sandbox seguro
- Analisar corretude, eficiência e boas práticas
- Fornecer feedback construtivo e educativo
- Identificar o conceito subjacente ao erro
- Guiar com dicas progressivas sem dar a resposta direta
"""

from agno.agent import Agent
from agno.models.anthropic import Claude
from backend.agents._model import get_model
from agno.tools import tool
from sqlalchemy import select
import json
import logging

from backend.config import settings
from backend.db.models import ExerciseAttempt, StudentModel
from backend.db.connection import AsyncSessionLocal
from backend.tools.code_executor import execute_code as _execute_code, format_execution_result

logger = logging.getLogger(__name__)


@tool
async def run_student_code(code: str, language: str = "python", stdin: str = "") -> str:
    """
    Executa o código do estudante em sandbox seguro (Judge0).
    Retorna stdout, stderr, status e métricas de execução.
    """
    result = await _execute_code(code, language, stdin)
    return format_execution_result(result)


@tool
async def run_code_with_test_cases(code: str, test_cases: list) -> str:
    """
    Executa o código do estudante contra múltiplos casos de teste.
    test_cases: lista de {"input": str, "expected_output": str}
    """
    if not test_cases:
        return await run_student_code(code)

    results = []
    passed = 0
    for i, tc in enumerate(test_cases):
        result = await _execute_code(code, "python", tc.get("input", ""))
        actual = (result.stdout or "").strip()
        expected = str(tc.get("expected_output", "")).strip()
        ok = actual == expected
        if ok:
            passed += 1
        results.append({
            "test": i + 1,
            "input": tc.get("input", ""),
            "expected": expected,
            "got": actual,
            "passed": ok,
        })

    summary = f"{passed}/{len(test_cases)} testes passaram.\n"
    summary += "\n".join(
        f"  ✓ Teste {r['test']}" if r["passed"] else
        f"  ✗ Teste {r['test']}: esperado '{r['expected']}', recebido '{r['got']}'"
        for r in results
    )
    return summary


@tool
async def analyze_code_quality(code: str) -> str:
    """
    Analisa a qualidade do código sem executá-lo.
    Verifica: nomeação, complexidade, comentários, boas práticas PEP8.
    """
    issues = []
    suggestions = []

    lines = code.split("\n")
    if len(lines) > 50:
        suggestions.append("Considere dividir em funções menores (mais de 50 linhas)")

    if "def " not in code and len(lines) > 15:
        suggestions.append("Organize o código em funções para melhor legibilidade")

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("x = ") or stripped.startswith("y = ") or stripped.startswith("a = "):
            issues.append("Use nomes descritivos para variáveis (evite 'x', 'y', 'a')")
            break

    has_docstring = '"""' in code or "'''" in code
    has_comments = "#" in code
    if "def " in code and not has_docstring:
        suggestions.append("Adicione docstrings às suas funções (ex: '''Descrição da função''')")

    if not has_comments and len(lines) > 10:
        suggestions.append("Comentários ajudam a explicar a lógica — adicione alguns")

    if "except:" in code:
        issues.append("Evite 'except:' genérico — especifique o tipo de exceção (ex: except ValueError:)")

    result = []
    if issues:
        result.append("Problemas encontrados:\n" + "\n".join(f"  ⚠️  {i}" for i in issues))
    if suggestions:
        result.append("Sugestões de melhoria:\n" + "\n".join(f"  💡 {s}" for s in suggestions))
    if not issues and not suggestions:
        result.append("✅ Código bem estruturado!")

    return "\n".join(result)


@tool
async def save_exercise_attempt(
    student_id: str,
    exercise_id: str,
    submitted_code: str,
    is_correct: bool,
    score: float,
    feedback: str,
    execution_output: str,
) -> str:
    """Salva a tentativa de exercício no banco e atualiza estatísticas do estudante."""
    async with AsyncSessionLocal() as db:
        # Verifica se já houve tentativas anteriores para este exercício
        result = await db.execute(
            select(ExerciseAttempt)
            .where(ExerciseAttempt.student_id == student_id)
            .where(ExerciseAttempt.exercise_id == exercise_id)
        )
        existing = result.scalars().all()
        attempt_count = len(existing) + 1

        attempt = ExerciseAttempt(
            student_id=student_id,
            exercise_id=exercise_id,
            submitted_code=submitted_code,
            is_correct=is_correct,
            score=score,
            feedback=feedback,
            execution_output=execution_output,
            attempts_count=attempt_count,
        )
        db.add(attempt)

        # Atualiza contadores no StudentModel
        model_result = await db.execute(
            select(StudentModel).where(StudentModel.student_id == student_id)
        )
        model = model_result.scalar_one_or_none()
        if model:
            model.total_exercises_done += 1
            if is_correct:
                model.total_correct_exercises += 1

        await db.commit()
    return f"Tentativa {attempt_count} salva. Correto: {is_correct}. Score: {score:.2f}"


def create_evaluation_agent() -> Agent:
    return Agent(
        name="EvaluationAgent",
        role="Agente de Avaliação e Feedback",
        model=get_model(settings.LLM_MODEL),
        tools=[
            run_student_code,
            run_code_with_test_cases,
            analyze_code_quality,
            save_exercise_attempt,
        ],
        instructions=[
            "Você avalia código Python de estudantes e fornece feedback educativo.",
            "Fluxo de avaliação:",
            "  1. Execute o código com run_student_code para ver o output real.",
            "  2. Se houver test_cases, use run_code_with_test_cases.",
            "  3. Analise a qualidade com analyze_code_quality.",
            "  4. Salve a tentativa com save_exercise_attempt.",
            "Estrutura do feedback:",
            "  ✅ O que está correto (sempre comece pelo positivo)",
            "  🔍 O que precisa melhorar (específico, não genérico)",
            "  💡 Dica de melhoria (mostre alternativa, não a solução completa)",
            "  📚 Conceito relacionado a reforçar",
            "NUNCA dê a solução completa de primeira — ofereça dicas progressivas.",
            "Se o código tiver erro de sintaxe, explique a linha específica.",
            "Compare a complexidade: se há solução mais elegante, mostre-a APÓS o aluno tentar.",
        ],
    )
