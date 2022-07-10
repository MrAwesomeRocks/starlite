from typing import Any, Callable, Collection, Dict, List, Tuple

from starlette.types import ASGIApp, Scope

from starlite.routes import BaseRoute


class RouteMap:
    def __init__(self) -> None:
        pass

    def add_routes(self, routes: Collection[BaseRoute]) -> None:
        """
        Add routes to the map
        """

    def parse_scope_to_route(
        self, scope: Scope, parse_path_params: Callable[[List[Dict[str, Any]], List[str]], Dict[str, Any]]
    ) -> Tuple[Dict[str, ASGIApp], bool]:
        """
        Given a scope object, retrieve the asgi_handlers and is_asgi values from correct trie node.

        Raises NotFoundException if no correlating node is found for the scope's path
        """

    def add_static_path(self, path: str) -> None:
        """
        Adds a new static path by path name
        """

    def is_static_path(self, path: str) -> bool:
        """
        Checks if a given path refers to a static path
        """

    def remove_static_path(self, path: str) -> bool:
        """
        Removes a path from the static path set
        """

    def add_plain_route(self, path: str) -> None:
        """
        Adds a new plain route by path name
        """

    def is_plain_route(self, path: str) -> bool:
        """
        Checks if a given path refers to a plain route
        """

    def remove_plain_route(self, path: str) -> bool:
        """
        Removes a path from the plain route set
        """
