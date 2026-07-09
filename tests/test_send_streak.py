import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_store_response_resets_send_streak():
    """store_response() debe eliminar la clave send_streak del teléfono."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.hget.return_value = None

    with patch("app.core.ycloud_sender.queue_manager.get_redis", return_value=mock_redis):
        from app.core.ycloud_sender import store_response
        await store_response("519111222", "test-account")

        nphone = "519111222"
        mock_redis.set.assert_called_with(f"response:{nphone}", pytest.approx(1234567890, abs=1e9), ex=86400)
        mock_redis.delete.assert_called_with(f"send_streak:{nphone}")


@pytest.mark.asyncio
async def test_store_response_auto_reactivates_blocked():
    """store_response() debe auto-reactivar si el teléfono estaba bloqueado."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.hget.return_value = "blocked"

    with patch("app.core.ycloud_sender.queue_manager.get_redis", return_value=mock_redis):
        from app.core.ycloud_sender import store_response
        await store_response("519111222", "test-account")

        nphone = "519111222"
        mock_redis.hset.assert_called_with(f"phonebook:state:test-account", nphone, "active")


@pytest.mark.asyncio
async def test_store_response_auto_reactivates_inactive():
    """store_response() debe auto-reactivar si el teléfono estaba inactivo."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.hget.return_value = "inactive"

    with patch("app.core.ycloud_sender.queue_manager.get_redis", return_value=mock_redis):
        from app.core.ycloud_sender import store_response
        await store_response("519111222", "test-account")

        nphone = "519111222"
        mock_redis.hset.assert_called_with(f"phonebook:state:test-account", nphone, "active")


@pytest.mark.asyncio
async def test_auto_block_stale_blocks_streak_3():
    """auto_block_stale() debe bloquear teléfonos con send_streak >= 3."""
    mock_redis = AsyncMock()
    mock_redis.smembers.return_value = {"519111111", "519222222", "519333333"}
    mock_redis.hgetall.return_value = {}
    mock_redis.hget.return_value = "active"

    async def mock_get(key):
        data = {
            "send_streak:519111111": None,
            "send_streak:519222222": "3",
            "send_streak:519333333": "2",
        }
        return data.get(key)

    mock_redis.get = AsyncMock(side_effect=mock_get)

    with patch("app.core.ycloud_sender.queue_manager.get_redis", return_value=mock_redis):
        with patch("app.core.ycloud_sender.config_manager.get_client_config") as mock_cfg:
            mock_cfg.return_value = {"auto_block_enabled": True, "auto_block_message": "Warning!"}
            with patch("app.core.ycloud_sender.queue_manager.enqueue", AsyncMock()) as mock_enqueue:
                from app.core.ycloud_sender import auto_block_stale
                total = await auto_block_stale("test-account")

                assert total == 2
                mock_redis.hset.assert_any_call("phonebook:state:test-account", "519222222", "blocked")
                mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_auto_block_stale_warns_streak_2():
    """auto_block_stale() debe encolar warning para teléfonos con send_streak == 2."""
    mock_redis = AsyncMock()
    mock_redis.smembers.return_value = {"519444444"}
    mock_redis.hgetall.return_value = {}
    mock_redis.hget.return_value = "active"
    mock_redis.get.return_value = "2"

    with patch("app.core.ycloud_sender.queue_manager.get_redis", return_value=mock_redis):
        with patch("app.core.ycloud_sender.config_manager.get_client_config") as mock_cfg:
            mock_cfg.return_value = {"auto_block_enabled": True, "auto_block_message": "Warning!"}
            with patch("app.core.ycloud_sender.queue_manager.enqueue", AsyncMock()) as mock_enqueue:
                from app.core.ycloud_sender import auto_block_stale
                total = await auto_block_stale("test-account")

                assert total == 1
                mock_enqueue.assert_called_once()
                args = mock_enqueue.call_args
                assert args[0][1].get("is_warning") is True
