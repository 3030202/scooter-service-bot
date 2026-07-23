import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app.db.models import ServiceCatalogItem, User, UserRole
from app.handlers.client import handle_client_webapp_data
from app.services.health import api_catalog_view, webapp_client_view, webapp_master_view


@pytest.mark.asyncio
async def test_webapp_views():
    app = web.Application()
    app.router.add_get("/webapp/client", webapp_client_view)
    app.router.add_get("/webapp/master", webapp_master_view)

    client = TestClient(TestServer(app))
    await client.start_server()

    try:
        resp_client = await client.get("/webapp/client")
        assert resp_client.status == 200
        text_client = await resp_client.text()
        assert "Диагностика поломки" in text_client

        resp_master = await client.get("/webapp/master")
        assert resp_master.status == 200
        text_master = await resp_master.text()
        assert "Смета мастера" in text_master
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_catalog_view():
    app = web.Application()
    app.router.add_get("/api/catalog", api_catalog_view)

    mock_item = ServiceCatalogItem(
        id=1, code="test", title="Test Item", category="battery", base_price=1000, default_eta="1 день"
    )
    with patch("app.services.health.seed_catalog", new_callable=AsyncMock), \
         patch("app.services.health.list_catalog", new_callable=AsyncMock) as mock_list, \
         patch("app.services.health.AsyncSessionLocal") as mock_session_local:
        
        mock_list.return_value = [mock_item]
        mock_session_ctx = AsyncMock()
        mock_session_local.return_value = mock_session_ctx

        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            resp = await client.get("/api/catalog")
            assert resp.status == 200
            data = await resp.json()
            assert len(data) == 1
            assert data[0]["title"] == "Test Item"
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_client_webapp_data_handler():
    mock_message = AsyncMock()
    mock_message.from_user = MagicMock(id=1001, first_name="ClientTest", username="client_test")
    mock_message.web_app_data = MagicMock()
    mock_message.web_app_data.data = json.dumps({
        "action": "client_webapp_select",
        "node": "Батарея / BMS",
        "details": "Не заряжается выше 80%"
    })
    mock_state = AsyncMock()
    mock_user = User(id=10, telegram_id=1001, full_name="ClientTest")

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch("app.handlers.client.get_or_create_user", new_callable=AsyncMock) as mock_get_user, \
         patch("app.handlers.client.AsyncSessionLocal") as mock_session_local:
        
        mock_get_user.return_value = mock_user
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        mock_session_local.return_value = mock_session_ctx

        await handle_client_webapp_data(mock_message, mock_state)

        mock_message.answer.assert_called_once()
        assert "Батарея / BMS" in mock_message.answer.call_args[0][0]
        mock_state.set_state.assert_called_once()
