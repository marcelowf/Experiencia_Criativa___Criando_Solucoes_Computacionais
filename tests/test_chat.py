"""Testes do chat de IA: config, fluxo de tool calling (Ollama mockado), privacidade."""

from unittest.mock import patch, MagicMock

from models.models import db, AiConfig, ChatConversa, ChatMensagem


def _fake_resp(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


def _ativar_ia():
    db.session.add(AiConfig(base_url='http://ollama:11434', modelo='qwen2.5:7b', ativo=True))
    db.session.commit()


# ---------- config ----------

def test_config_ia_requer_admin(auth_client_padrao):
    r = auth_client_padrao.get('/config/ia/')
    assert r.status_code == 403


def test_salvar_config_ia(auth_client, app):
    r = auth_client.post('/config/ia/', data={
        'base_url': 'http://ollama:11434', 'modelo': 'qwen2.5:7b',
        'temperatura': '0.2', 'max_iteracoes': '4',
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        c = AiConfig.query.first()
        assert c.modelo == 'qwen2.5:7b'
        assert c.ativo is True
        assert abs(c.temperatura - 0.2) < 1e-6


# ---------- fluxo de chat ----------

def test_chat_sem_config_responde_503(auth_client, app):
    auth_client.post('/chat/nova')
    with app.app_context():
        conv_id = ChatConversa.query.first().id
    r = auth_client.post(f'/chat/{conv_id}/mensagem', data={'texto': 'oi'})
    assert r.status_code == 503
    assert 'erro' in r.get_json()


def test_chat_fluxo_tool_calling(auth_client, app, admin):
    auth_client.post('/chat/nova')
    with app.app_context():
        _ativar_ia()
        conv_id = ChatConversa.query.first().id

    respostas = [
        # 1ª: a IA pede uma tool
        _fake_resp({'message': {'role': 'assistant', 'content': '',
                                'tool_calls': [{'function': {'name': 'buscar_pacientes',
                                                             'arguments': {}}}]}}),
        # 2ª: resposta final
        _fake_resp({'message': {'role': 'assistant',
                                'content': 'Você não tem pacientes cadastrados.'}}),
    ]
    with patch('controllers.ai_service.requests.post', side_effect=respostas):
        r = auth_client.post(f'/chat/{conv_id}/mensagem',
                             data={'texto': 'quantos pacientes eu tenho?'})

    assert r.status_code == 200
    assert 'pacientes' in r.get_json()['resposta'].lower()
    with app.app_context():
        papeis = [m.papel for m in ChatMensagem.query
                  .filter_by(id_conversa=conv_id)
                  .order_by(ChatMensagem.id).all()]
        # user -> tool (buscar_pacientes) -> assistant
        assert papeis == ['user', 'tool', 'assistant']


def test_chat_resposta_direta_sem_tool(auth_client, app):
    auth_client.post('/chat/nova')
    with app.app_context():
        _ativar_ia()
        conv_id = ChatConversa.query.first().id

    resp = _fake_resp({'message': {'role': 'assistant', 'content': 'Olá! Como posso ajudar?'}})
    with patch('controllers.ai_service.requests.post', return_value=resp):
        r = auth_client.post(f'/chat/{conv_id}/mensagem', data={'texto': 'oi'})

    assert r.status_code == 200
    assert 'ajudar' in r.get_json()['resposta'].lower()
    with app.app_context():
        papeis = [m.papel for m in ChatMensagem.query.filter_by(id_conversa=conv_id).all()]
        assert papeis == ['user', 'assistant']


def test_chat_titulo_vem_da_primeira_pergunta(auth_client, app):
    auth_client.post('/chat/nova')
    with app.app_context():
        conv_id = ChatConversa.query.first().id
        _ativar_ia()

    resp = _fake_resp({'message': {'role': 'assistant', 'content': 'resposta'}})
    with patch('controllers.ai_service.requests.post', return_value=resp):
        auth_client.post(f'/chat/{conv_id}/mensagem',
                         data={'texto': 'minha primeira pergunta sobre triagem'})
    with app.app_context():
        c = ChatConversa.query.get(conv_id)
        assert c.titulo.startswith('minha primeira pergunta')


def test_chat_ollama_fora_do_ar_503(auth_client, app):
    import requests as _rq
    auth_client.post('/chat/nova')
    with app.app_context():
        _ativar_ia()
        conv_id = ChatConversa.query.first().id

    with patch('controllers.ai_service.requests.post',
               side_effect=_rq.ConnectionError('connection refused')):
        r = auth_client.post(f'/chat/{conv_id}/mensagem', data={'texto': 'oi'})
    assert r.status_code == 503


# ---------- privacidade ----------

def test_conversa_e_privada(app, admin, usuario_padrao):
    c_admin = app.test_client()
    c_admin.post('/login', data={'email': 'admin@admin.com', 'senha': 'admin123'})
    c_admin.post('/chat/nova')
    with app.app_context():
        conv_id = ChatConversa.query.first().id

    c_padrao = app.test_client()
    c_padrao.post('/login', data={'email': 'teste@teste.com', 'senha': 'senha123'})
    r = c_padrao.get(f'/chat/{conv_id}')
    assert r.status_code == 403
    r = c_padrao.post(f'/chat/{conv_id}/mensagem', data={'texto': 'invadir'})
    assert r.status_code == 403


def test_remover_conversa(auth_client, app):
    auth_client.post('/chat/nova')
    with app.app_context():
        conv_id = ChatConversa.query.first().id
    auth_client.post(f'/chat/{conv_id}/remover')
    with app.app_context():
        c = ChatConversa.query.get(conv_id)
        assert c.removido_em is not None
