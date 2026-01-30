"""External API Gateway Module."""

from .external_gateway import (
    ExternalAPIGateway,
    NaverNewsClient,
    DuckDuckGoClient,
    get_external_gateway,
)

__all__ = [
    "ExternalAPIGateway",
    "NaverNewsClient",
    "DuckDuckGoClient",
    "get_external_gateway",
]
