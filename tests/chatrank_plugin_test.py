from __future__ import annotations

from collections import Counter
from unittest.mock import patch

import pytest

from bot.plugins import chatrank


@pytest.mark.parametrize(
    ('username', 'counts', 'expected'),
    (
        pytest.param(
            'this_user_does_not_exist',
            Counter(),
            None,
            id='non-existing user and empty rank counts',
        ),
        pytest.param(
            'this_user_does_not_exist',
            Counter({
                'rank_1_user': 69,
                'rank_2_user': 42,
                'another_rank_2_user': 42,
            }),
            None,
            id='non-existing user with non-empty rank counts',
        ),
        pytest.param(
            'rank_1_user',
            Counter({
                'rank_1_user': 69,
                'rank_2_user': 42,
                'another_rank_2_user': 42,
            }),
            (1, 69),
            id='the only user with the highest messages count on the #1 rank',
        ),
        pytest.param(
            'rank_2_user',
            Counter({
                'rank_1_user': 69,
                'rank_2_user': 42,
                'another_rank_2_user': 42,
            }),
            (2, 42),
            id='the first of several users on the #2 rank with 42 messages',
        ),
        pytest.param(
            'another_rank_2_user',
            Counter({
                'rank_1_user': 69,
                'rank_2_user': 42,
                'another_rank_2_user': 42,
            }),
            (2, 42),
            id='the second of several users on the #2 rank with 42 messages',
        ),
    ),
)
def test_user_rank_by_line_type(username, counts, expected):
    with patch.object(chatrank, '_chat_rank_counts', return_value=counts):
        # the second parameter does not really affect the ranking logic,
        # so we always use chatrank.CHAT_LOG_RE
        ret = chatrank._user_rank_by_line_type(username, chatrank.CHAT_LOG_RE)
        assert ret == expected


@pytest.mark.parametrize(
    ('counts', 'n', 'expected'),
    (
        (Counter(), 0, []),
        (Counter(), 1, []),
        (
            Counter({
                'rank_1_user': 69,
                'rank_2_user': 42,
                'another_rank_2_user': 42,
            }),
            0,
            [],
        ),
        (
            Counter({
                'rank_1_user': 69,
                'rank_2_user': 42,
                'another_rank_2_user': 42,
            }),
            1,
            ['1. rank_1_user (69)'],
        ),
        (
            Counter({
                'rank_1_user': 69,
                'rank_2_user': 42,
                'another_rank_2_user': 42,
            }),
            3,
            [
                '1. rank_1_user (69)',
                '2. rank_2_user, another_rank_2_user (42)',
            ],
        ),
        (
            Counter({
                'rank_1_user': 69,
                'rank_2_user': 42,
                'another_rank_2_user': 42,
            }),
            999,
            [
                '1. rank_1_user (69)',
                '2. rank_2_user, another_rank_2_user (42)',
            ],
        ),
    ),
)
def test_top_n_rank_by_line_type(counts, n, expected):
    with patch.object(chatrank, '_chat_rank_counts', return_value=counts):
        # the second parameter does not really affect the ranking logic,
        # so we always use chatrank.CHAT_LOG_RE
        ret = chatrank._top_n_rank_by_line_type(chatrank.CHAT_LOG_RE, n=n)
        assert ret == expected
