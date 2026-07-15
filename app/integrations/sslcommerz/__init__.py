"""SSLCommerz payment gateway integration.

`get_sslcommerz_client()` is the only thing the rest of the app should import —
it returns the mock or real client based on `settings.SSLCOMMERZ_MOCK_MODE`,
so payment business logic never depends on which one is active.
"""
from app.core.config import settings
from app.integrations.sslcommerz.client import SSLCommerzClient
from app.integrations.sslcommerz.mock_client import MockSSLCommerzClient

_client: SSLCommerzClient | None = None


def get_sslcommerz_client() -> SSLCommerzClient:
    global _client
    if _client is None:
        if settings.SSLCOMMERZ_MOCK_MODE:
            _client = MockSSLCommerzClient()
        else:
            raise NotImplementedError(
                "SSLCOMMERZ_MOCK_MODE is False but no real SSLCommerz client is "
                "implemented yet. Implement app/integrations/sslcommerz/real_client.py "
                "against the SSLCommerzClient interface and wire it in here."
            )
    return _client
