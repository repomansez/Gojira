# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Hitalo M. <https://github.com/HitaloM>

import asyncio
import random
import re
from contextlib import suppress

import aiohttp
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineQuery, InlineQueryResult, InlineQueryResultPhoto
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from gojira import bot
from gojira.utils.graphql import ANILIST_API, ANIME_GET, ANIME_SEARCH

router = Router(name="anime_inline")


@router.inline_query(F.query.regexp(r"^!a (?P<query>.+)").as_("match"))
async def anime_inline(inline: InlineQuery, match: re.Match[str]):
    query = match.group("query")

    results: list[InlineQueryResult] = []

    search_results = []
    async with aiohttp.ClientSession() as client:
        if not query.isdecimal():
            response = await client.post(
                url=ANILIST_API,
                json={
                    "query": ANIME_SEARCH,
                    "variables": {
                        "per_page": 15,
                        "search": query,
                    },
                },
            )
            if not response:
                await asyncio.sleep(0.5)
                response = await client.post(
                    url=ANILIST_API,
                    json={
                        "query": ANIME_SEARCH,
                        "variables": {
                            "per_page": 10,
                            "search": query,
                        },
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )

            data = await response.json()
            search_results = data["data"]["Page"]["media"]

        if not search_results:
            return

        for result in search_results:
            response = await client.post(
                url=ANILIST_API,
                json={
                    "query": ANIME_GET,
                    "variables": {
                        "id": result["id"],
                    },
                },
            )
            data = await response.json()
            anime = data["data"]["Page"]["media"][0]

            if not anime:
                continue

            photo: str = ""
            if anime["bannerImage"]:
                photo = anime["bannerImage"]
            elif anime["coverImage"]:
                if anime["coverImage"]["extraLarge"]:
                    photo = anime["coverImage"]["extraLarge"]
                elif anime["coverImage"]["large"]:
                    photo = anime["coverImage"]["large"]
                elif anime["coverImage"]["medium"]:
                    photo = anime["coverImage"]["medium"]

            description: str = ""
            if anime["description"]:
                description = anime["description"]
                description = re.sub(re.compile(r"<.*?>"), "", description)
                description = description[0:260] + "..."

            studios = []
            producers = []
            for studio in anime["studios"]["nodes"]:
                if studio["isAnimationStudio"]:
                    studios.append(studio["name"])
                else:
                    producers.append(studio["name"])

            end_date_components = [
                component
                for component in (
                    anime["endDate"].get("day"),
                    anime["endDate"].get("month"),
                    anime["endDate"].get("year"),
                )
                if component is not None
            ]

            start_date_components = [
                component
                for component in (
                    anime["startDate"].get("day"),
                    anime["startDate"].get("month"),
                    anime["startDate"].get("year"),
                )
                if component is not None
            ]

            end_date = "/".join(str(component) for component in end_date_components)
            start_date = "/".join(str(component) for component in start_date_components)

            text = f"<b>{anime['title']['romaji']}</b>"
            if anime["title"]["native"]:
                text += f" (<code>{anime['title']['native']}</code>)"
            text += _("\n\n<b>ID</b>: <code>{id}</code> (<b>ANIME</b>)").format(id=anime["id"])
            if anime["format"]:
                text += _("\n<b>Format</b>: <code>{format}</code>").format(format=anime["format"])
            if anime["format"] != "MOVIE" and anime["episodes"]:
                text += _("\n<b>Episodes</b>: <code>{episodes}</code>").format(
                    episodes=anime["episodes"]
                )
            if anime["duration"]:
                text += _("\n<b>Episode Duration</b>: <code>{duration} mins</code>").format(
                    duration=anime["duration"]
                )
            text += _("\n<b>Status</b>: <code>{status}</code>").format(
                status=anime["status"].capitalize()
            )
            if anime["status"] != "NOT_YET_RELEASED":
                text += _("\n<b>Start Date</b>: <code>{date}</code>").format(date=start_date)
            if anime["status"] not in ["NOT_YET_RELEASED", "RELEASING"]:
                text += _("\n<b>End Date</b>: <code>{date}</code>").format(date=end_date)
            if anime["season"]:
                season = f"{anime['season'].capitalize()} {anime['seasonYear']}"
                text += _("\n<b>Season</b>: <code>{season}</code>").format(season=season)
            if anime["averageScore"]:
                text += _("\n<b>Average Score</b>: <code>{score}</code>").format(
                    score=anime["averageScore"]
                )
            if anime["studios"] and len(anime["studios"]["nodes"]) > 0:
                text += _("\n<b>Studios</b>: <code>{studios}</code>").format(
                    studios=", ".join(studios)
                )
            if len(producers) > 0:
                text += _("\n<b>Producers</b>: <code>{producers}</code>").format(
                    producers=", ".join(producers)
                )
            if anime["source"]:
                text += _("\n<b>Source</b>: <code>{source}</code>").format(
                    source=anime["source"].capitalize()
                )
            if anime["genres"]:
                text += _("\n<b>Genres</b>: <code>{genres}</code>").format(
                    genres=", ".join(anime["genres"])
                )

            text += _("\n\n<b>Short Description</b>: <i>{description}</i>").format(
                description=description
            )

            keyboard = InlineKeyboardBuilder()

            me = await bot.get_me()
            bot_username = me.username
            keyboard.button(
                text=_("👓 View More"),
                url=f"https://t.me/{bot_username}/?start=anime_{anime['id']}",
            )

            anime_format = "| " + anime["format"] if anime["format"] else None

            results.append(
                InlineQueryResultPhoto(
                    type="photo",
                    id=str(random.getrandbits(64)),
                    photo_url=photo,
                    thumb_url=photo,
                    title=f"{anime['title']['romaji']} {anime_format}",
                    description=description,
                    caption=text,
                    reply_markup=keyboard.as_markup(),
                )
            )

    with suppress(TelegramBadRequest):
        if len(results) > 0:
            await inline.answer(
                results=results,
                is_personal=True,
                cache_time=6,
            )