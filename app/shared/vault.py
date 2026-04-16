"""Vault integration — load secrets from HashiCorp Vault KV v2 engine.

At startup, if ``VAULT_ADDR`` is set, secrets are read from Vault and
injected into the settings object.  If Vault is unreachable, the app
falls back to environment variables / .env file (backwards compatible).

Vault dev mode (``hashicorp/vault`` Docker image with ``VAULT_DEV_ROOT_TOKEN_ID``)
runs as a single container with in-memory backend, no unsealing required.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


def load_vault_secrets(
    vault_addr: str,
    vault_token: str,
    mount_point: str = "secret",
    path: str = "minihedge",
) -> dict[str, Any]:
    """Read secrets from Vault KV v2 and return as a flat dict.

    Returns an empty dict if Vault is unreachable (allows graceful fallback).
    """
    try:
        import hvac  # type: ignore[import-untyped]

        client = hvac.Client(url=vault_addr, token=vault_token)

        if not client.is_authenticated():
            logger.warning("vault_auth_failed", vault_addr=vault_addr)
            return {}

        response = client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point=mount_point,
        )

        secrets: dict[str, Any] = response["data"]["data"]

        logger.info(
            "vault_secrets_loaded",
            vault_addr=vault_addr,
            path=f"{mount_point}/{path}",
            keys=list(secrets.keys()),
        )
        return secrets

    except ImportError:
        logger.debug("vault_hvac_not_installed")
        return {}
    except hvac.exceptions.InvalidPath:
        # 404 is normal in dev when secrets aren't seeded yet.
        logger.info("vault_path_not_found", vault_addr=vault_addr, path=f"{mount_point}/{path}")
        return {}
    except Exception:
        logger.warning("vault_unreachable", vault_addr=vault_addr, exc_info=True)
        return {}
