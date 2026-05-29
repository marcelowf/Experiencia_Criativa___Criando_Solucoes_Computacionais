"""Serviço de IA local (Ollama) com tool calling + streaming.

A URL do servidor e o modelo são decisão de dev (env: OLLAMA_URL / OLLAMA_MODEL).
A IA recebe APENAS as ferramentas permitidas ao papel do usuário (ai_tools.specs);
o loop executa as tools que ela pedir (scoping/whitelist em ai_tools.dispatch).
"""

import json

import requests
from flask import current_app

from models.models import db, AiConfig, ChatMensagem
from controllers import ai_tools

# Timeout por chamada HTTP ao Ollama. Generoso porque, em CPU (sem GPU), o
# carregamento do modelo + o processamento do prompt com as ferramentas pode
# levar bem mais de 2 min. Em GPU, as respostas são rápidas e este teto raramente
# é tocado.
TIMEOUT_INFERENCIA = 300


class IaNaoConfiguradaError(RuntimeError):
    """IA desativada pelo admin."""


class IaIndisponivelError(RuntimeError):
    """Ollama fora do ar ou erro de comunicação."""


# ---------- config (env = dev, banco = admin) ----------

def _base_url():
    return current_app.config.get('OLLAMA_URL', 'http://ollama:11434').rstrip('/')


def _modelo():
    return current_app.config.get('OLLAMA_MODEL', 'qwen2.5:7b')


def get_config():
    return AiConfig.query.first()


def ia_configurada() -> bool:
    """A IA está utilizável se o admin a deixou ativa (URL/modelo vêm de env)."""
    c = get_config()
    return bool(c and c.ativo)


def listar_modelos():
    """Lista os modelos instalados no Ollama (para a tela de config testar conexão)."""
    try:
        r = requests.get(f'{_base_url()}/api/tags', timeout=10)
        r.raise_for_status()
        return [m.get('name') for m in r.json().get('models', [])]
    except requests.RequestException as e:
        raise IaIndisponivelError(f'Não foi possível conectar ao Ollama: {e}') from e


# ---------- helpers de conversa ----------

def _system_prompt(current_user):
    escopo = ('Você é ADMINISTRADOR e pode consultar dados de todos os pacientes, '
              'socioeconômico, logs e profissionais.'
              if current_user.is_admin else
              'Você é um profissional PADRÃO: só pode ver os SEUS pacientes e avaliações. '
              'Consultas administrativas não estão disponíveis para você.')
    return (
        'Você é o assistente clínico do sistema Triagem SXF (Síndrome do X Frágil). '
        'Responda sempre em português do Brasil, de forma objetiva e profissional. '
        'Use SOMENTE as ferramentas disponíveis para obter dados reais do sistema — '
        'nunca invente pacientes, números ou resultados. Se uma ferramenta retornar '
        '{"erro": ...}, explique a limitação ao usuário com clareza. '
        'Não forneça diagnóstico definitivo: a triagem é apoio à decisão clínica. '
        f'{escopo} '
        f'O usuário atual chama-se {current_user.nome}.'
    )


def _historico_para_mensagens(conversa):
    """Histórico textual (turnos anteriores) — só user/assistant."""
    return [{'role': m.papel, 'content': m.conteudo}
            for m in conversa.mensagens
            if m.papel in ('user', 'assistant') and (m.conteudo or '').strip()]


def _extrair_args(tool_call):
    args = (tool_call.get('function') or {}).get('arguments')
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (ValueError, TypeError):
            args = {}
    return args or {}


def _persistir_pergunta(conversa, texto_usuario):
    db.session.add(ChatMensagem(id_conversa=conversa.id, papel='user', conteudo=texto_usuario))
    if conversa.titulo in (None, '', 'Nova conversa'):
        conversa.titulo = texto_usuario[:120]
    db.session.commit()


def _executar_tools(conversa, tool_calls, current_user, messages):
    """Executa as tools pedidas (scoped), persiste e injeta o resultado no contexto.

    Devolve a lista de nomes executados (para emitir status no streaming).
    """
    nomes = []
    for tc in tool_calls:
        nome = (tc.get('function') or {}).get('name', '')
        resultado = ai_tools.dispatch(nome, current_user, _extrair_args(tc))
        conteudo_json = json.dumps(resultado, ensure_ascii=False, default=str)
        messages.append({'role': 'tool', 'name': nome, 'content': conteudo_json})
        db.session.add(ChatMensagem(id_conversa=conversa.id, papel='tool',
                                    tool_nome=nome, conteudo=conteudo_json))
        nomes.append(nome)
    db.session.commit()
    return nomes


