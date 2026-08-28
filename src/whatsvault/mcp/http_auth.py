"""HTTP-transport bearer auth for the Streamable-HTTP MCP surface (ledger #18, #19).

Why this exists as ASGI middleware rather than a tool argument: a `bearer`
parameter on a tool handler is published in that tool's JSON schema, so the
server would be advertising the secret as something the *model* should supply.
The token belongs on the transport, checked before any tool is reached.

Default-deny: every path is protected. 127.0.0.1 is not an auth boundary (any
local process running as the user can connect), so binding loopback does not
substitute for this check.
"""
from . import auth

_UNAUTHORISED = b'{"error":"unauthorized"}'


class BearerAuthMiddleware:
    """Rejects any HTTP request not carrying `Authorization: Bearer <token>`."""

    def __init__(self, app, token: str):
        if not token:
            raise ValueError("refusing to serve without a token; see mcp.auth.provision_token")
        self._app = app
        self._token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self._app(scope, receive, send)
        if scope["type"] != "http":
            # No websocket surface is offered; fail closed rather than pass through.
            raise RuntimeError(f"unsupported ASGI scope {scope['type']!r}")
        if not self._authorised(scope):
            return await self._reject(send)
        return await self._app(scope, receive, send)

    def _authorised(self, scope) -> bool:
        for name, value in scope.get("headers") or ():
            if name.lower() != b"authorization":
                continue
            scheme, _, provided = value.decode("latin-1").partition(" ")
            if scheme.lower() != "bearer":
                return False
            return auth.require_token(provided.strip(), self._token)
        return False

    async def _reject(self, send) -> None:
        await send({
            "type": "http.response.start",
            "status": 401,
            # RFC 6750: tell the client how to authenticate, without echoing input.
            "headers": [(b"www-authenticate", b'Bearer realm="whatsvault-mcp"'),
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(_UNAUTHORISED)).encode())],
        })
        await send({"type": "http.response.body", "body": _UNAUTHORISED})
