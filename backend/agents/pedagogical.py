"""
Agente Pedagógico

Responsabilidades:
- Decidir o que ensinar e como ensinar
- Adaptar a abordagem didática ao perfil do estudante
- Cobrir toda a grade de Engenharia de Computação
- Criar exercícios e explicações personalizados
"""

from agno.agent import Agent
from agno.tools import tool
import json
import logging

from backend.config import settings
from backend.db.connection import AsyncSessionLocal
from backend.db.models import Exercise
from backend.agents._model import get_model
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

# ── Currículo expandido — Engenharia de Computação ───────────────────────────

# Mapa de pré-requisitos por área
PREREQUISITES = {
    # Programação
    "loops":              ["variables", "conditionals"],
    "functions":          ["variables", "conditionals", "loops"],
    "recursion":          ["functions"],
    "lists":              ["variables", "loops"],
    "dicts":              ["variables", "loops"],
    "oop_classes":        ["functions", "variables"],
    "oop_inheritance":    ["oop_classes"],
    "exceptions":         ["functions", "conditionals"],
    "algorithms":         ["loops", "functions", "lists"],
    "data_structures":    ["lists", "dicts", "oop_classes"],
    "complexity":         ["algorithms"],
    # Redes
    "network_basics":     [],
    "osi_model":          ["network_basics"],
    "tcp_ip":             ["osi_model"],
    "http_dns":           ["tcp_ip"],
    "network_security":   ["tcp_ip"],
    # Sistemas Operacionais
    "so_processes":       [],
    "so_memory":          ["so_processes"],
    "so_scheduling":      ["so_processes"],
    "so_filesystems":     ["so_memory"],
    # IHC
    "ihc_usability":      [],
    "ihc_design":         ["ihc_usability"],
    "ihc_evaluation":     ["ihc_design"],
    # Engenharia de Software
    "software_requirements": [],
    "design_patterns":    ["oop_classes"],
    "software_testing":   ["functions"],
    "software_arch":      ["design_patterns"],
    # Banco de Dados
    "db_relational":      [],
    "db_sql":             ["db_relational"],
    "db_normalization":   ["db_sql"],
    "db_nosql":           ["db_relational"],
    # Lógica e Matemática
    "logic_propositional": [],
    "logic_predicates":   ["logic_propositional"],
    "discrete_math":      ["logic_propositional"],
    "linear_algebra":     [],
    # Arquitetura de Computadores
    "arch_binary":        [],
    "arch_cpu":           ["arch_binary"],
    "arch_memory":        ["arch_cpu"],
}

# Agrupamento por área para sugestões contextuais
AREAS = {
    "Programação":             ["variables", "data_types", "operators", "conditionals", "loops",
                                "functions", "recursion", "lists", "dicts", "sets",
                                "oop_classes", "oop_inheritance", "oop_polymorphism",
                                "exceptions", "file_io", "modules", "algorithms",
                                "data_structures", "complexity"],
    "Redes de Computadores":   ["network_basics", "osi_model", "tcp_ip", "http_dns", "network_security"],
    "Sistemas Operacionais":   ["so_processes", "so_memory", "so_scheduling", "so_filesystems"],
    "IHC":                     ["ihc_usability", "ihc_design", "ihc_evaluation"],
    "Engenharia de Software":  ["software_requirements", "design_patterns", "software_testing", "software_arch"],
    "Banco de Dados":          ["db_relational", "db_sql", "db_normalization", "db_nosql"],
    "Lógica e Matemática":     ["logic_propositional", "logic_predicates", "discrete_math", "linear_algebra"],
    "Arquitetura":             ["arch_binary", "arch_cpu", "arch_memory"],
}

# Linguagens de programação suportadas
SUPPORTED_LANGUAGES = ["Python", "C", "C++", "Java", "JavaScript", "TypeScript",
                        "SQL", "HTML/CSS", "Assembly", "Go", "Rust"]


@tool
async def suggest_next_concept(student_profile_json: str) -> str:
    """
    Sugere o próximo conceito a estudar com base no perfil do estudante.
    Considera pré-requisitos e progressão natural do currículo.
    """
    profile = json.loads(student_profile_json)
    mastery = profile.get("concept_mastery", {})

    ready_to_learn = []
    for concept, prereqs in PREREQUISITES.items():
        if concept in mastery and mastery[concept] >= 0.6:
            continue  # já domina
        prereqs_met = all(mastery.get(p, 0) >= 0.5 for p in prereqs)
        if prereqs_met:
            ready_to_learn.append((concept, mastery.get(concept, 0.0)))

    ready_to_learn.sort(key=lambda x: (x[1] > 0, x[1]))

    if not ready_to_learn:
        return json.dumps({"concept": "variables", "reason": "Conceito inicial do currículo"})

    concept, score = ready_to_learn[0]
    # Identifica a área do conceito
    area = next((a for a, concepts in AREAS.items() if concept in concepts), "Geral")
    reason = "em progresso, precisa de reforço" if score > 0 else "pré-requisitos cumpridos"
    return json.dumps({"concept": concept, "area": area, "reason": reason, "current_score": score})


