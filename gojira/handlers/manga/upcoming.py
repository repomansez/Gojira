# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Hitalo M. <https://github.com/HitaloM>

from contextlib import suppress

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.i18n import gettext as _

from gojira import AniList
from gojira.utils.callback_data import (
    MangaCallback,
    MangaUpcomingCallback,
    StartCallback,
    UpcomingCallback,
)
from gojira.utils.keyboard import Pagination

router = Router(name="manga_upcoming")


@router.callback_query(MangaUpcomingCallback.filter())
async def manga_upcoming(callback: CallbackQuery, callback_data: MangaUpcomingCallback):
    message = callback.message
    if not message or not message.from_user:
        return

    page = callback_data.page
    user_id = callback_data.user_id

    if user_id != callback.from_user.id:
        await message.answer(
            _("This button is not for you."),
            show_alert=True,
            cache_time=60,
        )
        return

    is_private = message.chat.type == ChatType.PRIVATE

    status, data = await AniList.upcoming("manga")
    if data["data"]:
        items = data["data"]["Page"]["media"]
        suggestions = []
        for item in items:
            suggestions.append(item)

        layout = Pagination(
            suggestions,
            item_data=lambda i, pg: MangaCallback(
                query=int(i["id"]), is_search=(not is_private)
            ).pack(),
            item_title=lambda i, pg: i["title"]["romaji"],
            page_data=lambda pg: MangaUpcomingCallback(page=pg, user_id=user_id).pack(),
        )

        keyboard = layout.create(page, lines=8)

        if is_private:
            keyboard.row(
                InlineKeyboardButton(
                    text=_("🔙 Back"),
                    callback_data=StartCallback(menu="manga").pack(),
                )
            )
        else:
            keyboard.row(
                InlineKeyboardButton(
                    text=_("🔙 Back"),
                    callback_data=UpcomingCallback(user_id=user_id).pack(),
                )
            )

        with suppress(TelegramAPIError):
            await message.edit_text(
                _("Below are the <b>50</b> mangas that have not yet been released."),
                reply_markup=keyboard.as_markup(),
            )
