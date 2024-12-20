# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Hitalo M. <https://github.com/HitaloM>

import math
import operator

import humanize
from aiogram import Router
from aiogram.enums import ChatType, InputMediaType
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InaccessibleMessage,
    InlineKeyboardButton,
    InputMediaPhoto,
    Message,
)
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder
from lxml import html

from gojira import AniList, bot
from gojira.handlers.anime.start import anime_start
from gojira.utils.callback_data import (
    AnimeAiringCallback,
    AnimeCallback,
    AnimeCharCallback,
    AnimeDescCallback,
    AnimeMoreCallback,
    AnimeStaffCallback,
    AnimeStudioCallback,
)
from gojira.utils.language import (
    i18n_anilist_format,
    i18n_anilist_season,
    i18n_anilist_source,
    i18n_anilist_status,
)

router = Router(name="anime_view")


@router.message(Command("anime"))
@router.callback_query(AnimeCallback.filter())
async def anime_view(
    union: Message | CallbackQuery,
    command: CommandObject | None = None,
    callback_data: AnimeCallback | None = None,
    anime_id: int | None = None,
    mal: bool = False,
):
    is_callback = isinstance(union, CallbackQuery)
    message = union.message if is_callback else union
    user = union.from_user
    if not message or not user:
        return

    if isinstance(message, InaccessibleMessage):
        return

    is_private: bool = message.chat.type == ChatType.PRIVATE

    if command and not command.args:
        if is_private:
            await anime_start(message)
            return
        await message.reply(
            _("You need to specify an anime. Use <code>/anime name</code> or <code>id</code>")
        )
        return

    query = str(
        callback_data.query
        if is_callback and callback_data is not None
        else command.args
        if command and command.args
        else anime_id
    )

    if is_callback and callback_data is not None:
        user_id = callback_data.user_id
        if user_id is not None:
            user_id = int(user_id)

            if user_id != user.id:
                await union.answer(
                    _("This button is not for you."),
                    show_alert=True,
                    cache_time=60,
                )
                return

        is_search = callback_data.is_search
        if is_search and not is_private:
            await message.delete()

    if not bool(query):
        return

    keyboard = InlineKeyboardBuilder()
    if not query.isdecimal():
        _status, data = await AniList.search("anime", query)
        if not data:
            await message.reply(_("No results found."))
            return

        results = data["data"]["Page"]["media"]
        if not results or len(results) == 0:
            await message.reply(_("No results found."))
            return

        if len(results) == 1:
            anime_id = int(results[0]["id"])
        else:
            for result in results:
                keyboard.row(
                    InlineKeyboardButton(
                        text=result["title"]["romaji"],
                        callback_data=AnimeCallback(
                            query=result["id"],
                            user_id=user.id,
                            is_search=True,
                        ).pack(),
                    )
                )
            await message.reply(
                _("Search results for: <b>{query}</b>").format(query=query),
                reply_markup=keyboard.as_markup(),
            )
            return
    else:
        anime_id = int(query)

    _status, data = await AniList.get("anime", anime_id, mal=mal)
    if not data:
        await message.reply(_("No results found."))
        return

    if not data["data"]["Page"]["media"]:
        await message.reply(_("No results found."))
        return

    anime = data["data"]["Page"]["media"][0]

    if not anime:
        await union.answer(
            _("No results found."),
            show_alert=True,
            cache_time=60,
        )
        return

    if "Hentai" in anime["genres"] or "Ecchi" in anime["genres"]:
        photo = f"https://play-lh.googleusercontent.com/KuM9arYZ6Oq2NzNDyyOK6Nk0ebMABOcQ8FxoMKT_CT2QOz7qMJYx_z7LmP5PZe5g08Q"
    else:
        photo = f"https://img.anili.st/media/{anime["id"]}"


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

    text = f"<b>{anime["title"]["romaji"]}</b>"
    if anime["title"]["native"]:
        text += f" (<code>{anime["title"]["native"]}</code>)"
    text += _("\n\n<b>ID</b>: <code>{id}</code>").format(id=anime["id"])
    if anime["format"]:
        text += _("\n<b>Format</b>: <code>{format}</code>").format(
            format=i18n_anilist_format(anime["format"])
        )
    if anime["format"] != "MOVIE" and anime["episodes"]:
        text += _("\n<b>Episodes</b>: <code>{episodes}</code>").format(episodes=anime["episodes"])
    if anime["duration"]:
        text += _("\n<b>Episode Duration</b>: <code>{duration} mins</code>").format(
            duration=anime["duration"]
        )
    text += _("\n<b>Status</b>: <code>{status}</code>").format(
        status=i18n_anilist_status(anime["status"])
    )
    if anime["status"] != "NOT_YET_RELEASED":
        text += _("\n<b>Start Date</b>: <code>{date}</code>").format(date=start_date)
    if anime["status"] not in {"NOT_YET_RELEASED", "RELEASING"}:
        text += _("\n<b>End Date</b>: <code>{date}</code>").format(date=end_date)
    if anime["season"]:
        season = f"{i18n_anilist_season(anime["season"])} {anime["seasonYear"]}"
        text += _("\n<b>Season</b>: <code>{season}</code>").format(season=season)
    if anime["averageScore"]:
        text += _("\n<b>Average Score</b>: <code>{score}</code>").format(
            score=anime["averageScore"]
        )
    if anime["studios"] and len(anime["studios"]["nodes"]) > 0:
        text += _("\n<b>Studios</b>: <code>{studios}</code>").format(studios=", ".join(studios))
    if len(producers) > 0:
        text += _("\n<b>Producers</b>: <code>{producers}</code>").format(
            producers=", ".join(producers)
        )
    if anime["source"]:
        text += _("\n<b>Source</b>: <code>{source}</code>").format(
            source=i18n_anilist_source(anime["source"])
        )
    if anime["genres"]:
        text += _("\n<b>Genres</b>: <code>{genres}</code>").format(
            genres=", ".join(anime["genres"])
        )

    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(
            text=_("👓 View More"),
            callback_data=AnimeMoreCallback(
                anime_id=anime["id"],
                user_id=user.id,
            ).pack(),
        )
    )

    if "relations" in anime and len(anime["relations"]["edges"]) > 0:
        relations_buttons = []
        for relation in anime["relations"]["edges"]:
            if relation["relationType"] in {"PREQUEL", "SEQUEL"}:
                button_text = (
                    _("➡️ Sequel") if relation["relationType"] == "SEQUEL" else _("⬅️ Prequel")
                )
                relations_buttons.append(
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=AnimeCallback(
                            query=relation["node"]["id"],
                            user_id=user.id,
                        ).pack(),
                    )
                )
        if len(relations_buttons) > 0:
            relations_buttons.sort(key=lambda button: button.text, reverse=True)
            keyboard.row(*relations_buttons)

    if bool(message.photo) and is_callback:
        await message.edit_media(
            InputMediaPhoto(type=InputMediaType.PHOTO, media=photo, caption=text),
            reply_markup=keyboard.as_markup(),
        )
        return
    if bool(message.photo) and not bool(message.via_bot):
        await message.edit_text(
            text,
            reply_markup=keyboard.as_markup(),
        )
        return

    await message.answer_photo(
        photo,
        caption=text,
        reply_markup=keyboard.as_markup(),
    )


