# Triagem SXF — Síndrome do X Frágil

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/) [![Flask](https://img.shields.io/badge/Flask-3BABC3?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/) [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Jinja](https://img.shields.io/badge/Jinja-7E0C1B?style=for-the-badge&logo=jinja&logoColor=white)](https://jinja.palletsprojects.com/) [![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/docs/Web/HTML) [![CSS](https://img.shields.io/badge/CSS-663399?style=for-the-badge&logo=css&logoColor=white)](https://developer.mozilla.org/docs/Web/CSS) [![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/docs/Web/JavaScript) [![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/) [![jQuery](https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white)](https://jquery.com/) [![Font Awesome](https://img.shields.io/badge/Font%20Awesome-538DD7?style=for-the-badge&logo=fontawesome&logoColor=white)](https://fontawesome.com/) [![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white)](https://www.chartjs.org/) [![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)](https://ollama.com/) [![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/) [![Terraform](https://img.shields.io/badge/Terraform-844FBA?style=for-the-badge&logo=terraform&logoColor=white)](https://www.terraform.io/) [![Ruff](https://img.shields.io/badge/Ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/) [![pre-commit](https://img.shields.io/badge/pre--commit-FAB040?style=for-the-badge&logo=pre-commit&logoColor=black)](https://pre-commit.com/) [![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org/) [![Git](https://img.shields.io/badge/Git-F03C2E?style=for-the-badge&logo=git&logoColor=white)](https://git-scm.com/)

Sistema web de **triagem clínica para a Síndrome do X Frágil (SXF)** baseado em score de
sintomas ponderados por sexo. Apoia o profissional na decisão de **encaminhar ou não** um
paciente para teste genético confirmatório — sem substituir o julgamento clínico.

---

## Como rodar

```bash
docker compose up -d
```

Sobe três serviços: `db` (PostgreSQL), `web` (Flask, porta **8080**) e `ollama` (IA local).

**Login inicial:** `admin@admin.com` / `admin123`

### Healthcheck

```bash
curl http://localhost:8080/health
```

### Assistente de IA (Ollama)

O serviço `ollama` sobe junto, mas o **modelo precisa ser baixado** uma vez:

```bash
docker compose exec ollama ollama pull qwen2.5:7b
```

Depois, em **Administração ▸ IA**, ajuste criatividade / nº de consultas e ative. A URL e o
modelo são definidos por variável de ambiente (`OLLAMA_URL` / `OLLAMA_MODEL`), não pela tela.

> 💡 Sem GPU o modelo funciona, mas é lento (dezenas de segundos por resposta). Para uso
> intenso, recomenda-se GPU ou um modelo menor (ex.: `qwen2.5:3b`).

### Rodar testes

```bash
docker compose exec web pytest /tests -v
```

### Formatação automática (pre-commit)

O código Python é formatado e lintado automaticamente pelo [Ruff](https://docs.astral.sh/ruff/)
via [pre-commit](https://pre-commit.com/).

```bash
pip install pre-commit       # ou: pipx install pre-commit
pre-commit install           # passa a rodar a cada git commit
pre-commit run --all-files   # rodar em tudo manualmente
```

Regras em [`pyproject.toml`](pyproject.toml) (Ruff) e [`.pre-commit-config.yaml`](.pre-commit-config.yaml).

---

## Variáveis de ambiente

| Variável               | Default                                                | Descrição                                 |
| ---------------------- | ------------------------------------------------------ | ----------------------------------------- |
| `DATABASE_URL`         | `postgresql://sxf_user:sxf_pass@localhost:5432/sxf_db` | Conexão SQLAlchemy                        |
| `SECRET_KEY`           | `dev-secret-mude-em-producao`                          | Sessões Flask, CSRF e cifra da senha SMTP |
| `OLLAMA_URL`           | `http://ollama:11434`                                  | Endereço do servidor Ollama               |
| `OLLAMA_MODEL`         | `qwen2.5:7b`                                           | Modelo usado pelo assistente de IA        |
| `GOOGLE_CLIENT_ID`     | _(vazio)_                                              | Habilita login com Google (opcional)      |
| `GOOGLE_CLIENT_SECRET` | _(vazio)_                                              | Segredo do OAuth Google (opcional)        |

---

## Funcionalidades

**Triagem & sintomas**

- Score ponderado por sexo, com limiar de encaminhamento (`ENCAMINHAR` / `NÃO ENCAMINHAR`).
- **Versionamento imutável dos pesos** científicos: cada avaliação fica vinculada à versão de
  pesos usada no cálculo; alterar um peso cria uma nova versão (histórico preservado).

**Pacientes**

- Cadastro com **CPF validado** (algoritmo módulo 11) e **consentimento LGPD** registrado.
- **Responsável** em tabela própria, compartilhável entre pacientes (irmãos, por ex.).
- **Anamnese** (histórico clínico e familiar) e **dados socioeconômicos** opcionais.
- Soft-delete com **lixeira** (restaurável por admin).

**Auto-cadastro via QR Code**

- Geração de QR com link público para o paciente preencher o próprio cadastro pelo celular.
- Validade configurável (minutos a anos, ou indeterminada), **prorrogação** e **revogação**.
- Opção de **enviar o link por e-mail**.

**Relatórios & indicadores**

- Dashboard com filtros, KPIs e gráficos (Chart.js).
- Exportação em **PDF** (WeasyPrint) e **Excel** (openpyxl).
- Filtro e **comparativo entre versões de pesos**; painel **socioeconômico** agregado.

**Assistente de IA** (opcional)

- Chat flutuante com **modelo local via [Ollama](https://ollama.com/)** — nenhum dado sai do servidor.
- Consulta o banco por **ferramentas pré-definidas e auditadas** (nunca SQL livre), respeitando
  permissões: admin vê tudo, profissional padrão só os próprios dados.
- Resposta em **streaming**; cada consulta fica registrada na auditoria.

**E-mail** (opcional)

- Recuperação de senha, envio do QR e do **resultado de exame (PDF anexo)**.
- Configurável pelo admin com **Senha de App do Gmail** (guardada cifrada — Fernet).

**Administração & segurança**

- Perfis **admin / padrão**; garantia de que sempre existe ao menos um admin.
- **Login com Google** opcional (OAuth), além de e-mail/senha.
- **Auditoria** completa de ações e trilha _criado/atualizado por_ nos registros.

---

## Resetar o ambiente Docker

> ⚠️ **Destrói containers, imagens e volumes** — inclusive o banco de dados local.

```bash
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
docker system prune -a --volumes
```
