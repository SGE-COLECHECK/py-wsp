import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_pause_resume_queue():
    """pause_worker debe pausar y resume_worker debe reanudar la cola."""
    from app.core.queue_manager import QueueManager

    qm = QueueManager()
    qm.paused_workers = set()

    await qm.pause_worker("test-account")
    assert "test-account" in qm.paused_workers

    await qm.resume_worker("test-account")
    assert "test-account" not in qm.paused_workers


@pytest.mark.asyncio
async def test_save_failed():
    """save_failed debe almacenar el item fallido en Redis."""
    mock_redis = AsyncMock()

    with patch("app.core.queue_manager.queue_manager.get_redis", return_value=mock_redis):
        from app.core.queue_manager import QueueManager
        qm = QueueManager()
        data = {"phone": "519111222", "label": "TEST", "message": "Hello"}
        await qm.save_failed("test-account", data, "Connection error", "/tmp/screenshot.png")

        assert mock_redis.lpush.called
        assert mock_redis.ltrim.called


@pytest.mark.asyncio
async def test_save_failed_no_redis():
    """save_failed debe fallar silenciosamente si no hay Redis."""
    with patch("app.core.queue_manager.queue_manager.get_redis", return_value=None):
        from app.core.queue_manager import QueueManager
        qm = QueueManager()
        await qm.save_failed("test-account", {}, "error")  # no debe levantar excepción


@pytest.mark.asyncio
async def test_toggle_pause():
    """toggle_pause debe alternar el estado de pausa."""
    from app.core.queue_manager import QueueManager

    qm = QueueManager()
    qm.paused_workers = set()

    qm.toggle_pause("test-account")
    assert "test-account" in qm.paused_workers

    qm.toggle_pause("test-account")
    assert "test-account" not in qm.paused_workers
