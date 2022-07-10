from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .route_map import RouteMap
else:
    try:
        # Native extension
        from ._route_map import RouteMap
    except ImportError:
        # Pure-python
        from .route_map import RouteMap

__all__ = ["RouteMap"]
