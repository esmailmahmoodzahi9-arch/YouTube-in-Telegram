import os
print("TOKEN =", os.getenv("TOKEN"))
import asyncio
import os
import yt_dlp

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart

# ================= TOKEN =================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise RuntimeError("❌ TOKEN is missing! Set it in Railway Variables.")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_state = {}


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 دانلود یوتیوب", callback_data="download")],
        [InlineKeyboardButton(text="🔎 یوتیوب گردی", callback_data="browse")]
    ])

    await message.answer(
        "👋 سلام!\nبه ربات یوتیوب خوش آمدی",
        reply_markup=kb
    )


# ================= MENU =================
@dp.callback_query()
async def menu(call: types.CallbackQuery):
    await call.answer()

    if call.data == "download":
        user_state[call.from_user.id] = {"mode": "download"}
        await call.message.answer("📥 لینک یوتیوب رو بفرست")

    elif call.data == "browse":
        user_state[call.from_user.id] = {"mode": "browse"}
        await call.message.answer("🔎 اسم ویدیو یا کانال رو بفرست")


# ================= TEXT =================
@dp.message(F.text)
async def handle_text(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_state.get(uid, {})

    # ---------- DOWNLOAD ----------
    if state.get("mode") == "download" and (
        "youtube.com" in text or "youtu.be" in text
    ):
        user_state[uid]["url"] = text

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 MP3", callback_data="mp3")],
            [InlineKeyboardButton(text="🎬 MP4", callback_data="mp4")]
        ])

        await message.answer("فرمت رو انتخاب کن:", reply_markup=kb)
        return


    # ---------- BROWSE ----------
    if state.get("mode") == "browse":

        await message.answer("🔎 در حال جستجو...")

        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "default_search": "ytsearch10"
        }

        try:
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

        except Exception as e:
            await message.answer(f"❌ خطا در جستجو:\n{e}")


# ================= VIDEO SELECT =================
@dp.callback_query(F.data.startswith("video|"))
async def select_video(call: types.CallbackQuery):
    await call.answer()

    video_id = call.data.split("|")[1]
    url = f"https://www.youtube.com/watch?v={video_id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 MP4", callback_data=f"dlmp4|{url}")],
        [InlineKeyboardButton(text="🎵 MP3", callback_data=f"dlmp3|{url}")]
    ])

    await call.message.answer("یکی رو انتخاب کن:", reply_markup=kb)


# ================= DOWNLOAD ENGINE =================
def download_video(url, mode):
    if mode == "mp3":
        opts = {
            "format": "bestaudio/best",
            "outtmpl": "audio.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }]
        }
    else:
        opts = {
            "format": "best",
            "outtmpl": "video.%(ext)s"
        }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


# ================= DOWNLOAD HANDLER =================
@dp.callback_query(F.data.startswith("dl"))
async def download_handler(call: types.CallbackQuery):
    await call.answer()

    url = call.data.split("|")[1]
    mode = "mp3" if "mp3" in call.data else "mp4"

    await call.message.answer("⏳ در حال دانلود...")

    try:
        file_path = await asyncio.to_thread(download_video, url, mode)

        await call.message.answer("📤 در حال ارسال فایل...")

        if mode == "mp3":
            await call.message.answer_audio(types.FSInputFile(file_path))
        else:
            await call.message.answer_video(types.FSInputFile(file_path))

        # پاکسازی فایل
        try:
            os.remove(file_path)
        except:
            pass

    except Exception as e:
        await call.message.answer(f"❌ خطا:\n{e}")


# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
