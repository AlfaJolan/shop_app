import secrets

def make_pkey(length: int = 32) -> str:
    # Безопасный URL-safe токен
    return secrets.token_urlsafe(length)