@router.callback_query(AnimeMoreCallback.filter())
async def anime_more(callback: CallbackQuery, callback_data: AnimeMoreCallback):
    message = callback.message
    user = callback.from_user
    if not message:
        return

    if isinstance(message, InaccessibleMessage):
        return

    anime_id = callback_data.anime_id
    user_id = callback_data.user_id

    if user_id != user.id:
        await callback.answer(
            _("This button is not for you"),
            show_alert=True,
            cache_time=60,
        )
        return

    _status, data = await AniList.get_atrailer("anime", anime_id)
    anime = data["data"]["Page"]["media"][0]

    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text=_("📜 Description"),
        callback_data=AnimeDescCallback(anime_id=anime_id, user_id=user_id),
    )
    keyboard.button(
        text=_("👨‍👩‍👧‍👦 Characters"),
        callback_data=AnimeCharCallback(anime_id=anime_id, user_id=user_id),
    )
    keyboard.button(
        text=_("👨‍💻 Staff"),
        callback_data=AnimeStaffCallback(anime_id=anime_id, user_id=user_id),
    )
    keyboard.button(
        text=_("🌆 Studios"),
        callback_data=AnimeStudioCallback(anime_id=anime_id, user_id=user_id),
    )
    keyboard.button(
        text=_("📺 Airing"),
        callback_data=AnimeAiringCallback(query=anime_id, user_id=user_id),
    )

    if anime["trailer"]:
        trailer_site = anime["trailer"]["site"]
        trailer_id = anime["trailer"]["id"]
        trailer_url = (
            f"https://www.dailymotion.com/video/{trailer_id}"
            if trailer_site != "youtube"
            else f"https://youtu.be/{trailer_id}"
        )
        keyboard.button(text=_("🎦 Trailer"), url=trailer_url)

    keyboard.button(text=_("🐢 AniList"), url=anime["siteUrl"])
    keyboard.adjust(2)

    keyboard.row(
        InlineKeyboardButton(
            text=_("🔙 Back"),
            callback_data=AnimeCallback(
                query=anime_id,
                user_id=user.id,
            ).pack(),
        )
    )

    text = _(
        "Here you will be able to see the description, the characters, the team, and other \
things; make good use of it!"
    )

    await message.edit_caption(
        caption=text,
        reply_markup=keyboard.as_markup(),
    )


