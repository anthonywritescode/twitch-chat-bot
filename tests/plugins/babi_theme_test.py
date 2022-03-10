from __future__ import annotations

import pytest

from bot.plugins.babi_theme import json_with_comments
from bot.plugins.babi_theme import safe_ish_plist_loads


def test_json_with_comments_basic():
    assert json_with_comments(b'{}') == {}


def test_json_with_comments_removes_inline_comment():
    s = b'''\
{
    "//foo": "bar" // baz
}
'''
    assert json_with_comments(s) == {'//foo': 'bar'}


def test_json_with_comments_removes_inline_trailing_comma():
    s = b'["a,],}",]'
    assert json_with_comments(s) == ['a,],}']


def test_json_with_comments_removes_non_inline_trailing_comma():
    s = b'''
{
    "foo,],}": "bar,],}", // hello ,],}
}
'''
    assert json_with_comments(s) == {'foo,],}': 'bar,],}'}


def test_plist_loads_works():
    src = b'''\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>hello</key>
    <string>world</string>
</dict>
</plist>
'''  # noqa: E501
    assert safe_ish_plist_loads(src) == {'hello': 'world'}


def test_plist_loads_ignores_entities():
    src = b'''\
<?xml version="1.0"?>
<!DOCTYPE lolz [
<!ENTITY lol "lol">
<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
<!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
<!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
<!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
<!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
<!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
<!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
]>
<lolz>&lol9;</lolz>
'''
    with pytest.raises(ValueError):
        safe_ish_plist_loads(src)
