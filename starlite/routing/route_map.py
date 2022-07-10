from collections import defaultdict
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Dict,
    List,
    Optional,
    Tuple,
    cast,
)

from starlette.types import ASGIApp, Scope

from starlite.enums import ScopeType
from starlite.exceptions import (
    ImproperlyConfiguredException,
    MethodNotAllowedException,
    NotFoundException,
)
from starlite.routes import ASGIRoute, BaseRoute, HTTPRoute, WebSocketRoute

if TYPE_CHECKING:
    from starlite import Starlite


@dataclass
class _RouteMapLeafData:
    path_parameters: List[Dict[str, Any]] = field(default_factory=list)
    asgi_handlers: Dict[str, ASGIApp] = field(default_factory=dict)
    is_asgi: bool = False
    static_path: str = ""


@dataclass
class _RouteMapTree:
    children: Dict[str, "_RouteMapTree"] = field(default_factory=lambda: defaultdict(_RouteMapTree))
    data: Optional[_RouteMapLeafData] = None


class RouteMap:
    def __init__(self) -> None:
        self._static_paths: set[str] = set()
        self._plain_routes: dict[str, _RouteMapTree] = defaultdict(_RouteMapTree)
        self._tree = _RouteMapTree()

    def add_routes(self, routes: Collection[BaseRoute], app: "Starlite") -> None:
        """
        Add routes to the map
        """
        for route in routes:
            self._add_node(route, app)

    def _add_node(self, route: BaseRoute, app: "Starlite") -> _RouteMapTree:
        """
        Adds a new route path (e.g. '/foo/bar/{param:int}') into the route_map tree.

        Inserts non-parameter paths ('plain routes') off the tree's root node.
        For paths containing parameters, splits the path on '/' and nests each path
        segment under the previous segment's node (see prefix tree / trie).
        """
        path = route.path
        cur_node: _RouteMapTree

        if route.path_parameters or path in self._static_paths:
            # Route is a "true" route, needs routing

            # Replace path params with "*"
            for param_def in route.path_parameters:
                path = path.replace("{" + param_def["full"] + "}", "*")

            # Iterate down trie with components
            cur_node = self._tree
            components = self._get_path_components(path)
            for component in components:
                cur_node = cur_node.children[component]
        else:
            # Plain path, no routing
            cur_node = self._plain_routes[path]

        self._configure_node(route, cur_node, app)
        return cur_node

    def _configure_node(self, route: BaseRoute, node: _RouteMapTree, app: "Starlite") -> None:
        """
        Set required attributes and route handlers on route_map tree node.
        """
        if not node.data:
            node.data = _RouteMapLeafData()

        data = node.data

        # Check and set path parameters
        if data.path_parameters and data.path_parameters != route.path_parameters:
            raise ImproperlyConfiguredException("Should not use routes with conflicting path parameters")
        data.path_parameters = route.path_parameters

        # Set static path attrs
        if route.path in self._static_paths:
            data.is_asgi = True
            data.static_path = route.path

        # Set ASGI handlers
        if isinstance(route, HTTPRoute):
            for method, (handler, _) in route.route_handler_map.items():
                data.asgi_handlers[method] = app.build_route_middleware_stack(route, handler)
        elif isinstance(route, WebSocketRoute):
            data.asgi_handlers[ScopeType.WEBSOCKET] = app.build_route_middleware_stack(route, route.route_handler)
        elif isinstance(route, ASGIRoute):
            data.asgi_handlers[ScopeType.ASGI] = app.build_route_middleware_stack(route, route.route_handler)
            data.is_asgi = True
        else:
            raise ImproperlyConfiguredException(f"Unknown route type {type(route)})")

    def resolve_route(
        self, scope: Scope, parse_path_params: Callable[[List[Dict[str, Any]], List[str]], Dict[str, Any]]
    ) -> ASGIApp:
        """
        Given a scope object, retrieve the ASGIApp values from correct trie node.

        Raises NotFoundException if no correlating node is found for the scope's path
        """
        try:
            asgi_handlers, is_asgi = self._parse_scope_to_route(scope, parse_path_params)
            return self._resolve_asgi_app(scope, asgi_handlers, is_asgi)
        except KeyError as e:
            raise NotFoundException() from e

    def _parse_scope_to_route(
        self, scope: Scope, parse_path_params: Callable[[List[Dict[str, Any]], List[str]], Dict[str, Any]]
    ) -> Tuple[Dict[str, ASGIApp], bool]:
        """
        Given a scope object, retrieve the asgi_handlers and is_asgi values from correct trie node.

        Raises NotFoundException if no correlating node is found for the scope's path
        """
        path = cast(str, scope["path"]).strip()

        # Path normalization
        if path != "/" and path.endswith("/"):
            path = path[:-1]

        # Get node and path params
        cur_node: _RouteMapTree
        path_params: list[str]

        if path in self._plain_routes:
            cur_node = self._plain_routes[path]
            path_params = []
        else:
            cur_node, path_params = self._traverse_route_map(path, scope)

        # Verify route data exits
        if not cur_node.data:
            raise NotFoundException()
        data = cur_node.data

        # Get path params
        scope["path_params"] = parse_path_params(data.path_parameters, path_params)

        return data.asgi_handlers, data.is_asgi

    def _traverse_route_map(self, path: str, scope: Scope) -> tuple[_RouteMapTree, list[str]]:
        """
        Traverses the application route mapping and retrieves the correct node for the request url.

        Raises NotFoundException if no correlating node is found
        """
        path_params: list[str] = []
        cur_node = self._tree

        # TODO: What if we try to match the requested path `/*` against a `@get("/{s:str}")`??
        for component in self._get_path_components(path):
            # Try to decend down the trie
            if component in cur_node.children:
                cur_node = cur_node.children[component]
                continue

            # Can't decend, maybe a path parameter?
            if "*" in cur_node.children:
                path_params.append(component)
                cur_node = cur_node.children["*"]
                continue

            # Not a path parameter, maybe a static path?
            if cur_node.data and (static_path := cur_node.data.static_path):
                if static_path != "/":
                    scope["path"] = scope["path"].replace(static_path, "")
                # TODO: break?
                continue

            # No match
            raise NotFoundException()

        # Return matched node and params
        return cur_node, path_params

    @staticmethod
    def _resolve_asgi_app(scope: Scope, asgi_handlers: Dict[str, ASGIApp], is_asgi: bool) -> ASGIApp:
        """
        Given a scope, retrieves the correct ASGI App for the route
        """
        if is_asgi:
            return asgi_handlers[ScopeType.ASGI]
        if scope["type"] == ScopeType.HTTP:
            if scope["method"] not in asgi_handlers:
                raise MethodNotAllowedException()
            return asgi_handlers[scope["method"]]
        return asgi_handlers[ScopeType.WEBSOCKET]

    @staticmethod
    def _get_path_components(path: str) -> list[str]:
        """Get the routing components of a path."""
        return ["/"] + [comp for comp in path.split("/") if comp]

    def add_static_path(self, path: str) -> None:
        """
        Adds a new static path by path name
        """
        self._static_paths.add(path)

    def is_static_path(self, path: str) -> bool:
        """
        Checks if a given path refers to a static path
        """
        return path in self._static_paths

    def remove_static_path(self, path: str) -> bool:
        """
        Removes a path from the static path set
        """
        try:
            self._static_paths.remove(path)
            return True
        except KeyError:
            return False
