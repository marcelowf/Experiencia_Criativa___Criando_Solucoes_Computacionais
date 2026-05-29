"""Login federado via Google (OAuth2 / OpenID Connect).

O Google é um método ALTERNATIVO de entrar: só funciona para usuários que já
existem na base (provisionados por um admin). O match é feito pelo e-mail
verificado retornado pelo Google.

Tolerante à ausência do Authlib: se a lib não estiver instalada ou as
credenciais não estiverem configuradas, o recurso fica simplesmente desligado
(o botão "Entrar com Google" não aparece).
"""

try:
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth()
    _AUTHLIB_DISPONIVEL = True
except ImportError:  # authlib ainda não instalado (ex.: antes do rebuild)
    oauth = None
    _AUTHLIB_DISPONIVEL = False


GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'


def init_oauth(app) -> bool:
    """Inicializa o OAuth e registra o Google se houver credenciais.

    Retorna True se o login Google está habilitado.
    """
    if not _AUTHLIB_DISPONIVEL:
        return False

    client_id = app.config.get('GOOGLE_CLIENT_ID')
    client_secret = app.config.get('GOOGLE_CLIENT_SECRET')
    if not client_id or not client_secret:
        return False

    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={'scope': 'openid email profile'},
    )
    return True
