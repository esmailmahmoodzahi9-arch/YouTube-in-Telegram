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
        [InlineKeyboardButton(text="🔎 جستجو", callback_data="search")],
        [InlineKeyboardButton(text="📥 دانلود لینک مستقیم", callback_data="download")]
    ])


# ================= YOUTUBE SEARCH (STABLE HTML) =================
async def search(query):
    url = f"https://www.youtube.com/results?search_query={query}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            html = await r.text()

    ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", html)

    return list(dict.fromkeys(ids))[:6]


# ================= EXTRACT ID =================
def extract_id(url):
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    if "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    return None


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("👋 ربات آماده است", reply_markup=menu())


# ================= MENU =================
@dp.callback_query(F.data.in_(["search", "download"]))
async def menu_handler(call: types.CallbackQuery):
    await call.answer()

    if call.data == "search":
        user_state[call.from_user.id] = {"mode": "search"}
        await call.message.answer("🔎 اسم ویدیو رو بفرست")

    if call.data == "download":
        user_state[call.from_user.id] = {"mode": "download"}
        await call.message.answer("📥 لینک مستقیم فایل رو بفرست (mp4/mp3 لینک مستقیم)")


# ================= TEXT =================
@dp.message(F.text)
async def handler(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_state.get(uid, {})

    # ---------- SEARCH ----------
    if state.get("mode") == "search":

        vids = await search(text)

        kb = InlineKeyboardMarkup(inline_keyboard=[])

        for v in vids:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🎬 {v}",
                    callback_data=f"vid|{v}"
                )
            ])

        await message.answer("📺 نتایج:", reply_markup=kb)


    # ---------- DOWNLOAD DIRECT LINK ----------
    elif state.get("mode") == "download":

        # اینجا فقط لینک مستقیم واقعی دانلود می‌گیره
        url = text

        if not url.startswith("http"):
            await message.answer("❌ لینک مستقیم نیست")
            return

        await message.answer("⬇️ در حال دانلود...")

        filename = f"file_{uid}.mp4"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as r:
                    with open(filename, "wb") as f:
                        while True:
                            chunk = await r.content.read(1024 * 512)
                            if not chunk:
                                break
                            f.write(chunk)

            await message.answer_video(types.FSInputFile(filename))

        except Exception as e:
            await message.answer(f"❌ خطا:\n{e}")


# ================= VIDEO BUTTON =================
@dp.callback_query(F.data.startswith("vid|"))
async def vid(call: types.CallbackQuery):
    await call.answer()

    vid = call.data.split("|")[1]

    await call.message.answer(
        "▶️ پخش مستقیم:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="▶️ باز کردن در یوتیوب",
                url=f"https://www.youtube.com/watch?v={vid}"
            )]
        ])
    )


# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