@tool
async def generate_explanation(concept: str, level: str, learning_style: str) -> str:
    """
    Retorna template de explicação adaptado ao nível e estilo.
    Funciona para qualquer disciplina da grade de Engenharia de Computação.
    level: 'beginner' | 'intermediate' | 'advanced'
    learning_style: 'visual' | 'textual' | 'hands-on'
    """
    templates = {
        "visual": (
            f"Explique '{concept}' usando diagramas ASCII, tabelas comparativas "
            f"e exemplos visuais passo a passo. Se for um conceito de rede ou SO, "
            f"desenhe o fluxo de dados ou estados do sistema."
        ),
        "textual": (
            f"Explique '{concept}' com: (1) definição formal, "
            f"(2) analogia do mundo real, (3) exemplo prático com código ou esquema."
        ),
        "hands-on": (
            f"Para '{concept}', comece com um exemplo funcional concreto "
            f"(código, configuração ou caso real), depois explique o porquê."
        ),
    }
    level_guidance = {
        "beginner":     "Linguagem simples, sem jargão, analogias cotidianas.",
        "intermediate": "Pode usar terminologia técnica, foque em casos de uso e comparações.",
        "advanced":     "Aprofunde em detalhes de implementação, trade-offs e boas práticas.",
    }
    style = learning_style if learning_style in templates else "visual"
    lvl = level if level in level_guidance else "beginner"
    return f"{templates[style]} {level_guidance[lvl]}"