@router.callback_query(AnimeDescCallback.filter())
async def anime_description(callback: CallbackQuery, callback_data: AnimeDescCallback):
    message = callback.message
    user = callback.from_user
    if not message:
        return

    if isinstance(message, InaccessibleMessage):
        return

    anime_id = callback_data.anime_id
    user_id = callback_data.user_id
    page = callback_data.page

    if user_id != user.id:
        await callback.answer(
            _("This button is not for you"),
            show_alert=True,
            cache_time=60,
        )
        return

    _status, data = await AniList.get_adesc("anime", anime_id)
    anime = data["data"]["Page"]["media"][0]

    if not anime["description"]:
        await callback.answer(
            _("Oops! This anime has no description on AniList."),
            show_alert=True,
            cache_time=60,
        )
        return

    description = anime["description"]
    amount = 1024
    page = 1 if page <= 0 else page
    offset = (page - 1) * amount
    stop = offset + amount
    pages = math.ceil(len(description) / amount)
    description = description[offset - (3 if page > 1 else 0) : stop]

    page_buttons = []
    if page > 1:
        page_buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AnimeDescCallback(
                    anime_id=anime_id, user_id=user_id, page=page - 1
                ).pack(),
            )
        )

    if page != pages:
        description = description[: len(description) - 3] + "..."
        page_buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=AnimeDescCallback(
                    anime_id=anime_id, user_id=user_id, page=page + 1
                ).pack(),
            )
        )

    keyboard = InlineKeyboardBuilder()
    if len(page_buttons) > 0:
        keyboard.row(*page_buttons)

    keyboard.row(
        InlineKeyboardButton(
            text=_("🔙 Back"),
            callback_data=AnimeMoreCallback(
                anime_id=anime_id,
                user_id=user_id,
            ).pack(),
        )
    )

    parsed_html = html.fromstring(description.replace("<br>", ""))
    description = (
        str(html.tostring(parsed_html, encoding="unicode")).replace("<p>", "").replace("</p>", "")
    )

    await message.edit_caption(
        caption=description,
        reply_markup=keyboard.as_markup(),
    )


