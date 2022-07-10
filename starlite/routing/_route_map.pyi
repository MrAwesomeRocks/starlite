from typing import Any, Callable, Collection, Dict, List, Tuple

from starlette.types import ASGIApp as ASGIApp
from starlette.types import Scope as Scope

from starlite.routes import BaseRoute as BaseRoute

class RouteMap:
    def __init__(self) -> None: ...
    def add_routes(self, routes: Collection[BaseRoute]) -> None: ...
    def parse_scope_to_route(
        self, scope: Scope, parse_path_params: Callable[[List[Dict[str, Any]], List[str]], Dict[str, Any]]
    ) -> Tuple[Dict[str, ASGIApp], bool]: ...
    def add_static_path(self, path: str) -> None: ...
    def is_static_path(self, path: str) -> bool: ...
    def remove_static_path(self, path: str) -> bool: ...
    def add_plain_route(self, path: str) -> None: ...
    def is_plain_route(self, path: str) -> bool: ...
    def remove_plain_route(self, path: str) -> bool: ...
