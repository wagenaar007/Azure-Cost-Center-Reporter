from azure.identity import ClientSecretCredential
from src import config

_credential: ClientSecretCredential | None = None


def _get_credential() -> ClientSecretCredential:
    global _credential
    if _credential is None:
        _credential = ClientSecretCredential(
            tenant_id=config.TENANT_ID,
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
        )
    return _credential


def get_arm_token() -> str:
    token = _get_credential().get_token("https://management.azure.com/.default")
    return token.token


def get_graph_token() -> str:
    token = _get_credential().get_token("https://graph.microsoft.com/.default")
    return token.token
