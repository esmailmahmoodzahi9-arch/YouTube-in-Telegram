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
    raise RuntimeError("TOKEN is missing in Railway Variables")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= STATE =================
user_state = {}
download_progress = {}


# ================= MENU =================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 دانلود از یوتیوب", callback_data="download")],
        [InlineKeyboardButton(text="🔎 یوتیوب گردی", callback_data="browse")]
    ])


# ================= PROGRESS BAR =================
def bar(p):
    p = max(0, min(100, p))
    return "▰" * (p // 10) + "▱" * (10 - (p // 10))


def progress_hook(d):
    if d.get("status") == "downloading":
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1

        percent = int(downloaded * 100 / total)
        download_progress["percent"] = percent


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 سلام!\nبه ربات دانلود یوتیوب خوش آمدی",
        reply_markup=menu()
    )


# ================= SAFE CALLBACK ROUTER =================
@dp.callback_query(F.data.in_(["download", "browse", "home"]))
async def router(call: types.CallbackQuery):
    await call.answer()

    if call.data == "download":
        user_state[call.from_user.id] = {"mode": "download"}
        await call.message.answer("📥 لینک یوتیوب رو بفرست")

    elif call.data == "browse":
        user_state[call.from_user.id] = {"mode": "browse"}
        await call.message.answer("🔎 اسم ویدیو رو بفرست")

    elif call.data == "home":
        await call.message.answer("🏠 منو اصلی", reply_markup=menu())


# ================= TEXT HANDLER =================
@dp.message(F.text)
async def text_handler(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_state.get(uid, {})

    # ---------- DOWNLOAD MODE ----------
    if state.get("mode") == "download":

        if "youtube.com" not in text and "youtu.be" not in text:
            await message.answer("❌ لینک معتبر نیست")
            return

        user_state[uid]["url"] = text

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 دانلود آهنگ", callback_data="mp3")],
            [InlineKeyboardButton(text="🎬 دانلود ویدیو", callback_data="mp4")],
            [InlineKeyboardButton(text="🏠 منو", callback_data="home")]
        ])

        await message.answer("یکی رو انتخاب کن:", reply_markup=kb)
        return


# ================= SAFE YT-DLP OPTIONS =================
def base_opts():
    return {
        "quiet": True,
        "nocheckcertificate": True,
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
        "progress_hooks": [progress_hook],
    }


# ================= VIDEO DOWNLOAD =================
@dp.callback_query(F.data == "mp4")
async def mp4(call: types.CallbackQuery):
    await call.answer()

    url = user_state.get(call.from_user.id, {}).get("url")

    if not url:
        await call.message.answer("❌ لینک پیدا نشد")
        return

    msg = await call.message.answer("⬇️ شروع دانلود...\n▱▱▱▱▱▱▱▱▱▱ 0%")

    download_progress["percent"] = 0

    async def updater():
        last = 0
        while True:
            p = download_progress.get("percent", 0)

            if time.time() - last > 1:
                try:
                    await msg.edit_text(f"⬇️ در حال دانلود...\n{bar(p)} {p}%")
                    last = time.time()
                except:
                    pass

            if p >= 100:
                break

            await asyncio.sleep(1)

    task = asyncio.create_task(updater())

    def run():
        opts = base_opts()
        opts["format"] = "best[height<=720]/best"
        opts["outtmpl"] = "video.%(ext)s"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    try:
        file_path = await asyncio.to_thread(run)

        task.cancel()

        await msg.edit_text("📤 در حال ارسال...")

        await call.message.answer_video(types.FSInputFile(file_path))

    except Exception as e:
        await call.message.answer(f"❌ خطا در دانلود:\n{e}")


# ================= MP3 DOWNLOAD =================
@dp.callback_query(F.data == "mp3")
async def mp3(call: types.CallbackQuery):
    await call.answer()

    url = user_state.get(call.from_user.id, {}).get("url")

    if not url:
        await call.message.answer("❌ لینک پیدا نشد")
        return

    msg = await call.message.answer("⬇️ ساخت MP3...\n▱▱▱▱▱▱▱▱▱▱ 0%")

    download_progress["percent"] = 0

    async def updater():
        last = 0
        while True:
            p = download_progress.get("percent", 0)

            if time.time() - last > 1:
                try:
                    await msg.edit_text(f"⬇️ در حال دانلود...\n{bar(p)} {p}%")
                    last = time.time()
                except:
                    pass

            if p >= 100:
                break

            await asyncio.sleep(1)

    task = asyncio.create_task(updater())

    def run():
        opts = base_opts()
        opts.update({
            "format": "bestaudio/best",
            "outtmpl": "audio.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    try:
        file_path = await asyncio.to_thread(run)

        task.cancel()

        await msg.edit_text("📤 در حال ارسال فایل...")

        await call.message.answer_audio(types.FSInputFile(file_path))

    except Exception as e:
        await call.message.answer(f"❌ خطا:\n{e}")


# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