@router.callback_query(AnimeCharCallback.filter())
async def anime_characters(callback: CallbackQuery, callback_data: AnimeCharCallback):
    message = callback.message
    user = callback.from_user
    if not message:
        return

    if isinstance(message, InaccessibleMessage):
        return

    anime_id = callback_data.anime_id
    user_id = callback_data.user_id
    page = callback_data.page

    if user_id != user.id:
        await callback.answer(
            _("This button is not for you"),
            show_alert=True,
            cache_time=60,
        )
        return

    _status, data = await AniList.get_achars("anime", anime_id)
    anime = data["data"]["Page"]["media"][0]

    if not anime["characters"]:
        await callback.answer(
            _("Oops! This anime doesn't have a character list on AniList."),
            show_alert=True,
            cache_time=60,
        )
        return

    characters_text = ""
    characters = sorted(
        [
            {
                "id": character["node"]["id"],
                "name": character["node"]["name"],
                "role": character["role"],
            }
            for character in anime["characters"]["edges"]
        ],
        key=operator.itemgetter("id"),
    )

    me = await bot.get_me()
    for character in characters:
        characters_text += f"\n• <code>{character["id"]}</code> - <a href='https://t.me/\
{me.username}/?start=character_{character["id"]}'>{character["name"]["full"]}</a> \
(<i>{character["role"]}</i>)"

    characters_text = characters_text.split("\n")
    characters_text = [line for line in characters_text if line]
    characters_text = [characters_text[i : i + 8] for i in range(0, len(characters_text), 8)]

    pages = len(characters_text)

    page_buttons = []
    if page > 0:
        page_buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AnimeCharCallback(
                    anime_id=anime_id, user_id=user_id, page=page - 1
                ).pack(),
            )
        )
    if page + 1 != pages:
        page_buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=AnimeCharCallback(
                    anime_id=anime_id, user_id=user_id, page=page + 1
                ).pack(),
            )
        )

    characters_text = characters_text[page]
    characters_text = "\n".join(characters_text)

    keyboard = InlineKeyboardBuilder()
    if len(page_buttons) > 0:
        keyboard.add(*page_buttons)

    keyboard.row(
        InlineKeyboardButton(
            text=_("🔙 Back"),
            callback_data=AnimeMoreCallback(
                anime_id=anime_id,
                user_id=user_id,
            ).pack(),
        )
    )

    text = _("Below is the list of characters in this anime.")
    text = f"{text}\n\n{characters_text}"
    await message.edit_caption(
        caption=text,
        reply_markup=keyboard.as_markup(),
    )


