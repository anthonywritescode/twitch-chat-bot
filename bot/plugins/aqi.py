import re
from typing import Match
from typing import Optional

import aiohttp

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import MessageResponse

ZIP_CODE_RE = re.compile(r'^\d{5}$', re.ASCII)


class AQIResponse(MessageResponse):
    def __init__(self, match: Match[str], zip_code: str) -> None:
        super().__init__(match, '')
        self.zip_code = zip_code

    async def __call__(self, config: Config) -> Optional[str]:
        params = {
            'format': 'application/json',
            'zipCode': self.zip_code,
            'API_KEY': config.airnow_api_key,
        }
        url = 'https://www.airnowapi.org/aq/observation/zipCode/current/'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                json_resp = await resp.json()
                pm_25 = [d for d in json_resp if d['ParameterName'] == 'PM2.5']
                if not pm_25:
                    self.msg_fmt = 'No PM2.5 info -- is this a US zip code?'
                else:
                    data, = pm_25
                    self.msg_fmt = (
                        f'Current AQI ({esc(data["ParameterName"])}) in '
                        f'{esc(data["ReportingArea"])}, '
                        f'{esc(data["StateCode"])}: '
                        f'{esc(str(data["AQI"]))} '
                        f'({esc(data["Category"]["Name"])})'
                    )
                return await super().__call__(config)


@command('!aqi')
def cmd_aq(match: Match[str]) -> MessageResponse:
    _, _, rest = match['msg'].partition(' ')
    if rest:
        zip_code = rest.split()[0]
        if not ZIP_CODE_RE.match(zip_code):
            return MessageResponse(
                match, '(invalid zip) usage: !aqi [US_ZIP_CODE]',
            )
    else:
        zip_code = '94401'

    return AQIResponse(match, zip_code)
