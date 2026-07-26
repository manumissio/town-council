import asyncio


def test_verify_api_key_uses_compare_digest(mocker):
    from api import app_setup

    mocker.patch("api.app_setup.hmac.compare_digest", return_value=True)

    class _Client:
        host = "127.0.0.1"

    class _URL:
        path = "/segment/1"

    req = mocker.MagicMock()
    req.client = _Client()
    req.url = _URL()

    assert asyncio.run(app_setup.verify_api_key(req, x_api_key="bad")) is None