@router.callback_query(AnimeStaffCallback.filter())
async def anime_staff(callback: CallbackQuery, callback_data: AnimeStaffCallback):
    message = callback.message
    user = callback.from_user
    if not message:
        return

    if isinstance(message, InaccessibleMessage):
        return

    anime_id = callback_data.anime_id
    user_id = callback_data.user_id
    page = callback_data.page

    if user_id != user.id:
        await callback.answer(
            _("This button is not for you"),
            show_alert=True,
            cache_time=60,
        )
        return

    _status, data = await AniList.get_astaff("anime", anime_id)
    anime = data["data"]["Page"]["media"][0]

    if not anime["staff"]:
        await callback.answer(
            _("This anime does not have staff."),
            show_alert=True,
            cache_time=60,
        )
        return

    staff_text = ""
    staffs = sorted(
        [
            {
                "id": staff["node"]["id"],
                "name": staff["node"]["name"],
                "role": staff["role"],
            }
            for staff in anime["staff"]["edges"]
        ],
        key=operator.itemgetter("id"),
    )

    me = await bot.get_me()
    for person in staffs:
        staff_text += f"\n• <code>{person["id"]}</code> - <a href='https://t.me/{me.username}/\
?start=staff_{person["id"]}'>{person["name"]["full"]}</a> (<i>{person["role"]}</i>)"

    staff_text = staff_text.split("\n")
    staff_text = [line for line in staff_text if line]
    staff_text = [staff_text[i : i + 8] for i in range(0, len(staff_text), 8)]

    pages = len(staff_text)

    page_buttons = []
    if page > 0:
        page_buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AnimeStaffCallback(
                    anime_id=anime_id, user_id=user_id, page=page - 1
                ).pack(),
            )
        )
    if page + 1 != pages:
        page_buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=AnimeStaffCallback(
                    anime_id=anime_id, user_id=user_id, page=page + 1
                ).pack(),
            )
        )

    staff_text = staff_text[page]
    staff_text = "\n".join(staff_text)

    keyboard = InlineKeyboardBuilder()
    if len(page_buttons) > 0:
        keyboard.add(*page_buttons)

    keyboard.row(
        InlineKeyboardButton(
            text=_("🔙 Back"),
            callback_data=AnimeMoreCallback(
                anime_id=anime_id,
                user_id=user_id,
            ).pack(),
        )
    )

    text = _("Below is a list of the team working on this anime.")
    text = f"{text}\n\n{staff_text}"
    await message.edit_caption(
        caption=text,
        reply_markup=keyboard.as_markup(),
    )


@router.message(Command("airing"))
@router.callback_query(AnimeAiringCallback.filter())
async def anime_airing(
    union: Message | CallbackQuery,
    command: CommandObject | None = None,
    callback_data: AnimeAiringCallback | None = None,
):
    is_callback = isinstance(union, CallbackQuery)
    message = union.message if is_callback else union
    user = union.from_user
    if not message or not user:
        return

    if isinstance(message, InaccessibleMessage):
        return

    is_private: bool = message.chat.type == ChatType.PRIVATE

    if command and not command.args:
        await message.reply(
            _("You need to specify an anime. Use <code>/airing name</code> or <code>id</code>")
        )
        return

    query = str(
        callback_data.query
        if is_callback and callback_data is not None
        else command.args
        if command and command.args
        else None
    )

    if is_callback and callback_data is not None:
        user_id = callback_data.user_id
        if user_id is not None:
            user_id = int(user_id)

            if user_id != user.id:
                await union.answer(
                    _("This button is not for you."),
                    show_alert=True,
                    cache_time=60,
                )
                return

        is_search = callback_data.is_search
        if is_search and not is_private:
            await message.delete()

    if not bool(query):
        return

    keyboard = InlineKeyboardBuilder()
    if not query.isdecimal():
        _status, data = await AniList.search("anime", query)
        if not data:
            await message.reply(_("No results found."))
            return

        results = data["data"]["Page"]["media"]
        if not results or len(results) == 0:
            await message.reply(_("No results found."))
            return

        if len(results) == 1:
            anime_id = int(results[0]["id"])
        else:
            for result in results:
                keyboard.row(
                    InlineKeyboardButton(
                        text=result["title"]["romaji"],
                        callback_data=AnimeAiringCallback(
                            query=result["id"],
                            user_id=user.id,
                            is_search=True,
                        ).pack(),
                    )
                )
            await message.reply(
                _("Search results for: <b>{query}</b>").format(query=query),
                reply_markup=keyboard.as_markup(),
            )
            return
    else:
        anime_id = int(query)

    _status, data = await AniList.get_airing(anime_id=anime_id)
    anime = data["data"]["Page"]["media"][0]

    text = _("See below when the next episode of the anime in question will air.\n\n")
    if anime["nextAiringEpisode"]:
        text += _("<b>Status:</b> <code>{status}</code>\n").format(
            status=i18n_anilist_status(anime["status"])
        )
        text += _("<b>Episode:</b> <code>{episode}</code>\n").format(
            episode=anime["nextAiringEpisode"]["episode"]
        )
        text += _("<b>Airing:</b> <code>{airing_time}</code>").format(
            airing_time=humanize.precisedelta(anime["nextAiringEpisode"]["timeUntilAiring"])
        )
    else:
        episodes = anime["episodes"] or "N/A"
        text += _("<b>Status:</b> <code>{status}</code>\n").format(
            status=i18n_anilist_status(anime["status"])
        )
        text += _("<b>Episodes:</b> <code>{episode}</code>\n").format(episode=episodes)

    external_links = anime["externalLinks"]
    buttons = [
        InlineKeyboardButton(text=link["site"], url=link["url"])
        for link in external_links
        if link["type"] == "STREAMING"
    ]

    keyboard = InlineKeyboardBuilder()
    if len(buttons) > 0:
        keyboard.row(*buttons)
        keyboard.adjust(3)

    if is_callback and callback_data and not callback_data.is_search:
        keyboard.row(
            InlineKeyboardButton(
                text=_("🔙 Back"),
                callback_data=AnimeMoreCallback(
                    anime_id=anime_id,
                    user_id=user.id,
                ).pack(),
            )
        )

    if message.photo and is_callback:
        await message.edit_caption(
            caption=text,
            reply_markup=keyboard.as_markup(),
        )
    else:
        await message.answer_photo(
            photo=f"https://img.anili.st/media/{anime_id}",
            caption=text,
            reply_markup=keyboard.as_markup(),
        )


