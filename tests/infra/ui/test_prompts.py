"""Tests for appinfra.ui.prompts module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from appinfra.ui import prompts
from appinfra.ui.prompts import (
    NonInteractiveError,
    _confirm_fallback,
    _get_auto_confirm,
    _get_non_interactive,
    _is_interactive,
    _multiselect_fallback,
    _normalize_choices,
    _password_getpass,
    _select_fallback,
    _text_fallback,
    confirm,
    multiselect,
    password,
    select,
    text,
)


class TestIsInteractive:
    """Tests for _is_interactive function."""

    def test_interactive_when_both_tty(self):
        """Test returns True when stdin and stdout are TTY."""
        with patch("sys.stdin") as mock_stdin, patch("sys.stdout") as mock_stdout:
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = True
            assert _is_interactive() is True

    def test_not_interactive_when_stdin_not_tty(self):
        """Test returns False when stdin is not TTY."""
        with patch("sys.stdin") as mock_stdin, patch("sys.stdout") as mock_stdout:
            mock_stdin.isatty.return_value = False
            mock_stdout.isatty.return_value = True
            assert _is_interactive() is False

    def test_not_interactive_when_stdout_not_tty(self):
        """Test returns False when stdout is not TTY."""
        with patch("sys.stdin") as mock_stdin, patch("sys.stdout") as mock_stdout:
            mock_stdin.isatty.return_value = True
            mock_stdout.isatty.return_value = False
            assert _is_interactive() is False


class TestGetAutoConfirm:
    """Tests for _get_auto_confirm function."""

    def test_auto_confirm_when_env_1(self):
        """Test returns True when APPINFRA_YES is 1."""
        with patch.dict(os.environ, {"APPINFRA_YES": "1"}):
            assert _get_auto_confirm() is True

    def test_auto_confirm_when_env_true(self):
        """Test returns True when APPINFRA_YES is true."""
        with patch.dict(os.environ, {"APPINFRA_YES": "true"}):
            assert _get_auto_confirm() is True

    def test_auto_confirm_when_env_yes(self):
        """Test returns True when APPINFRA_YES is yes."""
        with patch.dict(os.environ, {"APPINFRA_YES": "yes"}):
            assert _get_auto_confirm() is True

    def test_auto_confirm_case_insensitive(self):
        """Test env check is case insensitive."""
        with patch.dict(os.environ, {"APPINFRA_YES": "TRUE"}):
            assert _get_auto_confirm() is True

    def test_no_auto_confirm_when_env_empty(self):
        """Test returns False when APPINFRA_YES is not set."""
        with patch.dict(os.environ, {"APPINFRA_YES": ""}, clear=False):
            # Clear the env var if it exists
            os.environ.pop("APPINFRA_YES", None)
            assert _get_auto_confirm() is False

    def test_no_auto_confirm_when_env_no(self):
        """Test returns False when APPINFRA_YES is something else."""
        with patch.dict(os.environ, {"APPINFRA_YES": "no"}):
            assert _get_auto_confirm() is False


class TestGetNonInteractive:
    """Tests for _get_non_interactive function."""

    def test_non_interactive_when_env_1(self):
        """Test returns True when APPINFRA_NON_INTERACTIVE is 1."""
        with patch.dict(os.environ, {"APPINFRA_NON_INTERACTIVE": "1"}):
            assert _get_non_interactive() is True

    def test_non_interactive_when_env_true(self):
        """Test returns True when APPINFRA_NON_INTERACTIVE is true."""
        with patch.dict(os.environ, {"APPINFRA_NON_INTERACTIVE": "true"}):
            assert _get_non_interactive() is True

    def test_no_non_interactive_when_env_empty(self):
        """Test returns False when APPINFRA_NON_INTERACTIVE is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APPINFRA_NON_INTERACTIVE", None)
            assert _get_non_interactive() is False


class TestNonInteractiveError:
    """Tests for NonInteractiveError exception."""

    def test_exception_message(self):
        """Test exception contains message."""
        with pytest.raises(NonInteractiveError, match="test message"):
            raise NonInteractiveError("test message")


