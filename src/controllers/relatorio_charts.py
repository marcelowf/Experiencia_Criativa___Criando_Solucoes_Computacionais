"""Geração de gráficos server-side (matplotlib) para PDF/Excel."""

import io

import matplotlib

matplotlib.use('Agg')  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from controllers.relatorio_stats import (
    dados_por_mes,
    dados_por_recomendacao,
    dados_por_sexo,
    frequencia_sintomas,
    histograma_scores,
    por_profissional,
)

# Paleta consistente com o Asklepios
COR_PRIMARY = '#2563EB'
COR_SUCCESS = '#16A34A'
COR_DANGER = '#DC2626'
COR_INFO = '#0EA5E9'
COR_MUTED = '#94A3B8'


def _fig_to_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=110)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def grafico_por_mes(avaliacoes):
    dados = dados_por_mes(avaliacoes)
    fig, ax = plt.subplots(figsize=(8, 3.5))
    if not dados:
        ax.text(
            0.5,
            0.5,
            'Sem dados',
            ha='center',
            va='center',
            transform=ax.transAxes,
            color=COR_MUTED,
        )
        ax.set_axis_off()
        return _fig_to_png(fig)
    labels = [d['mes'] for d in dados]
    enc = [d['encaminhar'] for d in dados]
    nao = [d['nao_encaminhar'] for d in dados]
    ax.bar(labels, nao, color=COR_SUCCESS, label='Não encaminhar')
    ax.bar(labels, enc, bottom=nao, color=COR_DANGER, label='Encaminhar')
    ax.set_title('Avaliações por mês')
    ax.set_ylabel('Quantidade')
    ax.legend()
    ax.tick_params(axis='x', rotation=30)
    fig.tight_layout()
    return _fig_to_png(fig)


def grafico_recomendacao(avaliacoes):
    d = dados_por_recomendacao(avaliacoes)
    fig, ax = plt.subplots(figsize=(5, 4))
    if sum(d['values']) == 0:
        ax.text(
            0.5,
            0.5,
            'Sem dados',
            ha='center',
            va='center',
            transform=ax.transAxes,
            color=COR_MUTED,
        )
        ax.set_axis_off()
        return _fig_to_png(fig)
    ax.pie(
        d['values'],
        labels=d['labels'],
        colors=[COR_DANGER, COR_SUCCESS],
        autopct='%1.1f%%',
        startangle=90,
        wedgeprops={'width': 0.45},
    )
    ax.set_title('Distribuição por recomendação')
    fig.tight_layout()
    return _fig_to_png(fig)


def grafico_sexo(avaliacoes):
    d = dados_por_sexo(avaliacoes)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    labels = ['Masculino', 'Feminino']
    enc = [d['M']['encaminhar'], d['F']['encaminhar']]
    nao = [d['M']['nao_encaminhar'], d['F']['nao_encaminhar']]
    if sum(enc) + sum(nao) == 0:
        ax.text(
            0.5,
            0.5,
            'Sem dados',
            ha='center',
            va='center',
            transform=ax.transAxes,
            color=COR_MUTED,
        )
        ax.set_axis_off()
        return _fig_to_png(fig)
    x = range(len(labels))
    w = 0.35
    ax.bar([i - w / 2 for i in x], enc, w, color=COR_DANGER, label='Encaminhar')
    ax.bar([i + w / 2 for i in x], nao, w, color=COR_SUCCESS, label='Não encaminhar')
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_title('Resultados por sexo')
    ax.set_ylabel('Quantidade')
    ax.legend()
    fig.tight_layout()
    return _fig_to_png(fig)


def grafico_histograma(avaliacoes):
    d = histograma_scores(avaliacoes)
    fig, ax = plt.subplots(figsize=(8, 3.5))
    if not d['values']:
        ax.text(
            0.5,
            0.5,
            'Sem dados',
            ha='center',
            va='center',
            transform=ax.transAxes,
            color=COR_MUTED,
        )
        ax.set_axis_off()
        return _fig_to_png(fig)
    ax.bar(d['labels'], d['values'], color=COR_PRIMARY)
    ax.set_title('Distribuição de scores')
    ax.set_xlabel('Score (bucket de 0.05)')
    ax.set_ylabel('Quantidade')
    ax.tick_params(axis='x', rotation=45)
    fig.tight_layout()
    return _fig_to_png(fig)


def grafico_sintomas(avaliacoes, top_n=12):
    dados = frequencia_sintomas(avaliacoes, top_n=top_n)
    fig, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(dados) + 1)))
    if not dados:
        ax.text(
            0.5,
            0.5,
            'Sem dados',
            ha='center',
            va='center',
            transform=ax.transAxes,
            color=COR_MUTED,
        )
        ax.set_axis_off()
        return _fig_to_png(fig)
    labels = [d[0] for d in reversed(dados)]
    valores = [d[1] for d in reversed(dados)]
    ax.barh(labels, valores, color=COR_INFO)
    ax.set_title('Frequência dos sintomas')
    ax.set_xlabel('Avaliações em que o sintoma esteve presente')
    fig.tight_layout()
    return _fig_to_png(fig)


def grafico_profissional(avaliacoes):
    dados = por_profissional(avaliacoes)
    fig, ax = plt.subplots(figsize=(8, max(3, 0.4 * len(dados) + 1)))
    if not dados:
        ax.text(
            0.5,
            0.5,
            'Sem dados',
            ha='center',
            va='center',
            transform=ax.transAxes,
            color=COR_MUTED,
        )
        ax.set_axis_off()
        return _fig_to_png(fig)
    nomes = [d[0] for d in reversed(dados)]
    valores = [d[1] for d in reversed(dados)]
    ax.barh(nomes, valores, color=COR_PRIMARY)
    ax.set_title('Avaliações por profissional')
    ax.set_xlabel('Quantidade')
    fig.tight_layout()
    return _fig_to_png(fig)


def gerar_todos(avaliacoes, incluir_profissional=False):
    """Retorna dict com bytes PNG de todos os graficos."""
    out = {
        'por_mes': grafico_por_mes(avaliacoes),
        'recomendacao': grafico_recomendacao(avaliacoes),
        'sexo': grafico_sexo(avaliacoes),
        'histograma': grafico_histograma(avaliacoes),
        'sintomas': grafico_sintomas(avaliacoes),
    }
    if incluir_profissional:
        out['profissional'] = grafico_profissional(avaliacoes)
    return out
