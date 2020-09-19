import collections
import datetime
import functools
import os
import re
from typing import Counter
from typing import Mapping
from typing import Match
from typing import Optional
from typing import Pattern
from typing import Tuple

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.permissions import optional_user_arg

CHAT_LOG_RE = re.compile(
    r'^\[[^]]+\][^<*]*(<(?P<chat_user>[^>]+)>|\* (?P<action_user>[^ ]+))',
)
BONKER_RE = re.compile(r'^\[[^]]+\][^<*]*<(?P<chat_user>[^>]+)> !bonk\b')
BONKED_RE = re.compile(r'^\[[^]]+\][^<*]*<[^>]+> !bonk @?(?P<chat_user>\w+)')


@functools.lru_cache(maxsize=None)
def _counts_per_file(filename: str, reg: Pattern[str]) -> Mapping[str, int]:
    counts: Counter[str] = collections.Counter()
    with open(filename) as f:
        for line in f:
            match = reg.match(line)
            if match is None:
                assert reg is not CHAT_LOG_RE
                continue
            user = match['chat_user'] or match['action_user']
            assert user, line
            counts[user.lower()] += 1
    return counts


def _chat_rank_counts(reg: Pattern[str]) -> Counter[str]:
    total: Counter[str] = collections.Counter()
    for filename in os.listdir('logs'):
        full_filename = os.path.join('logs', filename)
        if filename != f'{datetime.date.today()}.log':
            total.update(_counts_per_file(full_filename, reg))
        else:
            # don't use the cached version for today's logs
            total.update(_counts_per_file.__wrapped__(full_filename, reg))
    return total


def _rank(username: str, reg: Pattern[str]) -> Optional[Tuple[int, int]]:
    total = _chat_rank_counts(reg)

    username = username.lower()
    for i, (candidate, count) in enumerate(total.most_common(), start=1):
        if candidate == username:
            return i, count
    else:
        return None


@functools.lru_cache(maxsize=1)
def _log_start_date() -> str:
    logs_start = min(os.listdir('logs'))
    logs_start, _, _ = logs_start.partition('.')
    return logs_start


@command('!chatrank')
async def cmd_chatrank(config: Config, match: Match[str]) -> str:
    user = optional_user_arg(match)
    ret = _rank(user, CHAT_LOG_RE)
    if ret is None:
        return format_msg(match, f'user not found {esc(user)}')
    else:
        rank, n = ret
        return format_msg(
            match,
            f'{esc(user)} is ranked #{rank} with {n} messages '
            f'(since {_log_start_date()})',
        )


@command('!top10chat')
async def cmd_top_10_chat(config: Config, match: Match[str]) -> str:
    total = _chat_rank_counts(CHAT_LOG_RE)
    user_list = ', '.join(
        f'{rank}. {user}({n})'
        for rank, (user, n) in enumerate(total.most_common(10), start=1)
    )
    return format_msg(match, f'{user_list} (since {_log_start_date()})')


@command('!bonkrank')
async def cmd_bonkrank(config: Config, match: Match[str]) -> str:
    user = optional_user_arg(match)
    ret = _rank(user, BONKER_RE)
    if ret is None:
        return format_msg(match, f'user not found {esc(user)}')
    else:
        rank, n = ret
        return format_msg(
            match,
            f'{esc(user)} is ranked #{rank}, has bonked others {n} times',
        )


@command('!top5bonkers')
async def cmd_top_5_bonkers(config: Config, match: Match[str]) -> str:
    total = _chat_rank_counts(BONKER_RE)
    user_list = ', '.join(
        f'{rank}. {user}({n})'
        for rank, (user, n) in enumerate(total.most_common(5), start=1)
    )
    return format_msg(match, user_list)


@command('!bonkedrank')
async def cmd_bonkedrank(config: Config, match: Match[str]) -> str:
    user = optional_user_arg(match)
    ret = _rank(user, BONKED_RE)
    if ret is None:
        return format_msg(match, f'user not found {esc(user)}')
    else:
        rank, n = ret
        return format_msg(
            match,
            f'{esc(user)} is ranked #{rank}, has been bonked {n} times',
        )


@command('!top5bonked')
async def cmd_top_5_bonked(config: Config, match: Match[str]) -> str:
    total = _chat_rank_counts(BONKED_RE)
    user_list = ', '.join(
        f'{rank}. {user}({n})'
        for rank, (user, n) in enumerate(total.most_common(5), start=1)
    )
    return format_msg(match, user_list)