class TestNormalizeChoices:
    """Tests for _normalize_choices function."""

    def test_normalize_string_choices(self):
        """Test normalizing string choices."""
        result = _normalize_choices(["a", "b", "c"])
        assert result == [
            {"name": "a", "value": "a"},
            {"name": "b", "value": "b"},
            {"name": "c", "value": "c"},
        ]

    def test_normalize_dict_choices(self):
        """Test normalizing dict choices passes through."""
        choices = [
            {"name": "Option A", "value": "a"},
            {"name": "Option B", "value": "b"},
        ]
        result = _normalize_choices(choices)
        assert result == choices

    def test_normalize_mixed_choices(self):
        """Test normalizing mixed string and dict choices."""
        choices = ["a", {"name": "Option B", "value": "b"}]
        result = _normalize_choices(choices)
        assert result == [
            {"name": "a", "value": "a"},
            {"name": "Option B", "value": "b"},
        ]


class TestConfirmFallback:
    """Tests for _confirm_fallback function."""

    def test_confirm_yes_response(self):
        """Test 'y' response returns True."""
        with patch("builtins.input", return_value="y"):
            assert _confirm_fallback("Continue?", False) is True

    def test_confirm_yes_full_response(self):
        """Test 'yes' response returns True."""
        with patch("builtins.input", return_value="yes"):
            assert _confirm_fallback("Continue?", False) is True

    def test_confirm_no_response(self):
        """Test 'n' response returns False."""
        with patch("builtins.input", return_value="n"):
            assert _confirm_fallback("Continue?", True) is False

    def test_confirm_empty_uses_default_true(self):
        """Test empty response returns default (True)."""
        with patch("builtins.input", return_value=""):
            assert _confirm_fallback("Continue?", True) is True

    def test_confirm_empty_uses_default_false(self):
        """Test empty response returns default (False)."""
        with patch("builtins.input", return_value=""):
            assert _confirm_fallback("Continue?", False) is False

    def test_confirm_eof_returns_false(self):
        """Test EOFError returns False."""
        with patch("builtins.input", side_effect=EOFError), patch("builtins.print"):
            assert _confirm_fallback("Continue?", True) is False

    def test_confirm_keyboard_interrupt_returns_false(self):
        """Test KeyboardInterrupt returns False."""
        with (
            patch("builtins.input", side_effect=KeyboardInterrupt),
            patch("builtins.print"),
        ):
            assert _confirm_fallback("Continue?", True) is False


class TestConfirm:
    """Tests for confirm function."""

    def test_confirm_auto_confirm_true(self):
        """Test auto_confirm=True returns True immediately."""
        assert confirm("Continue?", auto_confirm=True) is True

    def test_confirm_auto_confirm_from_env(self):
        """Test auto_confirm from environment."""
        with patch.dict(os.environ, {"APPINFRA_YES": "1"}):
            assert confirm("Continue?") is True

    def test_confirm_non_interactive_returns_default(self):
        """Test non-interactive mode returns default."""
        with (
            patch.object(prompts, "_is_interactive", return_value=False),
            patch.dict(os.environ, {"APPINFRA_YES": ""}),
        ):
            os.environ.pop("APPINFRA_YES", None)
            assert confirm("Continue?", default=True) is True
            assert confirm("Continue?", default=False) is False

    def test_confirm_non_interactive_raises_when_auto_confirm_false(self):
        """Test non-interactive mode raises when auto_confirm=False."""
        with patch.object(prompts, "_is_interactive", return_value=False):
            with pytest.raises(NonInteractiveError):
                confirm("Continue?", auto_confirm=False)

    def test_confirm_uses_fallback_when_no_questionary(self):
        """Test confirm uses fallback when questionary not available."""
        with (
            patch.object(prompts, "_is_interactive", return_value=True),
            patch.object(prompts, "_get_non_interactive", return_value=False),
            patch.object(prompts, "_get_auto_confirm", return_value=False),
            patch.object(prompts, "QUESTIONARY_AVAILABLE", False),
            patch.object(
                prompts, "_confirm_fallback", return_value=True
            ) as mock_fallback,
        ):
            result = confirm("Continue?", default=True)
            mock_fallback.assert_called_once_with("Continue?", True)
            assert result is True


