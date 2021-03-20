from __future__ import annotations

import pytest

from bot.emote import EmotePosition
from bot.emote import parse_emote_info


@pytest.mark.parametrize(
    ('s', 'expected'),
    (
        ('', []),
        ('303330140:23-31', [EmotePosition(23, 31, '303330140')]),
        ('302498976_BW:0-15', [EmotePosition(0, 15, '302498976_BW')]),
        (
            '300753352:36-45/303265469:0-7,9-16,18-25',
            [
                EmotePosition(0, 7, '303265469'),
                EmotePosition(9, 16, '303265469'),
                EmotePosition(18, 25, '303265469'),
                EmotePosition(36, 45, '300753352'),
            ],
        ),
    ),
)
def test_parse_emote_info(s, expected):
    assert parse_emote_info(s) == expected
