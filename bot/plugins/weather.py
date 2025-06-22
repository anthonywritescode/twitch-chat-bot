from __future__ import annotations

import re

import aiohttp

from bot.config import Config
from bot.data import command
from bot.data import esc
from bot.data import format_msg
from bot.message import Message


ZIP_PLACE_RE = re.compile(r'^\d{4,5}(?:,?\w+)?', re.ASCII)


def c2f(celsius: float) -> float:
    return celsius * 9 / 5 + 32


def wind_dir_name_from_deg(wind_dir: float) -> str:
    wind_dir_names = (
        'N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW',
        'WSW', 'W', 'WNW', 'NW', 'NNW', 'N',
    )
    degrees_per_class = 360 / len(wind_dir_names)
    idx = int((wind_dir + degrees_per_class / 2) / degrees_per_class)
    name = wind_dir_names[idx]
    return name


@command('!weather', secret=True)
async def cmd_aqi(config: Config, msg: Message) -> str:
    _, _, rest = msg.msg.partition(' ')
    if rest:
        m = ZIP_PLACE_RE.match(rest)
        if not m:
            return format_msg(
                msg,
                '(invalid zip) usage: !weather [ZIP_CODE],[COUNTRY_CODE?]',
            )
        zip_code = m.string
    else:
        zip_code = '48105,US'

    geocoding_url = 'http://api.openweathermap.org/geo/1.0/zip'
    weather_url = 'https://api.openweathermap.org/data/2.5/weather'
    geocoding_params = {
        'zip': zip_code,
        'appid': config.openweathermap_api_key,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(geocoding_url, params=geocoding_params) as resp:
            geocoding_resp = await resp.json()

        lat, lon = geocoding_resp.get('lat'), geocoding_resp.get('lon')
        if lat is None or lon is None:
            return format_msg(msg, 'Did not find this place...')

        weather_params = {
            'lon': lon,
            'lat': lat,
            'appid': config.openweathermap_api_key,
        }
        async with session.get(weather_url, params=weather_params) as resp:
            json_resp = await resp.json()

    # need to convert from Kelvin
    temp_c = json_resp['main']['temp'] - 273.15
    feels_like_c = json_resp['main']['feels_like'] - 273.15
    wind_speed = json_resp['wind']['speed']
    description = json_resp['weather'][0]['main'].lower()
    wind_speed = json_resp['wind']['speed']
    wind_dir = json_resp['wind']['deg']
    wind_dir_name = wind_dir_name_from_deg(wind_dir)
    air_press = json_resp['main']['sea_level']
    humidity = json_resp['main']['humidity']
    visibility = json_resp['visibility']
    place = geocoding_resp['name']
    country = geocoding_resp['country']
    text = (
        f'The current weather in {esc(place)}, {esc(country)} is '
        f'{esc(description)} with a temperature of {temp_c:.1f} °C '
        f'({c2f(temp_c):.1f} °F) '
        f'and a feels-like temperature of {feels_like_c:.1f} °C '
        f'({c2f(feels_like_c):.1f}° F). '
        f'The wind speed is {wind_speed:.1f} m/s '
        f'({(wind_speed * 2.236936):.1f} mph) coming from {wind_dir:.0f}° '
        f'({wind_dir_name}). '
        f'The air pressure is at {air_press:.0f} hPa with a humidity '
        f'level of {humidity:.0f}% and the visibility is {visibility} m '
        f'({(visibility * 3.28084):.0f} ft). '
    )
    return format_msg(msg, text)
