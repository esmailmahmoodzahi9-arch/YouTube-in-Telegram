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


# ================= PROGRESS =================
def bar(p):
    p = max(0, min(100, p))
    return "▰" * (p // 10) + "▱" * (10 - (p // 10))


def progress_hook(d):
    if d["status"] == "downloading":
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate", 1)

        percent = int(downloaded * 100 / total)
        download_progress["percent"] = percent


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("👋 خوش آمدی", reply_markup=menu())


# ================= SAFE CALLBACK ROUTER =================
@dp.callback_query(F.data.in_(["download", "browse", "home"]))
async def main_router(call: types.CallbackQuery):
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

    # ---------- DOWNLOAD MODE ----------
    if state.get("mode") == "download":
        if "youtube.com" not in text and "youtu.be" not in text:
            await message.answer("❌ لینک معتبر نیست")
            return

        user_state[uid]["url"] = text

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 دانلود آهنگ", callback_data="mp3")],
            [InlineKeyboardButton(text="🎬 انتخاب کیفیت", callback_data="mp4")],
            [InlineKeyboardButton(text="🏠 منو", callback_data="home")]
        ])

        await message.answer("یکی رو انتخاب کن:", reply_markup=kb)
        return


# ================= VIDEO QUALITY =================
def get_formats(url):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []

    for f in info.get("formats", []):
        if f.get("vcodec") != "none" and f.get("height") in [360, 720, 1080]:
            formats.append({
                "id": f["format_id"],
                "height": f.get("height")
            })

    return formats


@dp.callback_query(F.data == "mp4")
async def quality_menu(call: types.CallbackQuery):
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
                callback_data=f"dl|{f['id']}|{url}"
            )
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 منو", callback_data="home")
    ])

    await call.message.answer("🎥 کیفیت رو انتخاب کن:", reply_markup=kb)


# ================= DOWNLOAD VIDEO =================
@dp.callback_query(F.data.startswith("dl|"))
async def download_video(call: types.CallbackQuery):
    await call.answer()

    try:
        _, format_id, url = call.data.split("|")

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

        await msg.edit_text("📤 در حال ارسال...")

        await call.message.answer_video(types.FSInputFile(file_path))

    except Exception as e:
        await call.message.answer(f"❌ خطا:\n{e}")


# ================= MP3 =================
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
