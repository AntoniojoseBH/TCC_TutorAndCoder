"""
Agente de Modelagem do Aluno

Responsabilidades:
- Criar e manter o modelo cognitivo de cada estudante
- Rastrear domínio em toda a grade de Engenharia de Computação
- Identificar lacunas e padrões de aprendizado
- Atualizar o perfil com base em cada interação
"""

from agno.agent import Agent
from agno.tools import tool
from sqlalchemy import select
import json
import logging

from backend.config import settings
from backend.db.models import StudentModel
from backend.db.connection import AsyncSessionLocal, redis_client
from backend.agents._model import get_model

logger = logging.getLogger(__name__)

# ── Todos os conceitos rastreáveis — grade de Engenharia de Computação ────────
CONCEPTS = [
    # Fundamentos de programação
    "variables", "data_types", "operators", "conditionals", "loops",
    "functions", "recursion", "lists", "dicts", "sets",
    "oop_classes", "oop_inheritance", "oop_polymorphism",
    "exceptions", "file_io", "modules",
    # Algoritmos e estruturas
    "algorithms", "data_structures", "complexity",
    "sorting", "searching", "graphs", "trees",
    # Redes de Computadores
    "network_basics", "osi_model", "tcp_ip", "http_dns",
    "network_security", "network_routing",
    # Sistemas Operacionais
    "so_processes", "so_memory", "so_scheduling",
    "so_filesystems", "so_concurrency",
    # IHC
    "ihc_usability", "ihc_design", "ihc_evaluation",
    # Banco de Dados
    "db_relational", "db_sql", "db_normalization", "db_nosql",
    # Engenharia de Software
    "software_requirements", "design_patterns",
    "software_testing", "software_arch",
    # Arquitetura de Computadores
    "arch_binary", "arch_cpu", "arch_memory",
    # Lógica e Matemática
    "logic_propositional", "logic_predicates",
    "discrete_math", "linear_algebra",
]

# Mapeamento de palavras-chave para conceitos (para inferência automática)
CONCEPT_KEYWORDS = {
    # Programação
    "variables":       ["variável", "variable", "atribuição", "var "],
    "loops":           ["loop", "for ", "while ", "laço", "repetição", "iteração"],
    "functions":       ["função", "function", "def ", "return", "parâmetro"],
    "recursion":       ["recursão", "recursiv", "caso base"],
    "conditionals":    ["if ", "else", "elif", "condição", "condicion"],
    "lists":           ["lista", "list", "append", "índice"],
    "dicts":           ["dicion", "dict", "chave", "key", "value"],
    "oop_classes":     ["class ", "objeto", "instância", "self", "__init__"],
    "exceptions":      ["try", "except", "erro", "exception", "raise"],
    "algorithms":      ["algoritmo", "ordenação", "sort", "busca"],
    "data_structures": ["estrutura de dados", "pilha", "fila", "stack", "queue"],
    "complexity":      ["complexidade", "big o", "O(n)", "eficiência"],
    # Redes
    "network_basics":  ["rede", "network", "protocolo", "pacote", "nó"],
    "osi_model":       ["osi", "camada", "layer", "modelo osi"],
    "tcp_ip":          ["tcp", "ip", "udp", "socket", "porta", "handshake"],
    "http_dns":        ["http", "https", "dns", "url", "request", "response"],
    "network_security":["firewall", "vpn", "criptografia", "ssl", "tls"],
    # SO
    "so_processes":    ["processo", "thread", "pid", "fork"],
    "so_memory":       ["memória", "ram", "paginação", "segmentação", "heap"],
    "so_scheduling":   ["escalonamento", "scheduler", "cpu burst", "round robin"],
    "so_filesystems":  ["sistema de arquivos", "filesystem", "inodo", "diretório"],
    "so_concurrency":  ["deadlock", "semáforo", "mutex", "concorrência", "race condition"],
    # IHC
    "ihc_usability":   ["usabilidade", "usability", "heurística", "nielsen"],
    "ihc_design":      ["wireframe", "prototipo", "ui", "ux", "interface"],
    "ihc_evaluation":  ["avaliação", "teste de usabilidade", "eye tracking"],
    # BD
    "db_relational":   ["banco de dados", "tabela", "relacional", "chave primária"],
    "db_sql":          ["sql", "select", "insert", "update", "delete", "join"],
    "db_normalization":["normalização", "forma normal", "1fn", "2fn", "3fn"],
    "db_nosql":        ["nosql", "mongodb", "redis", "documento", "chave-valor"],
    # ES
    "design_patterns": ["design pattern", "padrão", "singleton", "factory", "mvc"],
    "software_testing":["teste", "test", "tdd", "unittest", "cobertura", "mock"],
    "software_arch":   ["arquitetura", "microsserviço", "monolito", "clean arch"],
    # Arq. Computadores
    "arch_binary":     ["binário", "hexadecimal", "bit", "byte", "base 2"],
    "arch_cpu":        ["cpu", "processador", "alu", "registrador", "clock"],
    # Lógica
    "logic_propositional": ["proposição", "lógica", "and", "or", "not", "tabela verdade"],
    "discrete_math":   ["grafo", "árvore", "combinatória", "indução", "conjuntos"],
}