@tool
async def get_exercise_for_concept(concept: str, difficulty: float) -> str:
    """Busca exercício do banco para o conceito e dificuldade informados."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Exercise)
            .where(Exercise.concept == concept)
            .where(Exercise.difficulty.between(max(0, difficulty - 0.2), min(1, difficulty + 0.2)))
            .order_by(func.random())
            .limit(1)
        )
        exercise = result.scalar_one_or_none()

    if not exercise:
        return json.dumps({
            "id": None,
            "title": f"Exercício de {concept}",
            "description": (
                f"Elabore uma solução prática que demonstre o conceito de '{concept}'. "
                f"Pode ser um código, um diagrama explicado em texto, "
                f"ou uma análise de um caso real."
            ),
            "hints": [
                f"Revise a definição de {concept}",
                "Tente aplicar em um exemplo do mundo real",
            ],
            "difficulty": difficulty,
        })

    return json.dumps({
        "id": exercise.id,
        "title": exercise.title,
        "description": exercise.description,
        "hints": exercise.hints,
        "difficulty": exercise.difficulty,
        "test_cases": exercise.test_cases,
    })


@tool
async def classify_student_intent(message: str) -> str:
    """
    Classifica a intenção da mensagem do estudante.
    Retorna: question | code_submission | exercise_request | explanation_request |
             language_question | other
    """
    msg = message.lower()

    has_code = any(kw in message for kw in [
        "def ", "for ", "while ", "class ", "import ", "```",
        "int ", "void ", "#include", "SELECT ", "function ", "=>",
    ])
    is_exercise = any(kw in msg for kw in [
        "exercício", "exercicio", "prática", "pratica",
        "treinar", "desafio", "atividade", "problema",
    ])
    is_explanation = any(kw in msg for kw in [
        "o que é", "o que e", "como funciona", "explica", "explique",
        "explain", "what is", "me fale sobre", "me conta",
        "diferença entre", "diferenca entre", "quando usar",
    ])
    is_language = any(lang.lower() in msg for lang in SUPPORTED_LANGUAGES)

    if has_code:
        return "code_submission"
    elif is_exercise:
        return "exercise_request"
    elif is_explanation:
        return "explanation_request"
    elif is_language and "?" in message:
        return "language_question"
    elif "?" in message:
        return "question"
    return "other"


@tool
async def get_area_for_topic(topic: str) -> str:
    """
    Identifica a área de conhecimento de um tópico mencionado pelo estudante.
    Retorna a área e sugestões de conceitos relacionados.
    """
    topic_lower = topic.lower()

    area_keywords = {
        "Redes de Computadores": [
            "rede", "tcp", "ip", "http", "dns", "protocolo", "pacote",
            "roteador", "switch", "firewall", "vpn", "socket", "porta",
        ],
        "Sistemas Operacionais": [
            "processo", "thread", "semáforo", "deadlock", "escalonamento",
            "memoria", "memória", "paginação", "paginacao", "sistema operacional",
            "kernel", "sistema de arquivos", "filesystem",
        ],
        "IHC": [
            "interface", "usabilidade", "ux", "ui", "design", "usuário",
            "usuario", "interação", "interacao", "acessibilidade", "prototipo",
            "wireframe", "heurística", "heuristica",
        ],
        "Banco de Dados": [
            "banco de dados", "sql", "nosql", "tabela", "query", "join",
            "índice", "indice", "normalização", "normalizacao", "mongodb",
            "postgresql", "mysql",
        ],
        "Engenharia de Software": [
            "padrão de projeto", "design pattern", "arquitetura", "teste",
            "scrum", "agile", "requisito", "uml", "diagrama", "mvc",
            "microservico", "microsserviço",
        ],
        "Arquitetura de Computadores": [
            "binário", "binario", "hexadecimal", "cpu", "processador",
            "registrador", "cache", "alu", "ciclo de instrução",
        ],
        "Lógica e Matemática": [
            "lógica", "logica", "proposição", "proposicao", "predicado",
            "grafo", "arvore", "árvore", "matriz", "vetor", "algebra",
            "probabilidade", "estatística", "estatistica",
        ],
    }

    for area, keywords in area_keywords.items():
        if any(kw in topic_lower for kw in keywords):
            related = AREAS.get(area, [])[:4]
            return json.dumps({"area": area, "related_concepts": related})

    return json.dumps({"area": "Programação", "related_concepts": AREAS["Programação"][:4]})


def create_pedagogical_agent() -> Agent:
    return Agent(
        name="PedagogicalAgent",
        role="Agente Pedagógico",
        model=get_model(settings.LLM_MODEL),
        tools=[
            suggest_next_concept,
            generate_explanation,
            get_exercise_for_concept,
            classify_student_intent,
            get_area_for_topic,
        ],
        instructions=[
            "Você é um tutor especialista em Engenharia de Computação.",
            "",
            "ESCOPO — você domina e ensina todas estas áreas:",
            "  - Programação: Python, C, C++, Java, JavaScript, SQL e mais",
            "  - Lógica de programação e algoritmos",
            "  - Redes de Computadores: OSI, TCP/IP, HTTP, DNS, segurança",
            "  - Sistemas Operacionais: processos, memória, escalonamento",
            "  - IHC: usabilidade, design de interfaces, avaliação",
            "  - Banco de Dados: SQL, NoSQL, modelagem, normalização",
            "  - Engenharia de Software: padrões, arquitetura, testes",
            "  - Arquitetura de Computadores: CPU, memória, binário",
            "  - Lógica e Matemática Discreta",
            "",
            "FLUXO para cada mensagem:",
            "  1. classify_student_intent — identifique a intenção",
            "  2. get_area_for_topic — identifique a área de conhecimento",
            "  3. Para explanation_request: use generate_explanation",
            "  4. Para exercise_request: use get_exercise_for_concept",
            "  5. Para code_submission: solicite ao EvaluationAgent",
            "  6. Para question/language_question: responda diretamente",
            "",
            "ESTRUTURA de resposta — adapte ao contexto:",
            "  Para explicações e dúvidas:",
            "    1. Reconheça a dúvida (1 linha)",
            "    2. Explique o conceito (2-4 parágrafos com exemplos)",
            "    3. Código, diagrama ou esquema quando aplicável",
            "    4. Mini-desafio ou pergunta de reflexão ao final",
            "",
            "  Para confirmações de entendimento (ex: 'entendi', 'obrigado', 'certo'):",
            "    1. Confirme brevemente que o estudante compreendeu",
            "    2. Pergunte se tem mais dúvidas sobre o tema ou quer explorar outro aspecto",
            "    3. NÃO proponha um novo desafio automaticamente — espere o estudante pedir",
            "    4. Exemplos de encerramento natural:",
            "       'Ótimo! Ficou com alguma dúvida sobre isso? Posso aprofundar algum ponto'",
            "       'Perfeito! Quer ver mais exemplos ou explorar outro conceito?'",
            "",
            "REGRAS:",
            "  - Use analogias antes de termos técnicos para iniciantes",
            "  - Para redes/SO: use diagramas ASCII para ilustrar fluxos",
            "  - Para IHC: relacione com exemplos de apps conhecidos",
            "  - NUNCA entregue a resposta de um exercício diretamente",
            "  - NUNCA proponha novo desafio logo após o estudante dizer que entendeu",
            "  - Desafios só devem ser propostos quando o estudante pedir ou durante explicações",
            "  - Tom: encorajador, paciente, nunca condescendente",
            "  - Responda em português, mas mantenha termos técnicos em inglês",
        ],
    )
