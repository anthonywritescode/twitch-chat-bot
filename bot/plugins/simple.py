import functools
from typing import Match
from typing import Tuple

from bot.config import Config
from bot.data import add_alias
from bot.data import command
from bot.data import format_msg


_TEXT_COMMANDS: Tuple[Tuple[str, str], ...] = (
    ('!bluething', 'it is a fidget toy: https://amzn.to/35PmPQr'),
    (
        '!bot',
        'I wrote the bot!  https://github.com/anthonywritescode/twitch-chat-bot',  # noqa: E501
    ),
    (
        '!discord',
        'We do have Discord, you are welcome to join: '
        'https://discord.gg/xDKGPaW',
    ),
    (
        '!distro',
        'awcActuallyWindows Windows 10 with Ubuntu 20.04 LTS virtual machine, '
        'more info here: https://www.youtube.com/watch?v=8KdAqlESQJo',
    ),
    (
        '!donate',
        "donations are appreciated but not necessary -- if you'd like to "
        'donate, you can donate at https://streamlabs.com/anthonywritescode',
    ),
    (
        '!editor',
        'awcBabi this is my text editor I made, called babi! '
        'https://github.com/asottile/babi '
        'more info in this video: https://www.youtube.com/watch?v=WyR1hAGmR3g',
    ),
    (
        '!emotes',
        'awcDumpsterFire awcPythonk awcHelloHello awcKeebL awcKeebR '
        'awcPreCommit awcBabi awcFLogo awcCarpet awcActuallyWindows',
    ),
    (
        '!github',
        "anthony's github is https://github.com/asottile -- stream github is "
        'https://github.com/anthonywritescode',
    ),
    ('!homeland', 'WE WILL PROTECT OUR HOMELAND!'),
    (
        '!keyboard',
        'either '
        '(normal) code v3 87-key (cherry mx clears) '
        '(contributed by PhillipWei): https://amzn.to/3jzmwh3 '
        'or '
        '(split) awcKeebL awcKeebR kinesis freestyle pro (cherry mx reds) '
        'https://amzn.to/3jyN4PC (faq: https://youtu.be/DZgCUWf9DZM)',
    ),
    (
        '!keyboard2',
        'this is my second mechanical keyboard: '
        'https://i.fluffy.cc/CDtRzWX1JZTbqzKswHrZsF7HPX2zfLL1.png',
    ),
    (
        '!keyboard3',
        'this is my stream deck keyboard (cherry mx black silent): '
        'https://keeb.io/products/bdn9-3x3-9-key-macropad-rotary-encoder-support '  # noqa: E501
        'here is more info: https://www.youtube.com/watch?v=p2TyRIAxR48',
    ),
    ('!levelup', 'https://i.imgur.com/Uoq5vGx.gif'),
    ('!lurk', 'thanks for lurking, {user}!'),
    ('!ohai', 'ohai, {user}!'),
    ('!playlist', 'HearWeGo: https://www.youtube.com/playlist?list=PL44UysF4ZQ23B_ITIqM8Fqt1UXgsA9yD6'),  # noqa: E501
    (
        '!theme',
        'awcBabi this is vs dark plus in !babi with one modification to '
        'highlight ini headers: '
        'https://github.com/asottile/babi#setting-up-syntax-highlighting',
    ),
    ('!twitter', 'https://twitter.com/codewithanthony'),
    ('!water', 'DRINK WATER, BITCH'),
    ('!youtube', 'https://youtube.com/anthonywritescode'),
)


async def _generic_msg(config: Config, match: Match[str], *, msg: str) -> str:
    return format_msg(match, msg)


for _cmd, _msg in _TEXT_COMMANDS:
    command(_cmd)(functools.partial(_generic_msg, msg=_msg))


_ALIASES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ('!bluething', ('!blueball',)),
    ('!distro', ('!os',)),
    (
        '!editor', (
            '!babi',
            '!nano',
            '!vim',
            '!emacs',
            '!vscode',
            '!wheredobabiscomefrom',
        ),
    ),
    ('!emotes', ('!emoji', '!emote')),
)
for _alias_name, _aliases in _ALIASES:
    add_alias(_alias_name, *_aliases)
