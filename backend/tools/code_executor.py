import httpx
import base64
import asyncio
from dataclasses import dataclass
from backend.config import settings

# Judge0 language IDs
LANGUAGE_IDS = {
    "python": 71,
    "javascript": 63,
    "java": 62,
    "cpp": 54,
    "c": 50,
}


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    compile_output: str
    status: str
    time_ms: float
    memory_kb: int
    success: bool


async def execute_code(
    code: str,
    language: str = "python",
    stdin: str = "",
    timeout_seconds: int = 10,
) -> ExecutionResult:
    """
    Executa código em sandbox seguro via Judge0.
    Retorna stdout, stderr, status e métricas de execução.
    """
    language_id = LANGUAGE_IDS.get(language.lower(), 71)

    # Codifica em base64 (requisito da API Judge0)
    encoded_code = base64.b64encode(code.encode()).decode()
    encoded_stdin = base64.b64encode(stdin.encode()).decode() if stdin else ""

    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": settings.JUDGE0_API_KEY,
        "X-RapidAPI-Host": "judge0-ce.p.rapidapi.com",
    }

    payload = {
        "language_id": language_id,
        "source_code": encoded_code,
        "stdin": encoded_stdin,
        "cpu_time_limit": timeout_seconds,
        "memory_limit": 128000,  # 128 MB
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Submete o código
        submit_resp = await client.post(
            f"{settings.JUDGE0_API_URL}/submissions?base64_encoded=true&wait=false",
            json=payload,
            headers=headers,
        )
        submit_resp.raise_for_status()
        token = submit_resp.json()["token"]

        # Aguarda resultado com polling
        for _ in range(20):
            await asyncio.sleep(0.5)
            result_resp = await client.get(
                f"{settings.JUDGE0_API_URL}/submissions/{token}?base64_encoded=true",
                headers=headers,
            )
            result = result_resp.json()

            # Status 1 = em fila, 2 = processando
            if result.get("status", {}).get("id", 0) > 2:
                break

    def decode_b64(val: str | None) -> str:
        if not val:
            return ""
        try:
            return base64.b64decode(val).decode("utf-8", errors="replace")
        except Exception:
            return val

    status_id = result.get("status", {}).get("id", 0)
    status_desc = result.get("status", {}).get("description", "Unknown")

    return ExecutionResult(
        stdout=decode_b64(result.get("stdout")),
        stderr=decode_b64(result.get("stderr")),
        compile_output=decode_b64(result.get("compile_output")),
        status=status_desc,
        time_ms=float(result.get("time") or 0) * 1000,
        memory_kb=int(result.get("memory") or 0),
        success=(status_id == 3),  # 3 = Accepted
    )


def format_execution_result(result: ExecutionResult) -> str:
    """Formata o resultado de execução para ser usado pelo agente."""
    lines = [f"Status: {result.status}"]

    if result.stdout:
        lines.append(f"Saída:\n{result.stdout.strip()}")

    if result.stderr:
        lines.append(f"Erro:\n{result.stderr.strip()}")

    if result.compile_output:
        lines.append(f"Compilação:\n{result.compile_output.strip()}")

    lines.append(f"Tempo: {result.time_ms:.0f}ms | Memória: {result.memory_kb}KB")

    return "\n".join(lines)
