"""Tests for cli.cli module."""

import sys
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestCLI:
    """Test CLI entry point."""

    def test_main_with_help(self, capsys):
        """Test main() with --help flag."""
        from appinfra.cli.cli import main

        with patch.object(sys, "argv", ["cli.py", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_with_invalid_args(self):
        """Test main() with invalid arguments."""
        from appinfra.cli.cli import main

        with patch.object(sys, "argv", ["cli.py", "nonexistent_command"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Should exit with non-zero for invalid command
            assert exc_info.value.code != 0