# ---------- streaming (usado pelo widget) ----------

def chat_stream(conversa, texto_usuario, current_user):
    """Generator de eventos para SSE:
        {'tipo':'status','tool':nome}  — uma consulta à base foi feita
        {'tipo':'token','texto':...}   — pedaço da resposta final
        {'tipo':'fim'}                 — concluído

    Levanta IaNaoConfiguradaError / IaIndisponivelError.
    """
    if not ia_configurada():
        raise IaNaoConfiguradaError('O assistente de IA está desativado.')
    c = get_config()
    base, modelo = _base_url(), _modelo()

    _persistir_pergunta(conversa, texto_usuario)
    messages = [{'role': 'system', 'content': _system_prompt(current_user)}]
    messages.extend(_historico_para_mensagens(conversa))
    tools = ai_tools.specs(current_user)

    resposta_final = ''
    for _ in range(max(1, c.max_iteracoes)):
        content_acc = ''
        tool_calls_acc = []
        try:
            with requests.post(
                f'{base}/api/chat',
                json={'model': modelo, 'messages': messages, 'tools': tools,
                      'stream': True, 'options': {'temperature': c.temperatura}},
                stream=True, timeout=TIMEOUT_INFERENCIA,
            ) as r:
                r.raise_for_status()
                for linha in r.iter_lines():
                    if not linha:
                        continue
                    chunk = json.loads(linha)
                    m = chunk.get('message', {}) or {}
                    pedaco = m.get('content') or ''
                    if pedaco and not tool_calls_acc:
                        content_acc += pedaco
                        yield {'tipo': 'token', 'texto': pedaco}
                    if m.get('tool_calls'):
                        tool_calls_acc.extend(m['tool_calls'])
                    if chunk.get('done'):
                        break
        except requests.RequestException as e:
            raise IaIndisponivelError(f'Falha na comunicação com a IA: {e}') from e

        if tool_calls_acc:
            messages.append({'role': 'assistant', 'content': content_acc,
                             'tool_calls': tool_calls_acc})
            for nome in _executar_tools(conversa, tool_calls_acc, current_user, messages):
                yield {'tipo': 'status', 'tool': nome}
            continue

        resposta_final = content_acc.strip()
        break

    if not resposta_final:
        resposta_final = ('Não consegui concluir a consulta. Tente reformular a '
                          'pergunta ou seja mais específico.')
        yield {'tipo': 'token', 'texto': resposta_final}

    db.session.add(ChatMensagem(id_conversa=conversa.id, papel='assistant',
                                conteudo=resposta_final))
    db.session.commit()
    yield {'tipo': 'fim'}


# ---------- não-streaming (fallback / testes) ----------

def chat(conversa, texto_usuario, current_user):
    """Versão não-streaming: roda o fluxo e devolve {'resposta': str}."""
    if not ia_configurada():
        raise IaNaoConfiguradaError('O assistente de IA está desativado.')
    c = get_config()
    base, modelo = _base_url(), _modelo()

    _persistir_pergunta(conversa, texto_usuario)
    messages = [{'role': 'system', 'content': _system_prompt(current_user)}]
    messages.extend(_historico_para_mensagens(conversa))
    tools = ai_tools.specs(current_user)

    resposta_final = None
    for _ in range(max(1, c.max_iteracoes)):
        try:
            r = requests.post(
                f'{base}/api/chat',
                json={'model': modelo, 'messages': messages, 'tools': tools,
                      'stream': False, 'options': {'temperature': c.temperatura}},
                timeout=TIMEOUT_INFERENCIA,
            )
            r.raise_for_status()
            msg = r.json().get('message', {}) or {}
        except requests.RequestException as e:
            raise IaIndisponivelError(f'Falha na comunicação com a IA: {e}') from e

        tool_calls = msg.get('tool_calls') or []
        if not tool_calls:
            resposta_final = (msg.get('content') or '').strip()
            break
        messages.append({'role': 'assistant', 'content': msg.get('content') or '',
                         'tool_calls': tool_calls})
        _executar_tools(conversa, tool_calls, current_user, messages)

    if not resposta_final:
        resposta_final = ('Não consegui concluir a consulta. Tente reformular a '
                          'pergunta ou seja mais específico.')
    db.session.add(ChatMensagem(id_conversa=conversa.id, papel='assistant',
                                conteudo=resposta_final))
    db.session.commit()
    return {'resposta': resposta_final}
