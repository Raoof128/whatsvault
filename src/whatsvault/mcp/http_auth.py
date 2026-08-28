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
_NOT_FOUND = b'{"error":"not_found"}'

# RFC 9728 / RFC 8414 discovery lives under this prefix. This server authenticates
# with a static bearer token and is not an OAuth authorization server, so the
# truthful answer is 404. Returning the gate's 401 instead was actively harmful:
# clients parse the body as protected-resource metadata, and OpenAI's
# tunnel-client reported "invalid metadata ... missing resource" and held
# readiness degraded.
#
# This is not a hole in the default-deny gate. The middleware answers the prefix
# ITSELF and never forwards it, so no request shape under it can reach the app --
# including one that tries to climb back out with `..`.
_METADATA_PREFIX = "/.well-known/"


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
        if str(scope.get("path", "")).startswith(_METADATA_PREFIX):
            # Answered here, never proxied, and identical with or without a token:
            # the absence of OAuth metadata is not a secret.
            return await self._not_found(send)
        if not self._authorised(scope):
            return await self._reject(send)
        return await self._app(scope, receive, send)

    def _authorised(self, scope) -> bool:
        found = [v for k, v in (scope.get("headers") or ()) if k.lower() == b"authorization"]
        # Ambiguous credentials fail closed rather than first-wins: an injected or
        # proxy-appended second header must never be silently ignored.
        if len(found) != 1:
            return False
        scheme, _, provided = found[0].decode("latin-1").partition(" ")
        if scheme.lower() != "bearer":
            return False
        return auth.require_token(provided.strip(), self._token)

    async def _reject(self, send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                # RFC 6750: tell the client how to authenticate, without echoing input.
                "headers": [
                    (b"www-authenticate", b'Bearer realm="whatsvault-mcp"'),
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_UNAUTHORISED)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _UNAUTHORISED})

    @staticmethod
    async def _not_found(send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_NOT_FOUND)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _NOT_FOUND})
