<img width="1534" height="1025" alt="arquite" src="https://github.com/user-attachments/assets/bf3dc7fa-c8c0-4e57-91e9-362aee19c2d7" />
# TutorAndCoder

**Trabalho de Conclusão de Curso — CEFET-MG**

**Título:** Proposta de uma IA Agêntica para o Apoio ao Aprendizado de Programação de Alunos de Computação

**Aluno:** Antônio José Peixoto Chaves

**Orientadora:** Glívia Angélica Rodrigues Barbosa

---

## Sobre o projeto

O **TutorAndCoder** é um sistema de tutoria baseado em uma arquitetura de **IA agêntica multiagente**, desenvolvido para apoiar estudantes de Computação no aprendizado de programação. O sistema oferece explicações adaptadas ao nível do estudante, propõe desafios de código, analisa projetos enviados com apoio de IA e mantém um perfil de domínio por conceito para cada usuário.

A arquitetura é composta por um **orquestrador** e **seis agentes especializados**, organizados com o framework [Agno](https://github.com/agno-agi/agno):

| Agente | Função |
|---|---|
| Governança | Avalia a segurança das mensagens e a qualidade das respostas |
| Infraestrutura | Persiste e recupera o contexto (interações e histórico da sessão) |
| Modelo do Aluno | Mantém o domínio por conceito, o nível e o estilo de aprendizado |
| Pedagógico | Classifica a intenção, escolhe o próximo conceito e orienta a explicação |
| Avaliação | Executa o código do aluno em sandbox e avalia o resultado |
| Edição de Arquivos | Lê, cria e altera arquivos dos projetos do estudante |

### Principais funcionalidades

- **Chat com IA** — dúvidas e explicações adaptadas ao nível (iniciante, intermediário, avançado) e ao propósito de uso (acadêmico, profissional, hobby). Aceita anexos (imagem, PDF, texto e código) e entrega a resposta em fluxo.
- **Projetos** — criação (em branco ou com IA a partir de uma descrição), edição, importação e análise assistida por IA de arquivos e de projetos, incluindo a busca por inconsistências entre arquivos.
- **Métricas** — painel com uso diário e tempo de resposta.
- **Autenticação** — cadastro, login e recuperação de senha por e-mail.

> A análise de inconsistências é feita pelo modelo de linguagem, não por análise estática, e sua precisão não foi medida.

---

## Arquitetura

![Arquitetura do TutorAndCoder](docs/arquitetura.png)

O frontend (React) se comunica com a API (FastAPI). A API aciona o orquestrador, que coordena os agentes. Os agentes usam o Claude como modelo de linguagem (com o Gemini como provedor de reserva), o PostgreSQL para dados permanentes, o Redis para o cache de sessão e de perfil, e o Judge0 para executar código.

### Stack tecnológica

| Camada | Tecnologias |
|---|---|
| **Frontend** | React, TypeScript, Tailwind CSS |
| **Backend** | Python, FastAPI |
| **Orquestração de agentes** | Agno |
| **Modelo de linguagem** | Anthropic Claude (provedor de reserva: Google Gemini) |
| **Banco de dados** | PostgreSQL com a extensão pgvector instalada (a busca vetorial ainda não está ativa) |
| **Cache** | Redis |
| **Execução de código** | Judge0 |
| **Autenticação** | JWT (JSON Web Tokens) |

---

## Como executar o projeto

### Pré-requisitos

- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/) (inclui o `npm`)
- [Docker](https://www.docker.com/products/docker-desktop/) (para o PostgreSQL e o Redis)
- Uma chave de API da [Anthropic](https://console.anthropic.com/)
- Uma chave do [Judge0 (RapidAPI)](https://rapidapi.com/judge0-official/api/judge0-ce), para a execução de código do aluno

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

Crie um arquivo `.env` na raiz do projeto. **Nunca versione esse arquivo** (confirme que ele está no `.gitignore`).

```env
# ── LLM (obrigatório) ─────────────────────────────────────────────
ANTHROPIC_API_KEY=sua_chave_aqui
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
LLM_MODEL_FAST=claude-haiku-4-5-20251001

# Provedor de reserva (opcional)
GEMINI_API_KEY=

# ── Execução de código (agente de Avaliação) ───────────────────────
JUDGE0_API_URL=https://judge0-ce.p.rapidapi.com
JUDGE0_API_KEY=sua_chave_rapidapi

# ── Banco de dados ─────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://tutor:senha@localhost:5432/tutoria
REDIS_URL=redis://localhost:6379/0

# ── Segurança ──────────────────────────────────────────────────────
SECRET_KEY=troque_esta_chave_em_producao
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# ── E-mail (recuperação de senha via Gmail) ─────────────────────────
SMTP_EMAIL=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_app_gmail
FRONTEND_URL=http://localhost:3000

# ── App ────────────────────────────────────────────────────────────
# Pasta dos projetos dos estudantes. No Windows, use por exemplo C:/tmp/student_projects.
# Em hospedagens com disco temporário, os projetos são perdidos a cada reinício.
PROJECTS_ROOT=/tmp/student_projects
DEBUG=true
```

> ⚠️ **Importante:** substitua `ANTHROPIC_API_KEY` por uma chave válida da [Anthropic Console](https://console.anthropic.com/settings/keys). Sem ela, o chat não funciona. Sem `JUDGE0_API_KEY`, a execução de código do aluno não funciona.
>
> Para a recuperação de senha, `SMTP_PASSWORD` deve ser uma **Senha de App** do Gmail (não a sua senha normal), gerada em [myaccount.google.com/security](https://myaccount.google.com/security), com a verificação em duas etapas ativada.

### 4. Subir o banco de dados e o Redis

```bash
docker compose up -d postgres redis
```

### 5. Rodar o backend

```bash
uvicorn backend.api.main:app --reload --port 8000
```

O backend estará em `http://localhost:8000`. As tabelas são criadas automaticamente na inicialização.

### 6. Popular o banco de exercícios

Execute **uma vez**, com o backend parado ou em outro terminal e o ambiente virtual ativo:

```bash
python seed_exercises.py
```

Sem esse passo, o agente pedagógico não encontra exercícios no banco e usa um exercício genérico.

### 7. Configurar e rodar o frontend

Em outro terminal:

```bash
cd tutor-frontend
npm install
npm start
```

O frontend abre em `http://localhost:3000`. Para apontar para outro backend (por exemplo, um endereço do ngrok), crie `tutor-frontend/.env` com:

```env
REACT_APP_API_URL=http://localhost:8000
```

---

## Estrutura do projeto

```
TutorAndCoder/
├── backend/
│   ├── agents/          # Orquestrador e agentes especializados (Agno)
│   ├── api/
│   │   ├── routes/      # Endpoints REST (auth, chat, projects, analysis, metrics...)
│   │   └── schemas.py   # Modelos Pydantic
│   ├── db/              # Conexão e modelos do banco de dados
│   ├── tools/           # Ferramentas dos agentes (edição de arquivos, etc.)
│   └── config.py        # Configurações e variáveis de ambiente
├── tutor-frontend/
│   └── src/
│       ├── pages/       # Páginas (Login, Chat, Projetos, Métricas...)
│       ├── components/  # Componentes reutilizáveis (Sidebar, etc.)
│       ├── context/     # Contexto de autenticação
│       └── api.ts       # Comunicação com o backend
├── seed_exercises.py    # Popula o banco de exercícios
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Solução de problemas

| Sintoma | Causa provável e solução |
|---|---|
| `invalid x-api-key` (erro 401) | Chave da Anthropic ausente, truncada ou sobrescrita por outra variável de ambiente. Confira o `.env` e reinicie o backend. |
| "Failed to fetch" no navegador | Backend desligado, `REACT_APP_API_URL` incorreta ou bloqueio de CORS. Confirme que `http://localhost:8000` responde. |
| `ModuleNotFoundError` (por exemplo, `agno`) | O ambiente virtual não está ativo, ou as dependências foram instaladas em outro Python. Ative o `venv` e rode `pip install -r requirements.txt`. |
| `ImportError` do `google.genai` | Falta o pacote `google-genai`. Instale com `pip install google-genai`. |
| Erro de conexão com o banco ou o Redis | Os contêineres não estão no ar (`docker compose ps`). Se o backend roda em contêiner, use os nomes dos serviços, não `localhost`. |
| O projeto criado pelo chat não aparece | Confira se `PROJECTS_ROOT` é o mesmo em todo o ambiente e se o disco não é temporário. |

---

## Status e limitações

O TutorAndCoder é um **protótipo de pesquisa**, avaliado com 5 estudantes de Computação por meio de questionário de percepção. Limitações conhecidas:

- A avaliação não incluiu estudantes iniciantes nem comparou a ferramenta com outras.
- O sistema não implementa RAG: o contexto é enriquecido com o perfil do aluno, o histórico da sessão, o banco de exercícios e os arquivos do projeto, por consultas estruturadas.
- O perfil do aluno é atualizado por heurística, e não foi validado contra um método formal de modelagem do conhecimento.
- A edição de arquivos pelo chat é um recurso experimental, não validado na avaliação com usuários.
- O limite de tamanho dos anexos (10 MB) é validado apenas no navegador.

---

## Como citar

> CHAVES, A. J. P. *Proposta de uma IA Agêntica para o Apoio ao Aprendizado de Programação de Alunos de Computação*. Trabalho de Conclusão de Curso — CEFET-MG, 2026.
## Licença e uso acadêmico

Este projeto foi desenvolvido como Trabalho de Conclusão de Curso (TCC) no Centro Federal de Educação Tecnológica de Minas Gerais (CEFET-MG), sob orientação da Profª. Glívia Angélica Rodrigues Barbosa. Uso e distribuição sujeitos às diretrizes acadêmicas da instituição.
