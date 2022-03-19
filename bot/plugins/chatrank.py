from __future__ import annotations

import collections
import datetime
import functools
import json
import os
import re
import urllib.request
from typing import Any
from typing import Counter
from typing import Mapping
from typing import Match
from typing import Pattern
from typing import Sequence

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.permissions import optional_user_arg
from bot.ranking import tied_rank

CHAT_ALIASES = {
    'kevinsjoberg': 'kevinwritescode',
    'kmjao': 'kevinwritescode',
    'makayla_fox': 'marsha_socks'
}
CHAT_LOG_RE = re.compile(
    r'^\[[^]]+\][^<*]*(<(?P<chat_user>[^>]+)>|\* (?P<action_user>[^ ]+))',
)
BONKER_RE = re.compile(r'^\[[^]]+\][^<*]*<(?P<chat_user>[^>]+)> !bonk\b')
BONKED_RE = re.compile(r'^\[[^]]+\][^<*]*<[^>]+> !bonk @?(?P<chat_user>\w+)')


def _alias(user: str) -> str:
    return CHAT_ALIASES.get(user, user)


@functools.lru_cache(maxsize=None)
def _counts_per_file(filename: str, reg: Pattern[str]) -> Mapping[str, int]:
    counts: Counter[str] = collections.Counter()
    with open(filename, encoding='utf8') as f:
        for line in f:
            match = reg.match(line)
            if match is None:
                assert reg is not CHAT_LOG_RE
                continue
            user = match['chat_user'] or match['action_user']
            assert user, line

            counts[_alias(user.lower())] += 1
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


def _user_rank_by_line_type(
        username: str, reg: Pattern[str],
) -> tuple[int, int] | None:
    total = _chat_rank_counts(reg)
    target_username = username.lower()
    for rank, (count, users) in tied_rank(total.most_common()):
        for username, _ in users:
            if target_username == username:
                return rank, count
    else:
        return None


def _top_n_rank_by_line_type(reg: Pattern[str], n: int = 10) -> list[str]:
    total = _chat_rank_counts(reg)
    user_list = []
    for rank, (count, users) in tied_rank(total.most_common(n)):
        usernames = ', '.join(username for username, _ in users)
        user_list.append(f'{rank}. {usernames} ({count})')
    return user_list


@functools.lru_cache(maxsize=1)
def _log_start_date() -> str:
    logs_start = min(os.listdir('logs'))
    logs_start, _, _ = logs_start.partition('.')
    return logs_start


@command('!chatrank')
async def cmd_chatrank(config: Config, match: Match[str]) -> str:
    user = optional_user_arg(match)
    ret = _user_rank_by_line_type(user, CHAT_LOG_RE)
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
    top_10_s = ', '.join(_top_n_rank_by_line_type(CHAT_LOG_RE, n=10))
    return format_msg(match, f'{top_10_s} (since {_log_start_date()})')


@command('!bonkrank', secret=True)
async def cmd_bonkrank(config: Config, match: Match[str]) -> str:
    user = optional_user_arg(match)
    ret = _user_rank_by_line_type(user, BONKER_RE)
    if ret is None:
        return format_msg(match, f'user not found {esc(user)}')
    else:
        rank, n = ret
        return format_msg(
            match,
            f'{esc(user)} is ranked #{rank}, has bonked others {n} times',
        )


@command('!top5bonkers', secret=True)
async def cmd_top_5_bonkers(config: Config, match: Match[str]) -> str:
    top_5_s = ', '.join(_top_n_rank_by_line_type(BONKER_RE, n=5))
    return format_msg(match, top_5_s)


@command('!bonkedrank', secret=True)
async def cmd_bonkedrank(config: Config, match: Match[str]) -> str:
    user = optional_user_arg(match)
    ret = _user_rank_by_line_type(user, BONKED_RE)
    if ret is None:
        return format_msg(match, f'user not found {esc(user)}')
    else:
        rank, n = ret
        return format_msg(
            match,
            f'{esc(user)} is ranked #{rank}, has been bonked {n} times',
        )


@command('!top5bonked', secret=True)
async def cmd_top_5_bonked(config: Config, match: Match[str]) -> str:
    top_5_s = ', '.join(_top_n_rank_by_line_type(BONKED_RE, n=5))
    return format_msg(match, top_5_s)