@router.callback_query(AnimeStudioCallback.filter())
async def anime_studio(callback: CallbackQuery, callback_data: AnimeStudioCallback):
    message = callback.message
    user = callback.from_user
    if not message:
        return

    if isinstance(message, InaccessibleMessage):
        return

    anime_id = callback_data.anime_id
    user_id = callback_data.user_id
    page = callback_data.page

    if user_id != user.id:
        await callback.answer(
            _("This button is not for you"),
            show_alert=True,
            cache_time=60,
        )
        return

    _status, data = await AniList.get_astudios("anime", anime_id)
    studio = data["data"]["Page"]["media"][0]["studios"]["nodes"]

    if not studio:
        await callback.answer(
            _("This anime does not have studio."),
            show_alert=True,
            cache_time=60,
        )
        return

    me = await bot.get_me()
    studio_text = ""
    studios = sorted(studio, key=operator.itemgetter("name"))
    for studio in studios:
        studio_text += f"\n• <code>{studio["id"]}</code> - <a href='https://t.me/\
{me.username}/?start=studio_{studio["id"]}'>{studio["name"]}</a> \
{"(producer)" if not studio["isAnimationStudio"] else ""}"

    studio_text = studio_text.split("\n")
    studio_text = [line for line in studio_text if line]
    studio_text = [studio_text[i : i + 8] for i in range(0, len(studio_text), 8)]

    pages = len(studio_text)

    page_buttons = []
    if page > 0:
        page_buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AnimeStudioCallback(
                    anime_id=anime_id, user_id=user_id, page=page - 1
                ).pack(),
            )
        )
    if page + 1 != pages:
        page_buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=AnimeStudioCallback(
                    anime_id=anime_id, user_id=user_id, page=page + 1
                ).pack(),
            )
        )

    studio_text = studio_text[page]
    studio_text = "\n".join(studio_text)

    keyboard = InlineKeyboardBuilder()
    if len(page_buttons) > 0:
        keyboard.row(*page_buttons)
        keyboard.adjust(3)

    keyboard.row(
        InlineKeyboardButton(
            text=_("🔙 Back"),
            callback_data=AnimeMoreCallback(
                anime_id=anime_id,
                user_id=user_id,
            ).pack(),
        )
    )

    text = _("Below is a list of the studios working on this anime.")
    text = f"{text}\n\n{studio_text}"
    await message.edit_caption(
        caption=text,
        reply_markup=keyboard.as_markup(),
    )
