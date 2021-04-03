from __future__ import annotations

import re
from typing import Match

import aiohttp

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg

ZIP_CODE_RE = re.compile(r'^\d{5}$', re.ASCII)


@command('!aqi', secret=True)
async def cmd_aqi(config: Config, match: Match[str]) -> str:
    _, _, rest = match['msg'].partition(' ')
    if rest:
        zip_code = rest.split()[0]
        if not ZIP_CODE_RE.match(zip_code):
            return format_msg(match, '(invalid zip) usage: !aqi [US_ZIP_CODE]')
    else:
        zip_code = '94401'

    params = {
        'format': 'application/json',
        'zipCode': zip_code,
        'API_KEY': config.airnow_api_key,
    }
    url = 'https://www.airnowapi.org/aq/observation/zipCode/current/'
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            json_resp = await resp.json()
            pm_25 = [d for d in json_resp if d['ParameterName'] == 'PM2.5']
            if not pm_25:
                return format_msg(
                    match,
                    'No PM2.5 info -- is this a US zip code?',
                )
            else:
                data, = pm_25
                return format_msg(
                    match,
                    f'Current AQI ({esc(data["ParameterName"])}) in '
                    f'{esc(data["ReportingArea"])}, '
                    f'{esc(data["StateCode"])}: '
                    f'{esc(str(data["AQI"]))} '
                    f'({esc(data["Category"]["Name"])})',
                )
