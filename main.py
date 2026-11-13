import os
import asyncio
import threading
import requests
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PD_KEY = os.environ.get("PIXELDRAIN_KEY", "")

app = Client(
    "file_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)
flask_app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_SIZE = 200 * 1024 * 1024  # 200MB


def upload_sync(path, name):
    with open(path, "rb") as f:
        return requests.put(
            f"https://pixeldrain.com/api/file/{name}",
            data=f,
            auth=("", PD_KEY),
            timeout=600,
        )


@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply("👋 أرسل لي أي ملف وسأعطيك رابطًا مباشرًا له.")


@app.on_message(
    (filters.document | filters.video | filters.audio) & filters.private
)
async def handle_file(client, message):
    media = message.document or message.video or message.audio

    if media.file_size and media.file_size > MAX_SIZE:
        await message.reply("❌ الملف أكبر من الحد المسموح (200MB).")
        return

    sent_msg = await message.reply("⏳ جاري تحميل الملف ورفعه إلى Pixeldrain...")
    file_path = None
    try:
        file_path = await message.download(
            file_name=os.path.join(DOWNLOAD_DIR, f"{message.id}_")
        )
        original_name = getattr(media, "file_name", None) or os.path.basename(file_path)

        response = await asyncio.to_thread(upload_sync, file_path, original_name)

        if response.status_code in (200, 201):
            file_id = response.json().get("id")
            direct_link = f"https://pixeldrain.com/api/file/{file_id}"
            page_link = f"https://pixeldrain.com/u/{file_id}"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ مسح رسالة الرابط", callback_data="delete_msg")]
            ])
            await sent_msg.edit_text(
                f"✅ **تم رفع الملف بنجاح!**\n\n"
                f"📁 **اسم الملف:** `{original_name}`\n\n"
                f"🔗 **الرابط المباشر (IDM):**\n{direct_link}\n\n"
                f"🌐 **صفحة العرض:**\n{page_link}",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        else:
            await sent_msg.edit_text(
                f"❌ فشل الرفع (كود: {response.status_code})\n{response.text[:200]}"
            )
    except Exception as e:
        await sent_msg.edit_text(f"❌ حدث خطأ: `{e}`")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


@app.on_callback_query(filters.regex("^delete_msg$"))
async def delete_message_handler(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("لم أتمكن من مسح الرسالة", show_alert=True)


@flask_app.route("/")
def home():
    return "Bot is running!"


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()  # في الخيط الرئيسي
