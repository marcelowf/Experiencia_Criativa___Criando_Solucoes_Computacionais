"""Testes do chat de IA: config admin, streaming (Ollama mockado), widget, privacidade."""

import json
from unittest.mock import patch

from flask_login import login_user

from controllers import ai_service
from models.models import AiConfig, ChatConversa, ChatMensagem, db

# ---------- fake do streaming do Ollama ----------


class _FakeStream:
    """Simula a resposta streaming do Ollama (context manager + iter_lines)."""

    def __init__(self, linhas):
        self._linhas = linhas

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        for l in self._linhas:
            yield l.encode('utf-8')


def _chunk(content='', tool_calls=None, done=False):
    msg = {'role': 'assistant', 'content': content}
    if tool_calls:
        msg['tool_calls'] = tool_calls
    return json.dumps({'message': msg, 'done': done})


# ---------- config admin ----------


def test_config_ia_requer_admin(auth_client_padrao):
    assert auth_client_padrao.get('/config/ia/').status_code == 403


def test_salvar_config_sem_campos_de_dev(auth_client, app):
    r = auth_client.post(
        '/config/ia/',
        data={'temperatura': '0.7', 'max_iteracoes': '3'},
        follow_redirects=True,
    )
    assert r.status_code == 200
    with app.app_context():
        c = AiConfig.query.first()
        assert abs(c.temperatura - 0.7) < 1e-6
        assert c.max_iteracoes == 3
        assert c.ativo is True


def test_config_nao_expoe_url_nem_modelo_editaveis(auth_client):
    body = auth_client.get('/config/ia/').data.decode('utf-8')
    assert 'name="base_url"' not in body
    assert 'name="modelo"' not in body
    assert 'Criatividade' in body  # slider presente
    assert 'type="range"' in body


def test_desativar_desliga_ia(auth_client, app):
    auth_client.post('/config/ia/desativar', follow_redirects=True)
    with app.app_context():
        assert AiConfig.query.first().ativo is False
        assert ai_service.ia_configurada() is False


# ---------- ai_service: env + flags ----------


def test_url_e_modelo_vem_de_env(app):
    with app.app_context():
        assert ai_service._base_url() == app.config['OLLAMA_URL'].rstrip('/')
        assert ai_service._modelo() == app.config['OLLAMA_MODEL']


def test_ia_configurada_depende_do_ativo(app, db):
    with app.app_context():
        assert ai_service.ia_configurada() is True  # seed cria ativa
        AiConfig.query.first().ativo = False
        db.session.commit()
        assert ai_service.ia_configurada() is False


# ---------- streaming (generator) ----------


def test_chat_stream_tool_calling(app, admin, db):
    with app.test_request_context():
        login_user(admin)
        conv = ChatConversa(id_usuario=admin.id, titulo='Nova conversa')
        db.session.add(conv)
        db.session.commit()

        resp_tool = _FakeStream(
            [
                _chunk(
                    tool_calls=[{'function': {'name': 'buscar_pacientes', 'arguments': {}}}],
                    done=True,
                )
            ]
        )
        resp_final = _FakeStream(
            [
                _chunk(content='Você '),
                _chunk(content='não tem pacientes.'),
                _chunk(done=True),
            ]
        )
        with patch('controllers.ai_service.requests.post', side_effect=[resp_tool, resp_final]):
            eventos = list(ai_service.chat_stream(conv, 'quantos pacientes?', admin))

        tipos = [e['tipo'] for e in eventos]
        assert 'status' in tipos  # consultou a base
        assert any(e['tipo'] == 'token' for e in eventos)  # streamou tokens
        assert eventos[-1]['tipo'] == 'fim'
        # persistência: user -> tool -> assistant
        papeis = [
            m.papel
            for m in ChatMensagem.query.filter_by(id_conversa=conv.id)
            .order_by(ChatMensagem.id)
            .all()
        ]
        assert papeis == ['user', 'tool', 'assistant']
        texto_final = ''.join(e.get('texto', '') for e in eventos if e['tipo'] == 'token')
        assert 'pacientes' in texto_final.lower()


