import asyncio
import aiohttp
import os
import time
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart

# ================= TOKEN =================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError("TOKEN is missing")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= INVIDIOUS SERVERS =================
SERVERS = [
    "https://inv.nadeko.net",
    "https://invidious.privacydev.net",
    "https://iv.ggtyler.dev"
]

# ================= CACHE =================
CACHE = {}  # video_id -> (data, time)
CACHE_TIME = 60 * 30  # 30 min

user_state = {}

# ================= HELPERS =================

def extract_video_id(url: str):
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{6,})", url)
    return match.group(1) if match else None


async def get_server():
    async with aiohttp.ClientSession() as session:
        for s in SERVERS:
            try:
                async with session.get(f"{s}/api/v1/stats", timeout=3) as r:
                    if r.status == 200:
                        return s
            except:
                continue
    return SERVERS[0]


async def api_get(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            return await r.json()


async def search(query):
    server = await get_server()
    return await api_get(f"{server}/api/v1/search?q={query}")


async def get_video(video_id):
    now = time.time()

    if video_id in CACHE:
        data, ts = CACHE[video_id]
        if now - ts < CACHE_TIME:
            return data

    server = await get_server()
    data = await api_get(f"{server}/api/v1/videos/{video_id}")

    CACHE[video_id] = (data, now)
    return data


async def download_file(url):
    filename = f"file_{int(time.time())}.mp4"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            with open(filename, "wb") as f:
                while True:
                    chunk = await r.content.read(1024 * 512)
                    if not chunk:
                        break
                    f.write(chunk)

    return filename


# ================= UI =================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 دانلود یوتیوب", callback_data="download")],
        [InlineKeyboardButton(text="🔎 جستجوی یوتیوب", callback_data="search")]
    ])


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 سلام!\nبه ربات دانلود یوتیوب خوش آمدی",
        reply_markup=main_menu()
    )


# ================= MENU =================
@dp.callback_query(F.data.in_(["download", "search", "home"]))
async def menu(call: types.CallbackQuery):
    await call.answer()

    if call.data == "download":
        user_state[call.from_user.id] = {"mode": "download"}
        await call.message.answer("📥 لینک ویدیو رو بفرست")

    elif call.data == "search":
        user_state[call.from_user.id] = {"mode": "search"}
        await call.message.answer("🔎 اسم ویدیو یا کانال رو بفرست")

    elif call.data == "home":
        await call.message.answer("🏠 منو", reply_markup=main_menu())


# ================= TEXT HANDLER =================
@dp.message(F.text)
async def handler(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_state.get(uid, {})

    # ---------- SEARCH ----------
    if state.get("mode") == "search":
        results = await search(text)

        kb = InlineKeyboardMarkup(inline_keyboard=[])

        for v in results[:6]:
            if v.get("videoId"):
                kb.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=v["title"][:40],
                        callback_data=f"vid|{v['videoId']}"
                    )
                ])

        await message.answer("📺 نتایج:", reply_markup=kb)


    # ---------- DOWNLOAD MODE ----------
    elif state.get("mode") == "download":

        video_id = extract_video_id(text)

        if not video_id:
            await message.answer("❌ لینک نامعتبره")
            return

        user_state[uid]["video_id"] = video_id

        data = await get_video(video_id)

        kb = InlineKeyboardMarkup(inline_keyboard=[])

        seen = set()

        for f in data.get("formats", []):
            h = f.get("height")
            fid = f.get("format_id")

            if h in [360, 720, 1080] and fid and h not in seen:
                seen.add(h)

                kb.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=f"🎬 {h}p",
                        callback_data=f"dl|{video_id}|{fid}"
                    )
                ])

        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="🎵 MP3",
                callback_data=f"mp3|{video_id}"
            )
        ])

        kb.inline_keyboard.append([
            InlineKeyboardButton(text="🏠 منو", callback_data="home")
        ])

        await message.answer("یکی رو انتخاب کن:", reply_markup=kb)


# ================= VIDEO DOWNLOAD =================
@dp.callback_query(F.data.startswith("dl|"))
async def download_video(call: types.CallbackQuery):
    await call.answer()

    _, video_id, format_id = call.data.split("|")

    data = await get_video(video_id)

    url = None

    for f in data.get("formats", []):
        if f.get("format_id") == format_id:
            url = f.get("url")
            break

    if not url:
        await call.message.answer("❌ لینک پیدا نشد")
        return

    msg = await call.message.answer("⬇️ دانلود شروع شد...")

    file_path = await download_file(url)

    await msg.edit_text("📤 در حال ارسال...")

    await call.message.answer_video(types.FSInputFile(file_path))

    try:
        os.remove(file_path)
    except:
        pass


# ================= MP3 DOWNLOAD =================
@dp.callback_query(F.data.startswith("mp3|"))
async def mp3(call: types.CallbackQuery):
    await call.answer()

    video_id = call.data.split("|")[1]

    data = await get_video(video_id)

    audio_url = None

    for f in data.get("adaptiveFormats", []):
        if f.get("mimeType", "").startswith("audio"):
            audio_url = f.get("url")
            break

    if not audio_url:
        await call.message.answer("❌ صوت پیدا نشد")
        return

    msg = await call.message.answer("⬇️ دانلود صوت...")

    file_path = await download_file(audio_url)

    await msg.edit_text("📤 ارسال...")

    await call.message.answer_audio(types.FSInputFile(file_path))

    try:
        os.remove(file_path)
    except:
        pass


# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
