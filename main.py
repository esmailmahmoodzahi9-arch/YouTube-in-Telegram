import asyncio
import os
import time
import yt_dlp

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart

# ================= TOKEN =================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError("❌ TOKEN is missing in Railway Variables!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_state = {}
download_status = {}


# ================= MENU =================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 دانلود از یوتیوب", callback_data="download")],
        [InlineKeyboardButton(text="🔎 یوتیوب گردی", callback_data="browse")]
    ])


# ================= PROGRESS BAR =================
def bar(p):
    p = max(0, min(100, p))
    full = int(p / 10)
    return "▰" * full + "▱" * (10 - full)


def progress_hook(d):
    if d['status'] == 'downloading':
        downloaded = d.get('downloaded_bytes', 0)
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 1)

        percent = int(downloaded * 100 / total)
        download_status["percent"] = percent


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 سلام!\nبه ربات حرفه‌ای یوتیوب خوش آمدی",
        reply_markup=main_menu()
    )


# ================= MENU HANDLER =================
@dp.callback_query()
async def menu(call: types.CallbackQuery):
    await call.answer()

    if call.data == "download":
        user_state[call.from_user.id] = {"mode": "download"}
        await call.message.answer("📥 لینک یوتیوب رو بفرست")

    elif call.data == "browse":
        user_state[call.from_user.id] = {"mode": "browse"}
        await call.message.answer("🔎 اسم ویدیو یا کانال رو بفرست")

    elif call.data == "home":
        await call.message.answer("🏠 منو اصلی", reply_markup=main_menu())


# ================= TEXT =================
@dp.message(F.text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_state.get(uid, {})

    # ---------- DOWNLOAD MODE ----------
    if state.get("mode") == "download" and (
        "youtube.com" in text or "youtu.be" in text
    ):
        user_state[uid]["url"] = text

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 دانلود آهنگ (MP3)", callback_data="mp3")],
            [InlineKeyboardButton(text="🎬 انتخاب کیفیت ویدیو", callback_data="mp4")],
            [InlineKeyboardButton(text="🏠 منو", callback_data="home")]
        ])

        await message.answer("یکی رو انتخاب کن:", reply_markup=kb)
        return

    # ---------- BROWSE MODE ----------
    if state.get("mode") == "browse":

        await message.answer("🔎 در حال جستجو...")

        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "default_search": "ytsearch10"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(text, download=False)

        entries = info.get("entries", [])

        kb = InlineKeyboardMarkup(inline_keyboard=[])

        for e in entries[:6]:
            if not e.get("id"):
                continue

            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=e.get("title", "video"),
                    callback_data=f"video|{e['id']}"
                )
            ])

        await message.answer("📺 نتایج:", reply_markup=kb)


# ================= VIDEO SELECT =================
@dp.callback_query(F.data.startswith("video|"))
async def select_video(call: types.CallbackQuery):
    await call.answer()

    video_id = call.data.split("|")[1]
    url = f"https://www.youtube.com/watch?v={video_id}"

    user_state[call.from_user.id] = {"mode": "download", "url": url}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 MP3", callback_data="mp3")],
        [InlineKeyboardButton(text="🎬 انتخاب کیفیت", callback_data="mp4")]
    ])

    await call.message.answer("یکی رو انتخاب کن:", reply_markup=kb)


# ================= GET FORMATS =================
def get_formats(url):
    ydl_opts = {"quiet": True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []

    for f in info.get("formats", []):
        if f.get("vcodec") != "none" and f.get("height") in [360, 720, 1080]:
            formats.append({
                "format_id": f["format_id"],
                "height": f.get("height")
            })

    return formats


# ================= QUALITY MENU =================
@dp.callback_query(F.data == "mp4")
async def show_quality(call: types.CallbackQuery):
    uid = call.from_user.id
    url = user_state.get(uid, {}).get("url")

    if not url:
        await call.message.answer("❌ لینک پیدا نشد")
        return

    formats = get_formats(url)

    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for f in formats:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🎬 {f['height']}p",
                callback_data=f"q|{f['format_id']}|{url}"
            )
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 منو", callback_data="home")
    ])

    await call.message.answer("🎥 کیفیت رو انتخاب کن:", reply_markup=kb)


# ================= DOWNLOAD QUALITY =================
@dp.callback_query(F.data.startswith("q|"))
async def download_quality(call: types.CallbackQuery):
    await call.answer()

    _, format_id, url = call.data.split("|")

    msg = await call.message.answer("⬇️ شروع دانلود...\n▱▱▱▱▱▱▱▱▱▱ 0%")

    download_status["percent"] = 0

    async def update_progress():
        last = 0

        while True:
            p = download_status.get("percent", 0)

            if time.time() - last > 1:
                try:
                    await msg.edit_text(f"⬇️ در حال دانلود...\n{bar(p)} {p}%")
                    last = time.time()
                except:
                    pass

            if p >= 100:
                break

            await asyncio.sleep(1)

    task = asyncio.create_task(update_progress())

    def run():
        ydl_opts = {
            "format": format_id,
            "outtmpl": "video.%(ext)s",
            "progress_hooks": [progress_hook]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    file_path = await asyncio.to_thread(run)

    task.cancel()

    await msg.edit_text("📤 در حال ارسال فایل...")

    await call.message.answer_video(types.FSInputFile(file_path))

    await call.message.answer("🏠 منو:", reply_markup=main_menu())


# ================= MP3 =================
@dp.callback_query(F.data == "mp3")
async def mp3(call: types.CallbackQuery):
    url = user_state.get(call.from_user.id, {}).get("url")

    msg = await call.message.answer("⬇️ در حال ساخت MP3...\n▱▱▱▱▱▱▱▱▱▱ 0%")

    download_status["percent"] = 0

    async def update():
        last = 0
        while True:
            p = download_status.get("percent", 0)

            if time.time() - last > 1:
                try:
                    await msg.edit_text(f"⬇️ در حال دانلود...\n{bar(p)} {p}%")
                    last = time.time()
                except:
                    pass

            if p >= 100:
                break

            await asyncio.sleep(1)

    task = asyncio.create_task(update())

    def run():
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "audio.%(ext)s",
            "progress_hooks": [progress_hook],
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    file_path = await asyncio.to_thread(run)

    task.cancel()

    await msg.edit_text("📤 ارسال فایل...")

    await call.message.answer_audio(types.FSInputFile(file_path))

    await call.message.answer("🏠 منو:", reply_markup=main_menu())


# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
