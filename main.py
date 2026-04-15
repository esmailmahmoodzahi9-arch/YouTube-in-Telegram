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
    raise RuntimeError("TOKEN missing in environment variables")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================= STATE =================
user_state = {}
progress = {}


# ================= MENU =================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 دانلود یوتیوب", callback_data="download")],
        [InlineKeyboardButton(text="🔎 یوتیوب گردی", callback_data="browse")]
    ])


# ================= PROGRESS =================
def bar(p):
    p = max(0, min(100, p))
    return "▰" * (p // 10) + "▱" * (10 - (p // 10))


def progress_hook(d):
    if d.get("status") == "downloading":
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
        progress["percent"] = int(downloaded * 100 / total)


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 سلام!\nبه ربات دانلود یوتیوب خوش آمدی",
        reply_markup=menu()
    )


# ================= ROUTER =================
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
        await call.message.answer("🏠 منو", reply_markup=menu())


# ================= TEXT HANDLER =================
@dp.message(F.text)
async def text_handler(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_state.get(uid, {})

    if state.get("mode") == "download":

        if "youtube.com" not in text and "youtu.be" not in text:
            await message.answer("❌ لینک نامعتبره")
            return

        user_state[uid] = {
            "mode": "download",
            "url": text
        }

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 دانلود آهنگ", callback_data="mp3")],
            [InlineKeyboardButton(text="🎬 دانلود ویدیو (انتخاب کیفیت)", callback_data="mp4")],
            [InlineKeyboardButton(text="🏠 منو", callback_data="home")]
        ])

        await message.answer("یکی رو انتخاب کن:", reply_markup=kb)


# ================= GET FORMATS =================
def get_formats(url):
    ydl_opts = {"quiet": True}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []
    seen = set()

    for f in info.get("formats", []):
        h = f.get("height")
        fid = f.get("format_id")

        if h in [360, 720, 1080] and fid not in seen:
            seen.add(fid)
            formats.append({
                "id": fid,
                "height": h
            })

    return formats


# ================= QUALITY MENU (FIX 1) =================
@dp.callback_query(F.data == "mp4")
async def mp4(call: types.CallbackQuery):
    await call.answer()

    uid = call.from_user.id
    url = user_state.get(uid, {}).get("url")

    if not url:
        await call.message.answer("❌ لینک پیدا نشد")
        return

    try:
        formats = get_formats(url)

        if not formats:
            await call.message.answer("❌ کیفیتی پیدا نشد")
            return

        kb = InlineKeyboardMarkup(inline_keyboard=[])

        for f in formats:
            # ❗ فقط format_id می‌فرستیم (بدون URL)
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🎬 {f['height']}p",
                    callback_data=f"dl|{f['id']}"
                )
            ])

        kb.inline_keyboard.append([
            InlineKeyboardButton(text="🏠 منو", callback_data="home")
        ])

        await call.message.answer("🎥 کیفیت رو انتخاب کن:", reply_markup=kb)

    except Exception as e:
        await call.message.answer(f"❌ خطا در گرفتن کیفیت:\n{e}")


# ================= DOWNLOAD VIDEO (FIX 2) =================
@dp.callback_query(F.data.startswith("dl|"))
async def download_video(call: types.CallbackQuery):
    await call.answer()

    try:
        _, format_id = call.data.split("|")

        uid = call.from_user.id
        url = user_state.get(uid, {}).get("url")

        if not url:
            await call.message.answer("❌ لینک پیدا نشد")
            return

        msg = await call.message.answer("⬇️ شروع دانلود...\n0%")

        progress["percent"] = 0

        async def updater():
            last = 0
            while True:
                p = progress.get("percent", 0)

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
            ydl_opts = {
                "format": format_id,
                "outtmpl": "video.%(ext)s",
                "progress_hooks": [progress_hook],
                "quiet": True,
                "nocheckcertificate": True,
                "retries": 10,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "web"]
                    }
                }
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        file_path = await asyncio.to_thread(run)

        task.cancel()

        await msg.edit_text("📤 در حال ارسال...")

        await call.message.answer_video(types.FSInputFile(file_path))

    except Exception as e:
        await call.message.answer(f"❌ خطا:\n{e}")


# ================= MP3 (FIX 3 - ffmpeg issue still depends on server) =================
@dp.callback_query(F.data == "mp3")
async def mp3(call: types.CallbackQuery):
    await call.answer()

    uid = call.from_user.id
    url = user_state.get(uid, {}).get("url")

    if not url:
        await call.message.answer("❌ لینک پیدا نشد")
        return

    msg = await call.message.answer("⬇️ ساخت MP3...\n0%")

    progress["percent"] = 0

    async def updater():
        last = 0
        while True:
            p = progress.get("percent", 0)

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
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "audio.%(ext)s",
            "progress_hooks": [progress_hook],
            "quiet": True,
            "retries": 10,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    try:
        file_path = await asyncio.to_thread(run)

        task.cancel()

        await msg.edit_text("📤 ارسال فایل...")

        await call.message.answer_audio(types.FSInputFile(file_path))

    except Exception as e:
        await call.message.answer(f"❌ خطا:\n{e}")


# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
