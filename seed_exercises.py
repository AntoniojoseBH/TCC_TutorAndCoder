"""
Script para popular o banco de exercícios.
Execute uma vez: python seed_exercises.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from backend.db.connection import AsyncSessionLocal, create_tables
from backend.db.models import Exercise

EXERCISES = [
    # ── Variáveis e tipos ────────────────────────────────────────────────
    {"title": "Calculadora de IMC", "concept": "variables", "difficulty": 0.2,
     "description": "Crie um programa que calcule o IMC (peso / altura²) e classifique como: Abaixo do peso (<18.5), Normal (18.5-24.9), Sobrepeso (25-29.9) ou Obeso (≥30).",
     "hints": ["Use variáveis para peso e altura", "Use if/elif/else para classificar"],
     "test_cases": [{"input": "70\n1.75", "expected_output": "Normal"}]},

    # ── Condicionais ─────────────────────────────────────────────────────
    {"title": "Verificador de ano bissexto", "concept": "conditionals", "difficulty": 0.2,
     "description": "Escreva uma função `is_bissexto(ano)` que retorna True se o ano for bissexto. Um ano é bissexto se divisível por 4, exceto séculos, que devem ser divisíveis por 400.",
     "hints": ["Ano divisível por 4 E não por 100 OU divisível por 400"],
     "test_cases": [{"input": "2024", "expected_output": "True"}, {"input": "1900", "expected_output": "False"}]},

    # ── Laços ────────────────────────────────────────────────────────────
    {"title": "Tabuada", "concept": "loops", "difficulty": 0.2,
     "description": "Crie uma função `tabuada(n)` que imprime a tabuada de n de 1 a 10.",
     "hints": ["Use for com range(1, 11)", "Formato: '3 x 1 = 3'"],
     "test_cases": []},

    {"title": "FizzBuzz", "concept": "loops", "difficulty": 0.3,
     "description": "Imprima números de 1 a 100. Para múltiplos de 3 imprima 'Fizz', de 5 imprima 'Buzz', de ambos imprima 'FizzBuzz'.",
     "hints": ["Verifique múltiplo de 15 primeiro", "Use o operador %"],
     "test_cases": []},

    # ── Funções ──────────────────────────────────────────────────────────
    {"title": "Fatorial recursivo", "concept": "functions", "difficulty": 0.4,
     "description": "Implemente `fatorial(n)` de forma recursiva. Deve funcionar para n=0 (retorna 1) e n>0.",
     "hints": ["Caso base: fatorial(0) = 1", "Caso recursivo: n * fatorial(n-1)"],
     "test_cases": [{"input": "5", "expected_output": "120"}, {"input": "0", "expected_output": "1"}]},

    {"title": "Verificador de palíndromo", "concept": "functions", "difficulty": 0.3,
     "description": "Crie `is_palindromo(texto)` que retorna True se o texto é igual ao reverso (ignore maiúsculas e espaços). Ex: 'Ame a ema' é palíndromo.",
     "hints": ["Use .lower() e .replace(' ', '')", "Compare com [::-1]"],
     "test_cases": [{"input": "arara", "expected_output": "True"}, {"input": "python", "expected_output": "False"}]},

    # ── Listas ───────────────────────────────────────────────────────────
    {"title": "Segundo maior elemento", "concept": "lists", "difficulty": 0.4,
     "description": "Dada uma lista de números, encontre o segundo maior elemento sem usar sorted().",
     "hints": ["Percorra a lista mantendo o maior e segundo maior", "Cuidado com duplicatas"],
     "test_cases": [{"input": "[3, 1, 4, 1, 5, 9, 2, 6]", "expected_output": "6"}]},

    # ── Dicionários ──────────────────────────────────────────────────────
    {"title": "Contador de palavras", "concept": "dicts", "difficulty": 0.3,
     "description": "Crie `contar_palavras(texto)` que retorna um dicionário com a frequência de cada palavra.",
     "hints": ["Use .split() para separar palavras", "Inicialize contador com 0 ou use .get()"],
     "test_cases": [{"input": "ola mundo ola", "expected_output": "{'ola': 2, 'mundo': 1}"}]},

    # ── POO ──────────────────────────────────────────────────────────────
    {"title": "Classe Conta Bancária", "concept": "oop_classes", "difficulty": 0.5,
     "description": "Implemente a classe ContaBancaria com: saldo inicial, métodos depositar(valor), sacar(valor) (não permite saldo negativo) e extrato() que mostra o saldo atual.",
     "hints": ["Use __init__ para o saldo", "sacar deve verificar se há saldo suficiente"],
     "test_cases": []},

    # ── Algoritmos ───────────────────────────────────────────────────────
    {"title": "Busca binária", "concept": "algorithms", "difficulty": 0.6,
     "description": "Implemente busca binária em uma lista ordenada. Retorne o índice do elemento ou -1 se não encontrado.",
     "hints": ["Mantenha índices low e high", "Calcule mid = (low + high) // 2"],
     "test_cases": [{"input": "[1,3,5,7,9]\n5", "expected_output": "2"}, {"input": "[1,3,5,7,9]\n4", "expected_output": "-1"}]},

    # ── Recursão ─────────────────────────────────────────────────────────
    {"title": "Torre de Hanói", "concept": "recursion", "difficulty": 0.7,
     "description": "Implemente a solução recursiva da Torre de Hanói para n discos. Imprima cada movimento no formato 'Mova disco X de A para C'.",
     "hints": ["Mova n-1 discos para o pino auxiliar", "Depois mova o maior, depois os n-1 de volta"],
     "test_cases": []},

    # ── SQL ──────────────────────────────────────────────────────────────
    {"title": "Consulta SQL com JOIN", "concept": "db_sql", "difficulty": 0.5,
     "description": "Escreva uma query SQL que retorne o nome dos clientes e o total gasto, considerando tabelas: clientes(id, nome) e pedidos(id, cliente_id, valor). Ordene do maior para o menor total.",
     "hints": ["Use JOIN entre clientes e pedidos", "Use SUM e GROUP BY", "ORDER BY total DESC"],
     "test_cases": []},

    # ── Redes ────────────────────────────────────────────────────────────
    {"title": "Calculadora de sub-rede", "concept": "tcp_ip", "difficulty": 0.6,
     "description": "Dado um endereço IP e máscara CIDR (ex: 192.168.1.0/24), calcule: endereço de rede, broadcast e número de hosts disponíveis.",
     "hints": ["Use a biblioteca ipaddress do Python", "import ipaddress; net = ipaddress.ip_network(...)"],
     "test_cases": []},
]

async def seed():
    await create_tables()
    async with AsyncSessionLocal() as db:
        for ex in EXERCISES:
            exercise = Exercise(
                title=ex["title"],
                description=ex["description"],
                concept=ex["concept"],
                difficulty=ex["difficulty"],
                hints=ex["hints"],
                test_cases=ex.get("test_cases", []),
            )
            db.add(exercise)
        await db.commit()
        print(f"✅ {len(EXERCISES)} exercícios inseridos com sucesso!")

if __name__ == "__main__":
    asyncio.run(seed())
