"""Serviço de IA local (Ollama) com tool calling.

A IA recebe APENAS as ferramentas permitidas ao papel do usuário (ver ai_tools.specs).
O loop executa as tools que a IA pedir (já com scoping/whitelist em ai_tools.dispatch)
e devolve a resposta final em linguagem natural.
"""

import json

import requests

from models.models import db, AiConfig, ChatMensagem
from controllers import ai_tools

# Timeout por chamada HTTP ao Ollama. Generoso porque, em CPU (sem GPU), o
# carregamento do modelo + o processamento do prompt com as ferramentas pode
# levar bem mais de 2 min na primeira mensagem. Em GPU, as respostas são rápidas
# e este teto raramente é tocado.
TIMEOUT_INFERENCIA = 300


class IaNaoConfiguradaError(RuntimeError):
    """IA não está configurada/ativa."""


class IaIndisponivelError(RuntimeError):
    """Ollama fora do ar ou erro de comunicação."""


def get_config():
    return AiConfig.query.first()


def ia_configurada() -> bool:
    c = get_config()
    return bool(c and c.ativo and c.base_url and c.modelo)


def listar_modelos():
    """Lista os modelos instalados no Ollama (para a tela de config testar conexão)."""
    c = get_config()
    if not c or not c.base_url:
        raise IaNaoConfiguradaError('Configure a URL do Ollama primeiro.')
    try:
        r = requests.get(f'{c.base_url.rstrip("/")}/api/tags', timeout=10)
        r.raise_for_status()
        return [m.get('name') for m in r.json().get('models', [])]
    except requests.RequestException as e:
        raise IaIndisponivelError(f'Não foi possível conectar ao Ollama: {e}') from e


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
    """Reconstrói o histórico textual (turnos anteriores) — só user/assistant."""
    msgs = []
    for m in conversa.mensagens:
        if m.papel in ('user', 'assistant') and (m.conteudo or '').strip():
            msgs.append({'role': m.papel, 'content': m.conteudo})
    return msgs


def _extrair_args(tool_call):
    args = (tool_call.get('function') or {}).get('arguments')
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (ValueError, TypeError):
            args = {}
    return args or {}


def chat(conversa, texto_usuario, current_user):
    """Roda uma rodada de conversa. Persiste mensagens e devolve {'resposta': str}.

    Levanta IaNaoConfiguradaError / IaIndisponivelError em caso de problema.
    """
    if not ia_configurada():
        raise IaNaoConfiguradaError('O assistente de IA não está configurado.')
    c = get_config()
    base = c.base_url.rstrip('/')

    # 1. persiste a pergunta do usuário
    db.session.add(ChatMensagem(id_conversa=conversa.id, papel='user', conteudo=texto_usuario))
    # título a partir da 1ª pergunta
    if conversa.titulo in (None, '', 'Nova conversa'):
        conversa.titulo = texto_usuario[:120]
    db.session.commit()

    # 2. monta as mensagens (system + histórico anterior + pergunta atual)
    messages = [{'role': 'system', 'content': _system_prompt(current_user)}]
    messages.extend(_historico_para_mensagens(conversa))

    tools = ai_tools.specs(current_user)
    resposta_final = None

    # 3. loop de tool calling
    for _ in range(max(1, c.max_iteracoes)):
        try:
            r = requests.post(
                f'{base}/api/chat',
                json={'model': c.modelo, 'messages': messages, 'tools': tools,
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

        # adiciona o turno do assistant (com os pedidos de tool) ao contexto local
        messages.append({'role': 'assistant', 'content': msg.get('content') or '',
                         'tool_calls': tool_calls})

        for tc in tool_calls:
            nome = (tc.get('function') or {}).get('name', '')
            args = _extrair_args(tc)
            resultado = ai_tools.dispatch(nome, current_user, args)
            conteudo_json = json.dumps(resultado, ensure_ascii=False, default=str)
            # contexto para o modelo
            messages.append({'role': 'tool', 'name': nome, 'content': conteudo_json})
            # persiste para auditoria/exibição
            db.session.add(ChatMensagem(id_conversa=conversa.id, papel='tool',
                                        tool_nome=nome, conteudo=conteudo_json))
        db.session.commit()

    if not resposta_final:
        resposta_final = ('Não consegui concluir a consulta. Tente reformular a pergunta '
                          'ou seja mais específico.')

    db.session.add(ChatMensagem(id_conversa=conversa.id, papel='assistant',
                                conteudo=resposta_final))
    db.session.commit()
    return {'resposta': resposta_final}
