# TutorAndCoder

**Trabalho de Conclusão de Curso — CEFET-MG**

**Título:** Proposta de uma IA Agêntica para o Apoio ao Aprendizado de Programação de Alunos de Computação

**Aluno:** Antônio José Peixoto Chaves

**Orientadora:** Glívia Angélica Rodrigues Barbosa

---

## Sobre o projeto

O **TutorAndCoder** é um sistema de tutoria inteligente baseado em uma arquitetura de **IA agêntica multiagente**, desenvolvido com o objetivo de apoiar estudantes de Engenharia de Computação no aprendizado de programação. O sistema oferece explicações adaptadas ao nível do estudante, propõe desafios de código, analisa projetos enviados, identifica inconsistências entre arquivos e acompanha o progresso individual de cada usuário ao longo do tempo.

A arquitetura é composta por **seis agentes especializados**, orquestrados pelo framework [Agno](https://github.com/agno-agi/agno), cada um responsável por uma função específica: infraestrutura de dados, modelagem do aluno, gerenciamento da interação, pedagogia, avaliação e feedback de código, e governança (segurança e conformidade das respostas).

### Principais funcionalidades

- **Chat com IA** — tira dúvidas, recebe explicações personalizadas conforme nível (iniciante, intermediário, avançado) e propósito de uso (acadêmico, profissional, hobby)
- **Projetos** — cria, edita, importa e analisa projetos de código diretamente na interface, com revisão automática de arquivos e detecção de inconsistências entre eles
- **Métricas** — painel com estatísticas de uso, tempo de resposta, domínio de conceitos e satisfação
- **Autenticação completa** — cadastro, login e recuperação de senha por e-mail

---

## Stack Tecnológica

| Camada | Tecnologias |
|---|---|
| **Frontend** | React, TypeScript, Tailwind CSS |
| **Backend** | Python, FastAPI |
| **Orquestração de Agentes** | Agno |
| **Modelo de Linguagem** | Anthropic Claude |
| **Banco de Dados** | PostgreSQL + pgvector |
| **Cache / Filas** | Redis |
| **Autenticação** | JWT (JSON Web Tokens) |

---

## Como executar o projeto

### Pré-requisitos

- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/) (inclui o `npm`)
- [Docker](https://www.docker.com/products/docker-desktop/) (para rodar PostgreSQL e Redis)
- Uma chave de API válida da [Anthropic](https://console.anthropic.com/)

### 1. Clonar o repositório

```bash
git clone https://github.com/AntoniojoseBH/TutorAndCoder.git
cd TutorAndCoder
```

### 2. Configurar o backend

Crie e ative um ambiente virtual Python:

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

### 3. Configurar as variáveis de ambiente (`.env`)

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
# ── LLM (obrigatório) ─────────────────────────────────────────────
ANTHROPIC_API_KEY=sua_chave_aqui
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
LLM_MODEL_FAST=claude-haiku-4-5-20251001

# ── Banco de dados ─────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://tutor:senha@localhost:5432/tutoria
REDIS_URL=redis://localhost:6379/0

# ── Segurança ──────────────────────────────────────────────────────
SECRET_KEY=troque_esta_chave_em_producao
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ── E-mail (recuperação de senha via Gmail) ─────────────────────────
SMTP_EMAIL=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_app_gmail

# ── App ────────────────────────────────────────────────────────────
PROJECTS_ROOT=/tmp/student_projects
DEBUG=true
```

> ⚠️ **Importante:** é **obrigatório** substituir `ANTHROPIC_API_KEY` por uma chave de API válida gerada na sua conta da [Anthropic Console](https://console.anthropic.com/settings/keys). Sem essa chave, o sistema não consegue se comunicar com o modelo de linguagem e o chat não funcionará.
>
> Para a recuperação de senha por e-mail, `SMTP_PASSWORD` deve ser uma **Senha de App** do Gmail (não a sua senha normal) — gerada em [myaccount.google.com/security](https://myaccount.google.com/security), na seção "Senhas de app", com a Verificação em duas etapas ativada.

### 4. Subir o banco de dados e o Redis

```bash
docker-compose up -d postgres redis
```

### 5. Rodar o backend

```bash
uvicorn backend.api.main:app --reload --port 8000
```

O backend estará disponível em `http://localhost:8000`.

### 6. Configurar e rodar o frontend

Em outro terminal:

```bash
cd tutor-frontend
npm install
npm start
```

O frontend abrirá automaticamente em `http://localhost:3000`.

---

## Estrutura do projeto

```
TutorAndCoder/
├── backend/
│   ├── agents/          # Agentes especializados (Agno)
│   ├── api/
│   │   ├── routes/      # Endpoints REST (auth, chat, projects, analysis, metrics...)
│   │   └── schemas.py   # Modelos Pydantic
│   ├── db/               # Conexão e modelos do banco de dados
│   ├── tools/            # Ferramentas usadas pelos agentes (edição de arquivos, etc.)
│   └── config.py         # Configurações e variáveis de ambiente
├── tutor-frontend/
│   └── src/
│       ├── pages/         # Páginas (Login, Chat, Projetos, Métricas...)
│       ├── components/    # Componentes reutilizáveis (Sidebar, etc.)
│       ├── context/        # Contexto de autenticação
│       └── api.ts          # Utilitários de comunicação com o backend
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Licença e uso acadêmico

Este projeto foi desenvolvido como Trabalho de Conclusão de Curso (TCC) no Centro Federal de Educação Tecnológica de Minas Gerais (CEFET-MG), sob orientação da Profª. Glívia Angélica Rodrigues Barbosa. Uso e distribuição sujeitos às diretrizes acadêmicas da instituição.
