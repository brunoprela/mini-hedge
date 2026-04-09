"""Unit tests for Vault secret loading."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.shared.vault import load_vault_secrets


class TestLoadVaultSecrets:
    def test_returns_secrets_on_success(self) -> None:
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "jwt_secret": "vault-managed-secret",
                    "database_url": "postgresql+asyncpg://...",
                }
            }
        }

        with patch.dict("sys.modules", {"hvac": MagicMock()}) as _:
            import hvac as mock_hvac_mod

            mock_hvac_mod.Client = MagicMock(return_value=mock_client)

            with patch("hvac.Client", return_value=mock_client):
                secrets = load_vault_secrets(
                    vault_addr="http://localhost:8200",
                    vault_token="test-token",
                )

            assert secrets["jwt_secret"] == "vault-managed-secret"
            assert secrets["database_url"] == "postgresql+asyncpg://..."

    def test_returns_empty_on_auth_failure(self) -> None:
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False

        mock_hvac = MagicMock()
        mock_hvac.Client.return_value = mock_client

        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            secrets = load_vault_secrets(
                vault_addr="http://localhost:8200",
                vault_token="bad-token",
            )

        assert secrets == {}

    def test_returns_empty_on_connection_error(self) -> None:
        mock_hvac = MagicMock()
        mock_hvac.Client.side_effect = ConnectionError("unreachable")

        with patch.dict("sys.modules", {"hvac": mock_hvac}):
            secrets = load_vault_secrets(
                vault_addr="http://unreachable:8200",
                vault_token="token",
            )

        assert secrets == {}

    def test_returns_empty_on_empty_addr(self) -> None:
        # Empty addr still gracefully returns empty dict (catches exception)
        secrets = load_vault_secrets(vault_addr="", vault_token="")
        assert secrets == {}
