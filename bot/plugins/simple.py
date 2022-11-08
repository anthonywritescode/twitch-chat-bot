from __future__ import annotations

import functools

from bot.config import Config
from bot.data import add_alias
from bot.data import command
from bot.data import format_msg
from bot.message import Message


_TEXT_COMMANDS: tuple[tuple[str, str], ...] = (
    (
        '!bot',
        'I wrote the bot!  https://github.com/anthonywritescode/twitch-chat-bot',  # noqa: E501
    ),
    (
        '!discord',
        'We do have Dicsord, you are welcome to join: '
        'https://discord.gg/xDKGPaW',
    ),
    (
        '!distro',
        'awcActuallyWindows Windows 10 with Ubuntu 22.04 LTS virtual machine, '
        'more info here: https://www.youtube.com/watch?v=8KdAqlESQJo',
    ),
    (
        '!donate',
        "donations are appreciated but not necessary -- if you'd like to "
        'donate, you can donate at https://streamlabs.com/anthonywritescode',
    ),
    (
        '!emotes',
        'awcBongo awcUp awcDown awcCarpet awcBonk awcHug awcPaint awc7 '
        'awcHide awcFacepalm awcPythonk awcHelloHello awcPreCommit awcBabi '
        'awcNoodle0 awcNoodle1 awcNoodle2 awcKeebL awcKeebR '
        'awcActuallyWindows awcFLogo awcDumpsterFire',
    ),
    (
        '!github',
        "anthony's github is https://github.com/asottile -- stream github is "
        'https://github.com/anthonywritescode',
    ),
    (
        '!job',
        'I am a staff software engineer at sentry.io working on developer '
        'infrastructure!',
    ),
    (
        '!keyboard',
        'either '
        '(normal) code v3 87-key (cherry mx clears) '
        '(contributed by PhillipWei): https://amzn.to/3jzmwh3 '
        'or '
        '(split) awcKeebL awcKeebR kinesis freestyle pro (cherry mx reds) '
        'https://amzn.to/3jyN4PC (faq: https://youtu.be/DZgCUWf9DZM )',
    ),
    ('!lurk', 'thanks for lurking, {user}!'),
    ('!ohai', 'ohai, {user}!'),
    ('!playlist', 'HearWeGo: https://www.youtube.com/playlist?list=PL44UysF4ZQ23B_ITIqM8Fqt1UXgsA9yD6'),  # noqa: E501
    (
        '!readme',
        'GitHub recently posted a blog post about me: '
        'https://github.com/readme/stories/anthony-sottile',
    ),
    (
        '!support',
        'Here are the great ways to support my content: '
        'https://github.com/asottile/asottile/blob/HEAD/supporting.md',
    ),
    ('!twitter', 'https://twitter.com/codewithanthony'),
    (
        '!youtube',
        'https://youtube.com/anthonywritescode -- '
        'stream vods: https://youtube.com/@anthonywritescode-vods',
    ),
)

_SECRET_COMMANDS = (
    (
        '!aoc',
        'advent of code is a series of puzzles which come out daily as an '
        'advent calendar in december -- for more information watch this '
        'wideo: https://youtu.be/QAwQ8eKBpYw',
    ),
    ('!bluething', 'it is a fidget toy: https://amzn.to/35PmPQr'),
    (
        '!copilot',
        'Quick TLDR of my thoughts on Github copilot: '
        'https://clips.twitch.tv/AntediluvianCloudyDotterelSquadGoals-EnFRoJsDEnEF_IjI',  # noqa: E501
    ),
    ('!chair', 'https://amzn.to/3zMzdPu'),
    (
        '!deadsnakes',
        'I maintain deadsnakes!  I backport and forward port pythons: '
        'https://github.com/deadsnakes -- '
        'see also https://youtu.be/Xe40amojaXE',
    ),
    (
        '!flake8',
        'I am the current primary maintainer of flake8!  '
        'https://github.com/pycqa/flake8',
    ),
    ('!homeland', 'WE WILL PROTECT OUR HOMELAND!'),
    (
        '!keyboard2',
        'this is my second mechanical keyboard: '
        'https://i.fluffy.cc/CDtRzWX1JZTbqzKswHrZsF7HPX2zfLL1.png '
        'here is more info: https://youtu.be/rBngGyWCV-4',
    ),
    (
        '!keyboard3',
        'this is my stream deck keyboard (cherry mx black silent): '
        'https://keeb.io/products/bdn9-3x3-9-key-macropad-rotary-encoder-support '  # noqa: E501
        'here is more info: https://www.youtube.com/watch?v=p2TyRIAxR48',
    ),
    ('!levelup', 'https://i.imgur.com/Uoq5vGx.gif'),
    (
        '!overlay',
        'https://github.com/anthonywritescode/data-url-twitch-overlays',
    ),
    (
        '!pre-commit',
        'I created pre-commit!  https://pre-commit.com and '
        'https://pre-commit.ci',
    ),
    ('!precommit', "it's spelled !pre-commit awcBongo"),
    (
        '!pytest',
        'yep, I am one of the pytest core devs '
        'https://github.com/pytest-dev/pytest',
    ),
    (
        '!question',
        '"udp your questions, don\'t tcp your questions" - marsha_socks',
    ),
    (
        '!rebase',
        'https://clips.twitch.tv/HonestCrowdedGalagoStoneLightning-khp2n3Fqvo0Wdpno',  # noqa: E501
    ),
    (
        '!schedule',
        'Monday evenings and Saturday at noon (EST) - '
        'Check !twitter and !dicsord for more, or see the google calendar '
        'link below the stream video.',
    ),
    ('!speechless', 'Good code changed like a ghost.Garbage.'),
    ('!tox', 'yep, I am a tox core dev https://github.com/tox-dev/tox'),
    ('!water', 'DRINK WATER, BITCH'),
    (
        '!wm',
        'the anthony window manager '
        'https://clips.twitch.tv/RefinedFunnyRavenFailFish',
    ),
)


async def _generic_msg(config: Config, msg: Message, *, s: str) -> str:
    return format_msg(msg, s)


for _cmd, _msg in _TEXT_COMMANDS:
    command(_cmd)(functools.partial(_generic_msg, s=_msg))
for _cmd, _msg in _SECRET_COMMANDS:
    command(_cmd, secret=True)(functools.partial(_generic_msg, s=_msg))


_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('!bluething', ('!blueball',)),
    ('!discord', ('!dicsord',)),
    ('!distro', ('!linux', '!os', '!ubuntu', '!vm', '!windows')),
    ('!emotes', ('!emoji', '!emote')),
    ('!job', ('!jorb',)),
    ('!keyboard', ('!keyboard1',)),
    ('!question', ('!ask', '!questions', '!tcp', '!udp')),
    ('!readme', ('!reamde',)),
    ('!speechless', ('!ghost',)),
    ('!youtube', ('!yt',)),
)
for _alias_name, _aliases in _ALIASES:
    add_alias(_alias_name, *_aliases)
