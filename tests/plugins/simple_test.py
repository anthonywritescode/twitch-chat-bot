from __future__ import annotations

from bot.plugins.simple import _SECRET_COMMANDS
from bot.plugins.simple import _TEXT_COMMANDS


def test_secret_commands_are_sorted():
    assert _SECRET_COMMANDS == tuple(sorted(_SECRET_COMMANDS))


def test_text_commands_are_sorted():
    assert _TEXT_COMMANDS == tuple(sorted(_TEXT_COMMANDS))