class TestTextFallback:
    """Tests for _text_fallback function."""

    def test_text_returns_input(self):
        """Test returns user input."""
        with patch("builtins.input", return_value="hello"):
            assert _text_fallback("Name:", "", None) == "hello"

    def test_text_empty_returns_default(self):
        """Test empty input returns default."""
        with patch("builtins.input", return_value=""):
            assert _text_fallback("Name:", "default", None) == "default"

    def test_text_with_validation_valid(self):
        """Test input passes validation."""
        with patch("builtins.input", return_value="valid"):
            assert _text_fallback("Name:", "", lambda x: len(x) > 2) == "valid"

    def test_text_with_validation_invalid_then_valid(self):
        """Test invalid input prompts again."""
        inputs = iter(["a", "valid"])
        with (
            patch("builtins.input", side_effect=lambda _: next(inputs)),
            patch("builtins.print"),
        ):
            assert _text_fallback("Name:", "", lambda x: len(x) > 2) == "valid"

    def test_text_eof_returns_default(self):
        """Test EOFError returns default."""
        with patch("builtins.input", side_effect=EOFError), patch("builtins.print"):
            assert _text_fallback("Name:", "default", None) == "default"


class TestText:
    """Tests for text function."""

    def test_text_non_interactive_returns_default(self):
        """Test non-interactive mode returns default."""
        with patch.object(prompts, "_is_interactive", return_value=False):
            assert text("Name:", default="default") == "default"

    def test_text_non_interactive_raises_without_default(self):
        """Test non-interactive mode raises without default."""
        with patch.object(prompts, "_is_interactive", return_value=False):
            with pytest.raises(NonInteractiveError):
                text("Name:")

    def test_text_uses_fallback_when_no_questionary(self):
        """Test text uses fallback when questionary not available."""
        with (
            patch.object(prompts, "_is_interactive", return_value=True),
            patch.object(prompts, "_get_non_interactive", return_value=False),
            patch.object(prompts, "QUESTIONARY_AVAILABLE", False),
            patch.object(
                prompts, "_text_fallback", return_value="input"
            ) as mock_fallback,
        ):
            result = text("Name:", default="default")
            mock_fallback.assert_called_once()
            assert result == "input"


class TestPasswordGetpass:
    """Tests for _password_getpass function."""

    def test_password_returns_input(self):
        """Test returns password input."""
        with patch("getpass.getpass", return_value="secret"):
            assert _password_getpass("Password:", False) == "secret"

    def test_password_with_confirm_matching(self):
        """Test password with matching confirmation."""
        with patch("getpass.getpass", side_effect=["secret", "secret"]):
            assert _password_getpass("Password:", True) == "secret"

    def test_password_with_confirm_not_matching_then_matching(self):
        """Test password retry on mismatch."""
        with (
            patch(
                "getpass.getpass", side_effect=["secret", "wrong", "secret", "secret"]
            ),
            patch("builtins.print"),
        ):
            assert _password_getpass("Password:", True) == "secret"


class TestPassword:
    """Tests for password function."""

    def test_password_non_interactive_raises(self):
        """Test non-interactive mode raises."""
        with patch.object(prompts, "_is_interactive", return_value=False):
            with pytest.raises(NonInteractiveError):
                password("Password:")

    def test_password_uses_getpass_when_no_questionary(self):
        """Test password uses getpass when questionary not available."""
        with (
            patch.object(prompts, "_is_interactive", return_value=True),
            patch.object(prompts, "_get_non_interactive", return_value=False),
            patch.object(prompts, "QUESTIONARY_AVAILABLE", False),
            patch.object(
                prompts, "_password_getpass", return_value="secret"
            ) as mock_getpass,
        ):
            result = password("Password:", confirm=True)
            mock_getpass.assert_called_once_with("Password:", True)
            assert result == "secret"


