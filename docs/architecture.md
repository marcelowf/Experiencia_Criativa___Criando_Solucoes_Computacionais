# Arquitetura — Triagem SXF

> Visão técnica para desenvolvedores. Para stack e instruções de execução, ver [README.md](../README.md).
> Para regras de negócio, ver [REQUISITOS.md](REQUISITOS.md). Para fundamento clínico dos pesos, ver [PESQUISA.md](PESQUISA.md).

---

## 1. Visão de camadas

```
┌──────────────────────────────────────────────────────────┐
│  Browser  (Bootstrap 4 + jQuery + DataTables + Chart.js) │
└───────────────┬──────────────────────────────────────────┘
                │ HTTP
┌───────────────▼──────────────────────────────────────────┐
│  Flask app  (app factory + blueprints)                   │
│  ├─ views/        Jinja2 templates                       │
│  ├─ controllers/  rotas + lógica por domínio             │
│  └─ models/       SQLAlchemy ORM                         │
└───────────────┬──────────────────────────────────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
   PostgreSQL 16     WeasyPrint / openpyxl / matplotlib
   (prod)            (geração de PDF / Excel / gráficos)
```

Entrada: [src/app.py](../src/app.py) → `create_app()` em [src/controllers/app_controller.py](../src/controllers/app_controller.py).

---

## 2. Organização do código

```
src/
├── app.py                       # entrypoint (porta 8080)
├── requirements.txt
├── controllers/                 # blueprints + lógica de domínio
│   ├── app_controller.py        # create_app(), seeds, healthcheck
│   ├── auth_controller.py       # login, logoff, tema
│   ├── reset_senha_controller.py
│   ├── paciente_controller.py   # CRUD paciente
│   ├── avaliacao_controller.py  # formulário + cálculo + salvar
│   ├── sintoma_controller.py    # admin: catálogo de sintomas
│   ├── usuario_controller.py    # admin: usuários
│   ├── relatorio_controller.py  # filtros + render + exportações
│   ├── relatorio_charts.py      # geração de gráficos (server-side, matplotlib)
│   ├── relatorio_stats.py       # agregações para os gráficos
│   ├── logs_controller.py       # tela de auditoria
│   ├── audit.py                 # helper log_audit()
│   ├── scoring.py               # cálculo do score
│   ├── versoes_pesos.py         # publicação de novas versões de pesos
│   └── seed_data.py             # sintomas iniciais (com descrição clínica)
├── models/
│   └── models.py                # todas as tabelas SQLAlchemy
├── views/                       # templates Jinja2 por domínio
│   ├── base.html
│   ├── base_login.html
│   ├── auth/  avaliacoes/  pacientes/  relatorios/
│   ├── sintomas/  usuarios/  logs/  errors/
└── static/
    ├── css/   (bootstrap, style, themes, font-awesome, datatables)
    └── js/    (jquery, bootstrap, popper, datatables)
tests/                           # pytest (SQLite in-memory)
```

---

## 3. Modelo de dados

```
Usuario ──┬── Paciente ── Avaliacao ── SintomaAvaliacao ── Sintoma
          │      │
          │      └── (soft delete: removido_em)
          │
          ├── UserPreference (tema)
          └── LogAuditoria (auditoria por usuário)

Sintoma ──┬── (peso M/F denormalizado da versão ativa)
          │
VersaoPesos ── SintomaPesoVersao (snapshot imutável dos pesos por versão)
                                     ▲
                                     │
              Avaliacao.id_versao_pesos
```

Definições em [src/models/models.py](../src/models/models.py).

### Tabelas

| Tabela | Função |
|---|---|
| `usuarios` | Profissional ou admin; senha hash, token de reset |
| `user_preferences` | Tema escolhido por usuário (claro / escuro / auto) |
| `pacientes` | Dados do paciente + `consentimento_dado_em` (LGPD) + `removido_em` (soft delete) |
| `avaliacoes` | Score, recomendação, aponta para a **versão de pesos** usada |
| `sintomas` | Catálogo (chave, label, peso M, peso F, descrição clínica, ativo) |
| `versoes_pesos` | Cabeçalho da versão (nome, criada_em, ativa) |
| `sintoma_peso_versao` | Pesos congelados por versão (1 linha por sintoma × versão) |
| `sintomas_avaliacao` | N:N — sintomas marcados em cada avaliação |
| `logs` | Auditoria: ação, entidade, usuário, IP, JSON de detalhes |

---

## 4. Decisões-chave

