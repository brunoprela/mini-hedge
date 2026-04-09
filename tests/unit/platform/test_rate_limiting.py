"""Unit tests for rate limiting middleware."""

from app.middleware.rate_limit import _key_func, build_limiter


class TestKeyFunc:
    def test_api_key_header(self):
        from starlette.requests import Request

        scope = {"type": "http", "headers": [(b"x-api-key", b"test-key-123")]}
        request = Request(scope)
        assert _key_func(request) == "apikey:test-key-123"

    def test_bearer_token(self):
        from starlette.requests import Request

        token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
        scope = {"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}
        request = Request(scope)
        key = _key_func(request)
        assert key.startswith("bearer:")
        assert len(key) > len("bearer:")

    def test_falls_back_to_ip(self):
        from starlette.requests import Request

        scope = {
            "type": "http",
            "headers": [],
            "client": ("192.168.1.1", 8080),
        }
        request = Request(scope)
        assert _key_func(request) == "ip:192.168.1.1"


class TestBuildLimiter:
    def test_in_memory_limiter(self):
        limiter = build_limiter()
        assert limiter is not None

    def test_redis_limiter(self):
        limiter = build_limiter("redis://localhost:6379/0")
        assert limiter is not None
