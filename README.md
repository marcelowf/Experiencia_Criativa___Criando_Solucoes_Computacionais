# Triagem SXF — Síndrome do X Frágil

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/) [![Flask](https://img.shields.io/badge/Flask-3BABC3?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/) [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/) [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Jinja](https://img.shields.io/badge/Jinja-7E0C1B?style=for-the-badge&logo=jinja&logoColor=white)](https://jinja.palletsprojects.com/) [![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)](https://developer.mozilla.org/docs/Web/HTML) [![CSS](https://img.shields.io/badge/CSS-663399?style=for-the-badge&logo=css&logoColor=white)](https://developer.mozilla.org/docs/Web/CSS) [![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/docs/Web/JavaScript) [![Bootstrap](https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/) [![jQuery](https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white)](https://jquery.com/) [![Font Awesome](https://img.shields.io/badge/Font%20Awesome-538DD7?style=for-the-badge&logo=fontawesome&logoColor=white)](https://fontawesome.com/) [![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white)](https://www.chartjs.org/) [![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/) [![Terraform](https://img.shields.io/badge/Terraform-844FBA?style=for-the-badge&logo=terraform&logoColor=white)](https://www.terraform.io/) [![Git](https://img.shields.io/badge/Git-F03C2E?style=for-the-badge&logo=git&logoColor=white)](https://git-scm.com/)

Sistema de triagem clínica para Síndrome do X Frágil baseado em score de sintomas ponderados.

---

## Como rodar

```bash
docker compose up -d
```

**Login inicial:** `admin@admin.com` / `admin123`

### Healthcheck

```bash
curl http://localhost:8080/health
```

### Rodar testes

```bash
docker compose exec web pytest tests/ -v
```

### Variáveis de ambiente reconhecidas

| Variável | Default | Descrição |
|---|---|---|
| `DATABASE_URL` | `postgresql://sxf_user:sxf_pass@localhost:5432/sxf_db` | Conexão SQLAlchemy |
| `SECRET_KEY` | `dev-secret-mude-em-producao` | Sessões Flask e CSRF |

docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
docker system prune -a --volumes