class TestSelectFallback:
    """Tests for _select_fallback function."""

    def test_select_valid_choice(self):
        """Test selecting valid choice."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", return_value="1"), patch("builtins.print"):
            assert _select_fallback("Choose:", choices, None) == "a"

    def test_select_second_choice(self):
        """Test selecting second choice."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", return_value="2"), patch("builtins.print"):
            assert _select_fallback("Choose:", choices, None) == "b"

    def test_select_empty_returns_default(self):
        """Test empty input returns default."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", return_value=""), patch("builtins.print"):
            assert _select_fallback("Choose:", choices, "b") == "b"

    def test_select_invalid_then_valid(self):
        """Test invalid input prompts again."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        inputs = iter(["5", "1"])
        with (
            patch("builtins.input", side_effect=lambda _: next(inputs)),
            patch("builtins.print"),
        ):
            assert _select_fallback("Choose:", choices, None) == "a"

    def test_select_non_number_then_valid(self):
        """Test non-number input prompts again."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        inputs = iter(["abc", "1"])
        with (
            patch("builtins.input", side_effect=lambda _: next(inputs)),
            patch("builtins.print"),
        ):
            assert _select_fallback("Choose:", choices, None) == "a"

    def test_select_eof_returns_default_or_first(self):
        """Test EOFError returns default or first choice."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", side_effect=EOFError), patch("builtins.print"):
            assert _select_fallback("Choose:", choices, "b") == "b"
            assert _select_fallback("Choose:", choices, None) == "a"


class TestSelect:
    """Tests for select function."""

    def test_select_non_interactive_returns_default(self):
        """Test non-interactive mode returns default."""
        with patch.object(prompts, "_is_interactive", return_value=False):
            assert select("Choose:", ["a", "b"], default="b") == "b"

    def test_select_non_interactive_raises_without_default(self):
        """Test non-interactive mode raises without default."""
        with patch.object(prompts, "_is_interactive", return_value=False):
            with pytest.raises(NonInteractiveError):
                select("Choose:", ["a", "b"])

    def test_select_uses_fallback_when_no_questionary(self):
        """Test select uses fallback when questionary not available."""
        with (
            patch.object(prompts, "_is_interactive", return_value=True),
            patch.object(prompts, "_get_non_interactive", return_value=False),
            patch.object(prompts, "QUESTIONARY_AVAILABLE", False),
            patch.object(
                prompts, "_select_fallback", return_value="a"
            ) as mock_fallback,
        ):
            result = select("Choose:", ["a", "b"], default="a")
            mock_fallback.assert_called_once()
            assert result == "a"


class TestMultiselectFallback:
    """Tests for _multiselect_fallback function."""

    def test_multiselect_single_choice(self):
        """Test selecting single choice."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", return_value="1"), patch("builtins.print"):
            assert _multiselect_fallback("Choose:", choices, None) == ["a"]

    def test_multiselect_multiple_choices(self):
        """Test selecting multiple choices."""
        choices = [
            {"name": "a", "value": "a"},
            {"name": "b", "value": "b"},
            {"name": "c", "value": "c"},
        ]
        with patch("builtins.input", return_value="1,3"), patch("builtins.print"):
            assert _multiselect_fallback("Choose:", choices, None) == ["a", "c"]

    def test_multiselect_empty_returns_default(self):
        """Test empty input returns default."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", return_value=""), patch("builtins.print"):
            assert _multiselect_fallback("Choose:", choices, ["b"]) == ["b"]

    def test_multiselect_empty_no_default(self):
        """Test empty input with no default returns empty list."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", return_value=""), patch("builtins.print"):
            assert _multiselect_fallback("Choose:", choices, None) == []

    def test_multiselect_invalid_indices_ignored(self):
        """Test invalid indices are ignored."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", return_value="1,5,abc"), patch("builtins.print"):
            assert _multiselect_fallback("Choose:", choices, None) == ["a"]

    def test_multiselect_eof_returns_default(self):
        """Test EOFError returns default."""
        choices = [{"name": "a", "value": "a"}, {"name": "b", "value": "b"}]
        with patch("builtins.input", side_effect=EOFError), patch("builtins.print"):
            assert _multiselect_fallback("Choose:", choices, ["a"]) == ["a"]


class TestMultiselect:
    """Tests for multiselect function."""

    def test_multiselect_non_interactive_returns_default(self):
        """Test non-interactive mode returns default."""
        with patch.object(prompts, "_is_interactive", return_value=False):
            assert multiselect("Choose:", ["a", "b"], default=["b"]) == ["b"]

    def test_multiselect_non_interactive_raises_without_default(self):
        """Test non-interactive mode raises without default."""
        with patch.object(prompts, "_is_interactive", return_value=False):
            with pytest.raises(NonInteractiveError):
                multiselect("Choose:", ["a", "b"])

    def test_multiselect_uses_fallback_when_no_questionary(self):
        """Test multiselect uses fallback when questionary not available."""
        with (
            patch.object(prompts, "_is_interactive", return_value=True),
            patch.object(prompts, "_get_non_interactive", return_value=False),
            patch.object(prompts, "QUESTIONARY_AVAILABLE", False),
            patch.object(
                prompts, "_multiselect_fallback", return_value=["a"]
            ) as mock_fallback,
        ):
            result = multiselect("Choose:", ["a", "b"], default=["a"])
            mock_fallback.assert_called_once()
            assert result == ["a"]


