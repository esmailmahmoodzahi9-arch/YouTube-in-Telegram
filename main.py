import asyncio
import os
import yt_dlp
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
        [InlineKeyboardButton(text="📥 دانلود یوتیوب", callback_data="download")]
    ])


# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    user_state[message.from_user.id] = {}

    await message.answer("👋 ربات آماده است", reply_markup=menu())


# ================= MENU =================
@dp.callback_query(F.data == "download")
async def download_mode(call: types.CallbackQuery):
    await call.answer()
    user_state[call.from_user.id] = {"mode": "download"}

    await call.message.answer("📥 لینک یوتیوب رو بفرست")


# ================= DOWNLOAD ENGINE =================
def download_video(url, mode="mp4"):
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
            "format": "best[ext=mp4]/best",
            "outtmpl": "video.%(ext)s"
        }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


# ================= HANDLER =================
@dp.message(F.text)
async def handler(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    state = user_state.get(uid, {})

    if state.get("mode") != "download":
        return

    if "youtube" not in text and "youtu.be" not in text:
        await message.answer("❌ لینک معتبر نیست")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 دانلود ویدیو", callback_data=f"mp4|{text}")
        ],
        [
            InlineKeyboardButton(text="🎵 دانلود آهنگ", callback_data=f"mp3|{text}")
        ]
    ])

    await message.answer("👇 انتخاب کن:", reply_markup=kb)


# ================= CALLBACK =================
@dp.callback_query(F.data.startswith("mp"))
async def dl(call: types.CallbackQuery):
    await call.answer()

    mode, url = call.data.split("|")

    await call.message.answer("⬇️ در حال دانلود...")

    try:
        file_path = await asyncio.to_thread(download_video, url, "mp3" if mode == "mp3" else "mp4")

        await call.message.answer("📤 ارسال فایل...")

        if mode == "mp3":
            await call.message.answer_audio(types.FSInputFile(file_path))
        else:
            await call.message.answer_video(types.FSInputFile(file_path))

    except Exception as e:
        await call.message.answer(f"❌ خطا:\n{e}")


# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