### 4.1 Pesos versionados e imutáveis
Os pesos científicos podem ser republicados pelo admin, mas **toda avaliação fica amarrada à versão que a calculou** (`Avaliacao.id_versao_pesos` → `VersaoPesos`). A tabela `SintomaPesoVersao` é tratada como append-only: avaliações antigas continuam reproduzíveis indefinidamente.

O catálogo `Sintoma` mantém uma **denormalização** dos pesos da versão ativa apenas para acelerar a renderização do formulário; a fonte canônica do histórico é `SintomaPesoVersao`.

### 4.2 Soft delete em pacientes
`pacientes.removido_em` (`DateTime` nullable). Listas comuns filtram por `removido_em IS NULL`; admin tem visão das removidas e pode restaurar. Avaliações associadas permanecem para auditoria.

### 4.3 Auditoria por chamada explícita
Não há triggers no banco nem decorator mágico. Cada controller chama `log_audit(...)` ([src/controllers/audit.py](../src/controllers/audit.py)) nos pontos sensíveis (criar/editar/remover paciente, criar avaliação, login/logoff, falha de login, etc.). Trade-off consciente: menos magia, mais explícito, mais fácil de auditar.

### 4.4 Score determinístico e centralizado
Toda a regra de cálculo está em [src/controllers/scoring.py](../src/controllers/scoring.py). Os limiares (`0,56` ♂ / `0,55` ♀) são **constantes do domínio** no código; os **pesos** vêm do banco. A separação reflete a natureza dos dados: limiar é decisão de política clínica (raramente muda), peso é parâmetro do modelo (pode ser republicado).

### 4.5 Gráficos em dois mundos
- Web: Chart.js (interativo no navegador).
- PDF/Excel: matplotlib server-side ([src/controllers/relatorio_charts.py](../src/controllers/relatorio_charts.py)) → imagens embutidas via WeasyPrint / openpyxl.

### 4.6 Banco diferente em produção e em testes
- Prod/dev: PostgreSQL 16 (`docker-compose.yml`).
- Testes: SQLite in-memory ([tests/conftest.py](../tests/conftest.py)) — rápido, isolado por teste, sem dependência de Docker para `pytest`.

---

## 5. Fluxo de uma avaliação

```
1. GET  /avaliacoes/nova/<id_paciente>
       └─ controller carrega sintomas ativos com peso para o sexo do paciente
       └─ template renderiza checkboxes (com tooltip da descrição clínica)

2. POST /avaliacoes/nova
       └─ scoring.calcular_score(sintomas_marcados, sexo)
       └─ persiste Avaliacao + SintomaAvaliacao
       └─ Avaliacao.id_versao_pesos = versão ativa atual
       └─ audit.log_audit('CREATE', 'avaliacao', ...)

3. GET  /avaliacoes/<id>/resultado
       └─ exibe score, recomendação, lista de sintomas marcados
```

---

## 6. Bootstrap do ambiente

Ao subir, `create_app()` executa em ordem:

1. `db.create_all()` — cria tabelas se não existirem (em prod, migrations Alembic substituem isso).
2. `_seed_sintomas()` — popula `sintomas` com os 12 iniciais; em execuções subsequentes apenas completa `descricao_clinica` vazia (preserva edições do admin).
3. `_seed_admin()` — cria `admin@admin.com` / `admin123` se ausente.
4. `_seed_user_preferences()` — garante uma linha em `user_preferences` para cada usuário.
5. `_seed_versao_pesos_inicial()` — cria a versão inicial (V1) dos pesos como ativa.

---

## 7. Segurança aplicada

| Risco (OWASP) | Mitigação | Onde |
|---|---|---|
| A01 Broken Access Control | `@login_required` + check de `is_admin` por endpoint | controllers |
| A02 Cryptographic Failures | Hash de senha via `werkzeug.security` | [models.py:48-51](../src/models/models.py#L48-L51) |
| A03 Injection | ORM parametrizado (sem SQL string) | toda camada de dados |
| A05 Security Misconfiguration | `SECRET_KEY` via env var | [app_controller.py:19](../src/controllers/app_controller.py#L19) |
| A07 Auth Failures | Bloqueio após 5 falhas / 15 min; política de senha; reset por token de 1h | `auth_controller.py`, [models.py:14-24](../src/models/models.py#L14-L24) |
| A09 Logging Failures | Tabela `logs` + chamadas explícitas a `log_audit()` | `audit.py` |
| CSRF | Flask-WTF global | [app_controller.py:11,30](../src/controllers/app_controller.py#L11) |

---

## 8. Pontos abertos

Ver [TODO.md](../TODO.md) — destaque para CI/CD, Terraform para Azure Web App e testes de usabilidade.