def lin_regr(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    sum_x = sum(x)
    sum_xx = sum(xi * xi for xi in x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    b = (sum_y * sum_xx - sum_x * sum_xy) / (len(x) * sum_xx - sum_x * sum_x)
    a = (sum_xy - b * sum_x) / sum_xx
    return a, b


@command('!chatplot')
async def cmd_chatplot(config: Config, match: Match[str]) -> str:
    user_list = optional_user_arg(match).lower().split()
    user_list = [_alias(user.lstrip('@')) for user in user_list]
    user_list = list(dict.fromkeys(user_list))

    if len(user_list) > 2:
        return format_msg(match, 'sorry, can only compare 2 users')

    min_date = datetime.date.fromisoformat(_log_start_date())
    comp_users: dict[str, dict[str, list[int]]]
    comp_users = collections.defaultdict(lambda: {'x': [], 'y': []})
    for filename in sorted(os.listdir('logs')):
        if filename == f'{datetime.date.today()}.log':
            continue

        filename_date = datetime.date.fromisoformat(filename.split('.')[0])

        full_filename = os.path.join('logs', filename)
        counts = _counts_per_file(full_filename, CHAT_LOG_RE)
        for user in user_list:
            if counts[user]:
                comp_users[user]['x'].append((filename_date - min_date).days)
                comp_users[user]['y'].append(counts[user])

    # create the datasets (scatter and trend line) for all users to compare
    PLOT_COLORS = ('#00a3ce', '#fab040')
    datasets: list[dict[str, Any]] = []
    for user, color in zip(user_list, PLOT_COLORS):
        if len(comp_users[user]['x']) < 2:
            if len(user_list) > 1:
                return format_msg(
                    match,
                    'sorry, all users need at least 2 days of data',
                )
            else:
                return format_msg(
                    match,
                    f'sorry {esc(user)}, need at least 2 days of data',
                )

        point_data = {
            'label': f"{user}'s chats",
            'borderColor': color,
            # add alpha to the point fill color
            'backgroundColor': f'{color}69',
            'data': [
                {'x': x_i, 'y': y_i}
                for x_i, y_i in
                zip(comp_users[user]['x'], comp_users[user]['y'])
                if y_i
            ],
        }
        m, c = lin_regr(comp_users[user]['x'], comp_users[user]['y'])
        trend_data = {
            'borderColor': color,
            'type': 'line',
            'fill': False,
            'pointRadius': 0,
            'data': [
                {
                    'x': comp_users[user]['x'][0],
                    'y': m * comp_users[user]['x'][0] + c,
                },
                {
                    'x': comp_users[user]['x'][-1],
                    'y': m * comp_users[user]['x'][-1] + c,
                },
            ],
        }
        datasets.append(point_data)
        datasets.append(trend_data)

    # generate title checking if we are comparing users
    if len(user_list) > 1:
        title_user = "'s, ".join(user_list)
        title_user = f"{title_user}'s"
    else:
        title_user = f"{user_list[0]}'s"

    chart = {
        'type': 'scatter',
        'data': {
            'datasets': datasets,
        },
        'options': {
            'scales': {
                'xAxes': [{'ticks': {'callback': 'CALLBACK'}}],
                'yAxes': [{'ticks': {'beginAtZero': True, 'min': 0}}],
            },
            'title': {
                'display': True,
                'text': f'{title_user} chat in twitch.tv/{config.channel}',
            },
            'legend': {
                'labels': {'filter': 'FILTER'},
            },
        },
    }

    callback = (
        'x=>{'
        f'y=new Date({str(min_date)!r});'
        'y.setDate(x+y.getDate());return y.toISOString().slice(0,10)'
        '}'
    )
    # https://github.com/chartjs/Chart.js/issues/3189#issuecomment-528362213
    filter = (
        '(legendItem, chartData)=>{'
        '  return (chartData.datasets[legendItem.datasetIndex].label);'
        '}'
    )
    data = json.dumps(chart, separators=(',', ':'))
    data = data.replace('"CALLBACK"', callback)
    data = data.replace('"FILTER"', filter)

    post_data = {'chart': data}
    request = urllib.request.Request(
        'https://quickchart.io/chart/create',
        method='POST',
        data=json.dumps(post_data).encode(),
        headers={'Content-Type': 'application/json'},
    )
    resp = urllib.request.urlopen(request)
    contents = json.load(resp)
    user_esc = [esc(user) for user in user_list]
    if len(user_list) > 1:
        return format_msg(
            match,
            f'comparing {", ".join(user_esc)}: {contents["url"]}',
        )
    else:
        return format_msg(match, f'{esc(user_esc[0])}: {contents["url"]}')
