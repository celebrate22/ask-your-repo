"""Small authentication module used by the retrieval evaluation."""


def is_token_expired(token, current_time):
    """Return whether the token's expiration time has passed."""
    return current_time >= token["expires_at"]


def require_login(request):
    """Require an Authorization header and return its token value."""
    token = request.headers.get("Authorization")
    if not token:
        raise PermissionError("login required")
    return token