@tool
async def get_student_profile(student_id: str) -> str:
    """Retorna o perfil cognitivo completo do estudante."""
    cache_key = f"profile:{student_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return cached

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StudentModel).where(StudentModel.student_id == student_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return json.dumps({
                "concept_mastery": {},
                "difficulty_level": 0.3,
                "learning_style": "visual",
                "total_interactions": 0,
            })
        profile = {
            "concept_mastery":    model.concept_mastery,
            "difficulty_level":   model.difficulty_level,
            "learning_style":     model.learning_style,
            "total_interactions": model.total_interactions,
            "total_exercises_done": model.total_exercises_done,
            "preferred_language": model.preferred_language,
        }
        await redis_client.setex(cache_key, 600, json.dumps(profile))
        return json.dumps(profile)


@tool
async def update_concept_mastery(
    student_id: str,
    concept: str,
    score_delta: float,
    reason: str = "",
) -> str:
    """
    Atualiza o nível de domínio de um conceito.
    score_delta: entre -0.2 e +0.2.
    Funciona para qualquer conceito da grade (programação, redes, SO, IHC, etc).
    """
    if concept not in CONCEPTS:
        # Aceita conceitos livres não mapeados — importante para tópicos novos
        logger.info(f"Conceito livre registrado: {concept}")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(StudentModel).where(StudentModel.student_id == student_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return "Perfil do estudante não encontrado."

        current = model.concept_mastery.get(concept, 0.3)
        new_score = max(0.0, min(1.0, current + score_delta))
        model.concept_mastery = {**model.concept_mastery, concept: round(new_score, 3)}
        model.total_interactions += 1

        if model.concept_mastery:
            numeric_values = [
                v for k, v in model.concept_mastery.items()
                if not k.startswith("_") and isinstance(v, (int, float))
            ]
            if numeric_values:
                avg = sum(numeric_values) / len(numeric_values)
                model.difficulty_level = round(avg, 3)

        await db.commit()

    await redis_client.delete(f"profile:{student_id}")
    return f"Conceito '{concept}': {current:.2f} → {new_score:.2f}. Razão: {reason}"


@tool
async def identify_weak_concepts(student_id: str, threshold: float = 0.5) -> str:
    """Identifica conceitos abaixo do threshold, agrupados por área."""
    profile_str = await get_student_profile(student_id)
    profile = json.loads(profile_str)
    mastery = profile.get("concept_mastery", {})

    weak   = {k: v for k, v in mastery.items() if v < threshold}
    strong = {k: v for k, v in mastery.items() if v >= 0.8}
    unvisited = [c for c in CONCEPTS if c not in mastery]

    return json.dumps({
        "weak_concepts":       weak,
        "strong_concepts":     strong,
        "unvisited_concepts":  unvisited[:5],
        "recommended_focus":   sorted(weak, key=weak.get)[:3] if weak else unvisited[:3],
    })


@tool
async def infer_concepts_from_message(message: str) -> str:
    """
    Infere conceitos presentes na mensagem do estudante.
    Cobre toda a grade de Engenharia de Computação.
    """
    msg_lower = message.lower()
    detected = []

    for concept, keywords in CONCEPT_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            detected.append(concept)

    return json.dumps(detected)


def create_student_model_agent() -> Agent:
    return Agent(
        name="StudentModelAgent",
        role="Agente de Modelagem do Aluno",
        model=get_model(settings.LLM_MODEL_FAST),
        tools=[
            get_student_profile,
            update_concept_mastery,
            identify_weak_concepts,
            infer_concepts_from_message,
        ],
        instructions=[
            "Você mantém o modelo cognitivo de cada estudante.",
            "Rastreie domínio em TODAS as áreas da grade de Engenharia de Computação:",
            "  Programação, Redes, SO, IHC, BD, Engenharia de Software, Arquitetura, Lógica.",
            "",
            "Para cada interação:",
            "  1. Use infer_concepts_from_message para detectar conceitos na mensagem.",
            "  2. Use update_concept_mastery para atualizar o domínio detectado.",
            "  3. score_delta positivo (+0.05 a +0.15) quando o aluno demonstra compreensão.",
            "  4. score_delta negativo (-0.05 a -0.10) quando demonstra confusão.",
            "",
            "Aceite conceitos fora da lista pré-definida — o estudante pode mencionar",
            "tópicos específicos de disciplinas não mapeadas ainda.",
            f"Conceitos mapeados: {len(CONCEPTS)} no total, cobrindo toda a grade.",
        ],
    )