def test_chat_stream_resposta_direta(app, admin, db):
    with app.test_request_context():
        login_user(admin)
        conv = ChatConversa(id_usuario=admin.id, titulo='Nova conversa')
        db.session.add(conv)
        db.session.commit()
        resp = _FakeStream(
            [_chunk(content='Olá! '), _chunk(content='Como ajudar?'), _chunk(done=True)]
        )
        with patch('controllers.ai_service.requests.post', return_value=resp):
            eventos = list(ai_service.chat_stream(conv, 'oi', admin))
        assert [e['tipo'] for e in eventos if e['tipo'] == 'status'] == []  # nenhuma tool
        assert eventos[-1]['tipo'] == 'fim'
        papeis = [m.papel for m in ChatMensagem.query.filter_by(id_conversa=conv.id).all()]
        assert papeis == ['user', 'assistant']


def test_chat_stream_ia_desativada(app, admin, db):
    with app.test_request_context():
        login_user(admin)
        AiConfig.query.first().ativo = False
        db.session.commit()
        conv = ChatConversa(id_usuario=admin.id, titulo='x')
        db.session.add(conv)
        db.session.commit()
        try:
            list(ai_service.chat_stream(conv, 'oi', admin))
            assert False, 'deveria ter levantado IaNaoConfiguradaError'
        except ai_service.IaNaoConfiguradaError:
            pass


# ---------- endpoints do widget ----------


def test_endpoint_mensagem_sse(auth_client, app):
    resp_final = _FakeStream([_chunk(content='resposta de teste'), _chunk(done=True)])
    with patch('controllers.ai_service.requests.post', return_value=resp_final):
        r = auth_client.post('/chat/widget/mensagem', data={'texto': 'oi'})
    assert r.status_code == 200
    assert r.mimetype == 'text/event-stream'
    assert 'data:' in r.data.decode('utf-8')


def test_endpoint_mensagem_vazia(auth_client):
    r = auth_client.post('/chat/widget/mensagem', data={'texto': '  '})
    assert r.status_code == 400


def test_endpoint_mensagem_ia_desativada(auth_client, app):
    auth_client.post('/config/ia/desativar')
    r = auth_client.post('/chat/widget/mensagem', data={'texto': 'oi'})
    assert r.status_code == 503


def test_historico_da_conversa_corrente(auth_client, app, admin):
    with app.app_context():
        conv = ChatConversa(id_usuario=admin.id, titulo='c')
        db.session.add(conv)
        db.session.flush()
        db.session.add(ChatMensagem(id_conversa=conv.id, papel='user', conteudo='pergunta'))
        db.session.add(ChatMensagem(id_conversa=conv.id, papel='assistant', conteudo='resposta'))
        db.session.commit()
    r = auth_client.get('/chat/widget/historico')
    d = json.loads(r.data)
    assert len(d['mensagens']) == 2
    assert d['mensagens'][0]['conteudo'] == 'pergunta'


def test_nova_encerra_conversa_corrente(auth_client, app, admin):
    with app.app_context():
        conv = ChatConversa(id_usuario=admin.id, titulo='c')
        db.session.add(conv)
        db.session.commit()
        conv_id = conv.id
    auth_client.post('/chat/widget/nova')
    with app.app_context():
        assert ChatConversa.query.get(conv_id).removido_em is not None


def test_widget_injetado_quando_ativa(auth_client):
    html = auth_client.get('/home').data.decode('utf-8')
    assert 'cw-launcher' in html  # bolha presente
    assert 'chat-widget.css' in html


def test_widget_some_quando_desativada(auth_client):
    auth_client.post('/config/ia/desativar')
    html = auth_client.get('/home').data.decode('utf-8')
    assert 'cw-launcher' not in html


def test_historico_nao_vaza_entre_usuarios(app, admin, usuario_padrao):
    # admin cria conversa com mensagem
    with app.app_context():
        conv = ChatConversa(id_usuario=admin.id, titulo='secreta')
        db.session.add(conv)
        db.session.flush()
        db.session.add(ChatMensagem(id_conversa=conv.id, papel='user', conteudo='dado do admin'))
        db.session.commit()

    c_padrao = app.test_client()
    c_padrao.post('/login', data={'email': 'teste@teste.com', 'senha': 'senha123'})
    r = c_padrao.get('/chat/widget/historico')
    body = r.data.decode('utf-8')
    assert 'dado do admin' not in body  # padrão não vê a conversa do admin
