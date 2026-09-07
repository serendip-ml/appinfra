# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""
Tests for app/builder/configurer/server.py.

ServerScope is the FastAPI ServerBuilder bound to an AppBuilder. The
AppBuilder builds the server at build() and registers a ServerPlugin,
which adds the ``serve`` tool.
"""

from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest

from appinfra.app.builder.app import AppBuilder
from appinfra.app.builder.configurer.server import ServerFields, ServerScope
from appinfra.app.fastapi.builder.server import ServerBuilder
from appinfra.app.fastapi.config.api import ApiConfig

ADAPTER = "appinfra.app.fastapi.builder.server.FastAPIAdapter"


def _health() -> dict[str, str]:
    return {"status": "ok"}


# =============================================================================
# The scope is the standalone builder
# =============================================================================


@pytest.mark.unit
class TestServerScopeIsABuilder:
    """ServerScope inherits ServerBuilder and is memoized per AppBuilder."""

    def test_is_server_builder(self):
        """Every ServerBuilder method and facet is available through inheritance."""
        assert isinstance(AppBuilder("test").server, ServerBuilder)
        assert isinstance(AppBuilder("test").server, ServerScope)

    def test_same_instance_per_builder(self):
        """State lives on the scope, so the builder hands out one instance."""
        builder = AppBuilder("test")

        assert builder.server is builder.server

    def test_name_follows_app(self):
        """The server is named after the app."""
        assert AppBuilder("myapp").server._name == "myapp"

    def test_build_raises_pointing_at_done(self):
        """The AppBuilder builds the server, not the scope."""
        with pytest.raises(TypeError, match=r"done\(\)"):
            AppBuilder("test").server.build()

    def test_done_returns_builder(self):
        """done() closes the block."""
        builder = AppBuilder("test")

        assert builder.server.done() is builder

    def test_facets_return_to_scope(self):
        """routes, uvicorn and subprocess close back onto the scope."""
        scope = AppBuilder("test").server

        assert scope.routes.done() is scope
        assert scope.uvicorn.done() is scope
        assert scope.subprocess.done() is scope


# =============================================================================
# Chained configuration
# =============================================================================


@pytest.mark.unit
class TestChainedConfiguration:
    """Inherited methods write ServerBuilder state on the scope."""

    def test_direct_methods_set_state(self):
        """Host, port and title go to the builder fields."""
        builder = (
            AppBuilder("test")
            .server.with_port(8080)
            .with_host("127.0.0.1")
            .with_title("T")
            .done()
        )

        scope = builder._server_scope
        assert (scope._port, scope._host, scope._title) == (8080, "127.0.0.1", "T")

    def test_routes_reach_scope(self):
        """A route added through the facet lands on the scope."""
        builder = (
            AppBuilder("test")
            .server.routes.with_route("/health", _health)
            .done()
            .done()
        )

        routes = builder._server_scope._routes
        assert [r.path for r in routes] == ["/health"]


# =============================================================================
# Keyword form
# =============================================================================


@pytest.mark.unit
class TestKeywordForm:
    """Calling the block sets fields and returns the AppBuilder."""

    def test_call_sets_fields_and_returns_builder(self):
        """Each key maps onto the builder's direct setter."""
        builder = AppBuilder("test")

        result = builder.server(
            host="127.0.0.1",
            port=9000,
            title="T",
            description="D",
            version="2.0",
            timeout=5.0,
        )

        assert result is builder
        scope = builder._server_scope
        assert scope._host == "127.0.0.1"
        assert scope._port == 9000
        assert scope._title == "T"
        assert scope._description == "D"
        assert scope._version == "2.0"
        assert scope._response_timeout == 5.0

    def test_uvicorn_mapping_routes_to_uvicorn_block(self):
        """The uvicorn key takes UvicornFields."""
        builder = AppBuilder("test").server(uvicorn={"workers": 4, "access_log": True})

        uvicorn = builder._server_scope._uvicorn_config
        assert uvicorn.workers == 4
        assert uvicorn.access_log is True

    def test_fields_map_onto_api_config(self):
        """ServerFields keys are ApiConfig fields; timeout is response_timeout."""
        api = {f.name for f in fields(ApiConfig)}

        assert set(ServerFields.__annotations__) - {"timeout"} <= api
        assert "response_timeout" in api


# =============================================================================
# build() registers the server
# =============================================================================


@pytest.mark.unit
class TestBuildRegistersServer:
    """Declaring .server adds the serve tool through ServerPlugin at build()."""

    def test_build_registers_serve_tool(self):
        """The built app has a serve tool for the declared server."""
        with patch(ADAPTER) as adapter:
            adapter.return_value = MagicMock()
            app = AppBuilder("test").server.with_port(8080).done().build()

        assert app.registry.is_registered("serve")

    def test_build_without_server_registers_nothing(self):
        """No .server, no serve tool."""
        app = AppBuilder("test").build()

        assert not app.registry.is_registered("serve")

    def test_built_server_carries_scope_config(self):
        """The Server handed to the plugin has the scope's port."""
        builder = AppBuilder("test").server(port=8123)

        with patch(ADAPTER) as adapter:
            adapter.return_value = MagicMock()
            builder.build()

        (plugin,) = builder._plugins._plugins.values()
        assert plugin._server.config.port == 8123
