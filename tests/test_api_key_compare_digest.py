import asyncio
import pytest


def test_verify_api_key_uses_compare_digest(mocker):
    from api import main

    spy = mocker.patch("api.main.hmac.compare_digest", return_value=False)

    class _Client:
        host = "127.0.0.1"

    class _URL:
        path = "/segment/1"

    req = mocker.MagicMock()
    req.client = _Client()
    req.url = _URL()

    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.verify_api_key(req, x_api_key="bad"))

    assert exc.value.status_code == 401
    spy.assert_called_once()
