import asyncio
import aiohttp
import os
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_state = {}


# ================= MENU =================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 دانلود یوتیوب", callback_data="download")],
        [InlineKeyboardButton(text="🔎 جستجو", callback_data="search")]
    ])


# ================= EXTRACT ID =================
def extract_id(url):
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    if "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    return None


# ================= SEARCH (Piped API - STABLE) =================
async def search(query):
    url = f"https://pipedapi.kavin.rocks/search?q={query}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            data = await r.json()

    return data.get("items", [])[:6]


# ================= VIDEO INFO =================
async def video_info(video_id):
    url = f"https://pipedapi.kavin.rocks/streams/{video_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            return await r.json()


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("👋 ربات فعال شد", reply_markup=menu())


# ================= MENU =================
@dp.callback_query(F.data.in_(["download", "search"]))
async def menu_handler(call: types.CallbackQuery):
    await call.answer()

    if call.data == "search":
        user_state[call.from_user.id] = {"mode": "search"}
        await call.message.answer("🔎 اسم ویدیو رو بفرست")

    elif call.data == "download":
        user_state[call.from_user.id] = {"mode": "download"}
        await call.message.answer("📥 لینک یوتیوب رو بفرست")


# ================= TEXT =================
@dp.message(F.text)
async def handler(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_state.get(uid, {})

    # ---------- SEARCH ----------
    if state.get("mode") == "search":

        results = await search(text)

        kb = InlineKeyboardMarkup(inline_keyboard=[])

        for v in results:
            vid = v.get("url", "").split("v=")[-1] if v.get("url") else v.get("id")

            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=v.get("title", "video")[:40],
                    callback_data=f"vid|{vid}"
                )
            ])

        await message.answer("📺 نتایج:", reply_markup=kb)


    # ---------- DOWNLOAD ----------
    elif state.get("mode") == "download":

        vid = extract_id(text)

        if not vid:
            await message.answer("❌ لینک اشتباهه")
            return

        data = await video_info(vid)

        formats = data.get("videoStreams", [])
        audio = data.get("audioStreams", [])

        kb = InlineKeyboardMarkup(inline_keyboard=[])

        # ================= VIDEO QUALITIES =================
        seen = set()

        for f in formats:
            q = f.get("quality")
            url = f.get("url")

            if q and url and q not in seen:
                seen.add(q)

                kb.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=f"🎬 دانلود {q}",
                        callback_data=f"vdl|{vid}|{q}"
                    )
                ])

        # ================= AUDIO =================
        if audio:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text="🎵 دانلود آهنگ",
                    callback_data=f"adl|{vid}"
                )
            ])

        kb.inline_keyboard.append([
            InlineKeyboardButton(text="🏠 منو", callback_data="home")
        ])

        await message.answer("👇 انتخاب کن:", reply_markup=kb)


# ================= VIDEO DOWNLOAD =================
@dp.callback_query(F.data.startswith("vdl|"))
async def video_dl(call: types.CallbackQuery):
    await call.answer()

    _, vid, quality = call.data.split("|")

    data = await video_info(vid)

    url = None

    for f in data.get("videoStreams", []):
        if f.get("quality") == quality:
            url = f.get("url")
            break

    if not url:
        await call.message.answer("❌ کیفیت پیدا نشد")
        return

    await call.message.answer_video(types.FSInputFile(url))


# ================= AUDIO DOWNLOAD =================
@dp.callback_query(F.data.startswith("adl|"))
async def audio_dl(call: types.CallbackQuery):
    await call.answer()

    vid = call.data.split("|")[1]

    data = await video_info(vid)

    audio = data.get("audioStreams", [])

    if not audio:
        await call.message.answer("❌ صوت پیدا نشد")
        return

    url = audio[0]["url"]

    await call.message.answer_audio(types.FSInputFile(url))


# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
