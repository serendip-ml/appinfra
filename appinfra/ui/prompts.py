"""
Interactive prompts for CLI tools.

Provides smart confirmations, password input, selections, and
other interactive prompts. Respects --yes and --non-interactive
flags, and auto-detects non-TTY environments.
"""

from __future__ import annotations

import getpass
import os
import sys
from collections.abc import Callable, Sequence
from typing import Any

# Check for questionary availability
try:
    import questionary
    from questionary import Style

    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False
    questionary = None  # type: ignore[assignment]
    Style = None  # type: ignore[assignment, misc]


# Default style for prompts
PROMPT_STYLE = None
if QUESTIONARY_AVAILABLE and Style is not None:
    PROMPT_STYLE = Style(
        [
            ("question", "bold"),
            ("answer", "fg:green bold"),
            ("pointer", "fg:cyan bold"),
            ("highlighted", "fg:cyan bold"),
            ("selected", "fg:green"),
        ]
    )


def _is_interactive() -> bool:
    """Check if we're in an interactive terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _get_auto_confirm() -> bool:
    """Check if auto-confirm is enabled via environment."""
    return os.environ.get("APPINFRA_YES", "").lower() in ("1", "true", "yes")


def _get_non_interactive() -> bool:
    """Check if non-interactive mode is forced via environment."""
    return os.environ.get("APPINFRA_NON_INTERACTIVE", "").lower() in (
        "1",
        "true",
        "yes",
    )


class NonInteractiveError(Exception):
    """Raised when interactive input is required but not available."""

    pass


def _confirm_fallback(message: str, default: bool) -> bool:
    """Fallback confirmation using standard input."""
    suffix = " [Y/n]" if default else " [y/N]"
    try:
        response = input(f"{message}{suffix} ").strip().lower()
        return response in ("y", "yes") if response else default
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def confirm(
    message: str, *, default: bool = False, auto_confirm: bool | None = None
) -> bool:
    """
    Ask for confirmation.

    Args:
        message: The confirmation question
        default: Default value if user just presses Enter
        auto_confirm: Override auto-confirm behavior (None = auto-detect)

    Returns:
        True if confirmed, False otherwise

    Raises:
        NonInteractiveError: If in non-interactive mode and no auto-confirm
    """
    if auto_confirm is True or (auto_confirm is None and _get_auto_confirm()):
        return True
    if not _is_interactive() or _get_non_interactive():
        if auto_confirm is False:
            raise NonInteractiveError(
                f"Cannot prompt for confirmation in non-interactive mode: {message}"
            )
        return default
    if QUESTIONARY_AVAILABLE and questionary:
        result = questionary.confirm(message, default=default, style=PROMPT_STYLE).ask()
        return result if result is not None else default
    return _confirm_fallback(message, default)


def _text_fallback(
    message: str, default: str, validate: Callable[[str], bool] | None
) -> str:
    """Fallback text input using standard input."""
    prompt = f"{message} [{default}] " if default else f"{message} "
    while True:
        try:
            response = input(prompt).strip() or default
            if validate and not validate(response):
                print("Invalid input. Please try again.")
                continue
            return response
        except (EOFError, KeyboardInterrupt):
            print()
            return default


def text(
    message: str,
    *,
    default: str = "",
    validate: Callable[[str], bool] | None = None,
    multiline: bool = False,
) -> str:
    """
    Prompt for text input.

    Args:
        message: The prompt message
        default: Default value
        validate: Optional validation function
        multiline: Allow multiline input

    Returns:
        User input string

    Raises:
        NonInteractiveError: If in non-interactive mode
    """
    if not _is_interactive() or _get_non_interactive():
        if default:
            return default
        raise NonInteractiveError(
            f"Cannot prompt for text input in non-interactive mode: {message}"
        )
    if QUESTIONARY_AVAILABLE and questionary:
        result = questionary.text(
            message,
            default=default,
            validate=validate,
            multiline=multiline,
            style=PROMPT_STYLE,
        ).ask()
        return result if result is not None else default
    return _text_fallback(message, default, validate)


def _password_questionary(message: str, do_confirm: bool) -> str:
    """Get password using questionary."""
    pwd_result = questionary.password(message, style=PROMPT_STYLE).ask()
    if pwd_result is None:
        return ""
    pwd: str = str(pwd_result)
    if do_confirm:
        pwd2_result = questionary.password(
            "Confirm password:", style=PROMPT_STYLE
        ).ask()
        if str(pwd2_result) if pwd2_result else "" != pwd:
            print("Passwords do not match. Please try again.")
            return _password_questionary(message, do_confirm)
    return pwd


def _password_getpass(message: str, do_confirm: bool) -> str:
    """Get password using getpass fallback."""
    while True:
        pwd = getpass.getpass(f"{message} ")
        if do_confirm:
            if getpass.getpass("Confirm password: ") != pwd:
                print("Passwords do not match. Please try again.")
                continue
        return pwd


def password(message: str, *, confirm: bool = False) -> str:
    """
    Prompt for password input (masked).

    Args:
        message: The prompt message
        confirm: Ask for confirmation (enter password twice)

    Returns:
        Password string

    Raises:
        NonInteractiveError: If in non-interactive mode
    """
    if not _is_interactive() or _get_non_interactive():
        raise NonInteractiveError(
            f"Cannot prompt for password in non-interactive mode: {message}"
        )
    if QUESTIONARY_AVAILABLE and questionary:
        return _password_questionary(message, confirm)
    return _password_getpass(message, confirm)


def _normalize_choices(choices: Sequence[str] | Sequence[dict[str, Any]]) -> list[dict]:
    """Normalize choices to list of dicts with name and value."""
    choice_list = []
    for c in choices:
        if isinstance(c, dict):
            choice_list.append(c)
        else:
            choice_list.append({"name": str(c), "value": str(c)})
    return choice_list


def _select_questionary(
    message: str, choice_list: list[dict], default: str | None
) -> str:
    """Use questionary for selection if available."""
    result = questionary.select(
        message,
        choices=[c["name"] for c in choice_list],
        default=default,
        style=PROMPT_STYLE,
    ).ask()

    if result is None:
        return default or str(choice_list[0]["value"])

    for c in choice_list:
        if c["name"] == result:
            return str(c["value"])
    return str(result)


def _select_fallback(message: str, choice_list: list[dict], default: str | None) -> str:
    """Fallback to numbered selection without questionary."""
    print(message)
    for i, c in enumerate(choice_list, 1):
        marker = "*" if c["value"] == default else " "
        print(f"  {marker}{i}. {c['name']}")

    while True:
        try:
            response = input("Enter number: ").strip()
            if not response and default:
                return default
            idx = int(response) - 1
            if 0 <= idx < len(choice_list):
                return str(choice_list[idx]["value"])
            print(f"Please enter a number between 1 and {len(choice_list)}")
        except ValueError:
            print("Please enter a valid number")
        except (EOFError, KeyboardInterrupt):
            print()
            return default or str(choice_list[0]["value"])


def select(
    message: str,
    choices: Sequence[str] | Sequence[dict[str, Any]],
    *,
    default: str | None = None,
) -> str:
    """
    Prompt for single selection from choices.

    Args:
        message: The prompt message
        choices: List of choices (strings or dicts with 'name' and 'value')
        default: Default selection

    Returns:
        Selected value

    Raises:
        NonInteractiveError: If in non-interactive mode

    Example:
        env = select("Choose environment:", ["dev", "staging", "prod"])
    """
    if not _is_interactive() or _get_non_interactive():
        if default:
            return default
        raise NonInteractiveError(
            f"Cannot prompt for selection in non-interactive mode: {message}"
        )

    choice_list = _normalize_choices(choices)

    if QUESTIONARY_AVAILABLE and questionary:
        return _select_questionary(message, choice_list, default)
    return _select_fallback(message, choice_list, default)


def _multiselect_questionary(
    message: str, choice_list: list[dict], default: Sequence[str] | None
) -> list[str]:
    """Use questionary for multiselect if available."""
    q_choices = []
    for c in choice_list:
        checked = bool(default and c["value"] in default)
        q_choices.append(questionary.Choice(c["name"], checked=checked))

    result = questionary.checkbox(message, choices=q_choices, style=PROMPT_STYLE).ask()

    if result is None:
        return list(default) if default else []

    values = []
    for name in result:
        for c in choice_list:
            if c["name"] == name:
                values.append(str(c["value"]))
                break
    return values


def _multiselect_fallback(
    message: str, choice_list: list[dict], default: Sequence[str] | None
) -> list[str]:
    """Fallback to comma-separated input without questionary."""
    print(message)
    for i, c in enumerate(choice_list, 1):
        marker = "*" if default and c["value"] in default else " "
        print(f"  {marker}{i}. {c['name']}")

    print("Enter numbers separated by commas (e.g., 1,3,4)")
    if default:
        print(f"Press Enter for default: {', '.join(default)}")

    try:
        response = input("Selection: ").strip()
        if not response:
            return list(default) if default else []

        selected = []
        for part in response.split(","):
            try:
                idx = int(part.strip()) - 1
                if 0 <= idx < len(choice_list):
                    selected.append(str(choice_list[idx]["value"]))
            except ValueError:
                pass
        return selected
    except (EOFError, KeyboardInterrupt):
        print()
        return list(default) if default else []


def multiselect(
    message: str,
    choices: Sequence[str] | Sequence[dict[str, Any]],
    *,
    default: Sequence[str] | None = None,
) -> list[str]:
    """
    Prompt for multiple selections from choices.

    Args:
        message: The prompt message
        choices: List of choices (strings or dicts with 'name' and 'value')
        default: Default selections

    Returns:
        List of selected values

    Raises:
        NonInteractiveError: If in non-interactive mode

    Example:
        features = multiselect(
            "Enable features:",
            ["auth", "logging", "cache"],
            default=["logging"]
        )
    """
    if not _is_interactive() or _get_non_interactive():
        if default:
            return list(default)
        raise NonInteractiveError(
            f"Cannot prompt for multiselect in non-interactive mode: {message}"
        )

    choice_list = _normalize_choices(choices)

    if QUESTIONARY_AVAILABLE and questionary:
        return _multiselect_questionary(message, choice_list, default)
    return _multiselect_fallback(message, choice_list, default)
