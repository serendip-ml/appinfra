"""Tests for LogConfigRegistry - singleton holder registry."""

import pytest

from appinfra.log.config import LogConfig
from appinfra.log.config_holder import LogConfigHolder
from appinfra.log.config_registry import LogConfigRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset singleton before and after each test."""
    LogConfigRegistry.reset_instance()
    yield
    LogConfigRegistry.reset_instance()


@pytest.mark.unit
class TestLogConfigRegistry:
    """Unit tests for LogConfigRegistry."""

    def test_singleton_instance(self):
        """Test that get_instance returns singleton."""
        instance1 = LogConfigRegistry.get_instance()
        instance2 = LogConfigRegistry.get_instance()

        assert instance1 is instance2

    def test_reset_instance(self):
        """Test that reset_instance creates new instance."""
        instance1 = LogConfigRegistry.get_instance()
        LogConfigRegistry.reset_instance()
        instance2 = LogConfigRegistry.get_instance()

        assert instance1 is not instance2

    def test_create_holder_returns_holder(self):
        """Test create_holder returns LogConfigHolder."""
        registry = LogConfigRegistry.get_instance()
        config = LogConfig.from_params("info")

        holder = registry.create_holder(config)

        assert isinstance(holder, LogConfigHolder)
        assert holder.config is config

    def test_create_holder_uses_default_config(self):
        """Test create_holder uses default when no config provided."""
        registry = LogConfigRegistry.get_instance()

        holder = registry.create_holder()

        # Default is "info"
        assert holder.config is not None
        assert holder.level == 20  # logging.INFO

    def test_set_default_config(self):
        """Test setting default config for new holders."""
        registry = LogConfigRegistry.get_instance()
        debug_config = LogConfig.from_params("debug")

        registry.set_default_config(debug_config)
        holder = registry.create_holder()

        assert holder.level == 10  # logging.DEBUG

    def test_get_default_config(self):
        """Test getting default config."""
        registry = LogConfigRegistry.get_instance()
        config = LogConfig.from_params("warning")

        registry.set_default_config(config)

        assert registry.get_default_config() is config

    def test_update_all_updates_all_holders(self):
        """Test update_all updates all registered holders."""
        registry = LogConfigRegistry.get_instance()

        holder1 = registry.create_holder(LogConfig.from_params("info"))
        holder2 = registry.create_holder(LogConfig.from_params("info"))
        holder3 = registry.create_holder(LogConfig.from_params("info"))

        new_config = LogConfig.from_params("debug")
        registry.update_all(new_config)

        assert holder1.level == 10  # DEBUG
        assert holder2.level == 10
        assert holder3.level == 10

    def test_update_all_updates_default_config(self):
        """Test update_all also updates default config."""
        registry = LogConfigRegistry.get_instance()
        new_config = LogConfig.from_params("debug")

        registry.update_all(new_config)

        assert registry.get_default_config() is new_config

    def test_update_display_options_partial_update(self):
        """Test update_display_options only updates specified options."""
        registry = LogConfigRegistry.get_instance()
        config = LogConfig.from_params("info", location=1, micros=False, colors=True)
        holder = registry.create_holder(config)

        registry.update_display_options(location=5, colors=False)

        # Level unchanged
        assert holder.level == 20
        # Updated
        assert holder.location == 5
        assert holder.colors is False
        # Unchanged
        assert holder.micros is False

    def test_update_display_options_location_color(self):
        """Test update_display_options can update location_color."""
        registry = LogConfigRegistry.get_instance()
        holder = registry.create_holder(LogConfig.from_params("info"))

        registry.update_display_options(location_color="\x1b[35")

        assert holder.location_color == "\x1b[35"

    def test_holder_count(self):
        """Test holder_count returns correct count."""
        registry = LogConfigRegistry.get_instance()

        assert registry.holder_count() == 0

        registry.create_holder()
        assert registry.holder_count() == 1

        registry.create_holder()
        registry.create_holder()
        assert registry.holder_count() == 3

    def test_clear_holders(self):
        """Test clear_holders removes all holders."""
        registry = LogConfigRegistry.get_instance()

        registry.create_holder()
        registry.create_holder()
        assert registry.holder_count() == 2

        registry.clear_holders()
        assert registry.holder_count() == 0