class TestQuestionaryIntegration:
    """Tests for questionary integration when available."""

    @pytest.fixture
    def mock_questionary(self):
        """Mock questionary module."""
        mock_q = MagicMock()
        with (
            patch.object(prompts, "QUESTIONARY_AVAILABLE", True),
            patch.object(prompts, "questionary", mock_q),
            patch.object(prompts, "_is_interactive", return_value=True),
            patch.object(prompts, "_get_non_interactive", return_value=False),
            patch.object(prompts, "_get_auto_confirm", return_value=False),
        ):
            yield mock_q

    def test_confirm_uses_questionary(self, mock_questionary):
        """Test confirm uses questionary when available."""
        mock_questionary.confirm.return_value.ask.return_value = True
        result = confirm("Continue?", default=False)
        mock_questionary.confirm.assert_called_once()
        assert result is True

    def test_confirm_questionary_none_returns_default(self, mock_questionary):
        """Test confirm returns default when questionary returns None."""
        mock_questionary.confirm.return_value.ask.return_value = None
        result = confirm("Continue?", default=True)
        assert result is True

    def test_text_uses_questionary(self, mock_questionary):
        """Test text uses questionary when available."""
        mock_questionary.text.return_value.ask.return_value = "hello"
        result = text("Name:", default="default")
        mock_questionary.text.assert_called_once()
        assert result == "hello"

    def test_text_questionary_none_returns_default(self, mock_questionary):
        """Test text returns default when questionary returns None."""
        mock_questionary.text.return_value.ask.return_value = None
        result = text("Name:", default="default")
        assert result == "default"

    def test_select_uses_questionary(self, mock_questionary):
        """Test select uses questionary when available."""
        mock_questionary.select.return_value.ask.return_value = "b"
        result = select("Choose:", ["a", "b"])
        mock_questionary.select.assert_called_once()
        assert result == "b"

    def test_select_questionary_none_returns_default(self, mock_questionary):
        """Test select returns default when questionary returns None."""
        mock_questionary.select.return_value.ask.return_value = None
        result = select("Choose:", ["a", "b"], default="a")
        assert result == "a"

    def test_multiselect_uses_questionary(self, mock_questionary):
        """Test multiselect uses questionary when available."""
        mock_questionary.checkbox.return_value.ask.return_value = ["a", "b"]
        mock_questionary.Choice = MagicMock()
        result = multiselect("Choose:", ["a", "b", "c"])
        mock_questionary.checkbox.assert_called_once()
        assert result == ["a", "b"]

    def test_multiselect_questionary_none_returns_default(self, mock_questionary):
        """Test multiselect returns default when questionary returns None."""
        mock_questionary.checkbox.return_value.ask.return_value = None
        mock_questionary.Choice = MagicMock()
        result = multiselect("Choose:", ["a", "b"], default=["a"])
        assert result == ["a"]

    def test_password_uses_questionary(self, mock_questionary):
        """Test password uses questionary when available."""
        mock_questionary.password.return_value.ask.return_value = "secret"
        result = password("Password:")
        mock_questionary.password.assert_called_once()
        assert result == "secret"

    def test_password_questionary_none_returns_empty(self, mock_questionary):
        """Test password returns empty when questionary returns None."""
        mock_questionary.password.return_value.ask.return_value = None
        result = password("Password:")
        assert result == ""

    def test_password_questionary_no_confirm(self, mock_questionary):
        """Test password without confirmation."""
        # Test the happy path without confirmation
        mock_questionary.password.return_value.ask.return_value = "secretpass"
        result = password("Password:", confirm=False)
        assert mock_questionary.password.call_count == 1
        assert result == "secretpass"
