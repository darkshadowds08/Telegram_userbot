import os
import re
import uuid
import asyncio
import threading
from urllib.parse import quote

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------- الإعدادات ----------
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

B2_KEY_ID = os.environ.get("B2_KEY_ID", "")
B2_APP_KEY = os.environ.get("B2_APP_KEY", "")
B2_BUCKET = os.environ.get("B2_BUCKET", "Ddlink")
B2_ENDPOINT = os.environ.get("B2_ENDPOINT", "")  # مثال: https://s3.us-west-004.backblazeb2.com

# 1 = روابط خاصة موقّعة تنتهي صلاحيتها، 0 = bucket عام
PRIVATE_LINKS = os.environ.get("PRIVATE_LINKS", "0") == "1"
LINK_EXPIRY = 7 * 24 * 3600  # الحد الأقصى في B2: 7 أيام

MAX_SIZE = 2000 * 1024 * 1024  # 2GB (عدّله كما تشاء)

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

s3 = boto3.client(
    "s3",
    endpoint_url=B2_ENDPOINT,
    aws_access_key_id=B2_KEY_ID,
    aws_secret_access_key=B2_APP_KEY,
    config=Config(
        signature_version="s3v4",
        retries={"max_attempts": 5, "mode": "standard"},
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    ),
)

transfer_config = TransferConfig(
    multipart_threshold=50 * 1024 * 1024,
    multipart_chunksize=50 * 1024 * 1024,
    max_concurrency=4,
)


def upload_sync(path, key):
    s3.upload_file(path, B2_BUCKET, key, Config=transfer_config)
    if PRIVATE_LINKS:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": B2_BUCKET, "Key": key},
            ExpiresIn=LINK_EXPIRY,
        )
    return f"{B2_ENDPOINT}/{B2_BUCKET}/{quote(key)}"


def clean_name(name):
    return re.sub(r"[^\w.\-]+", "_", name).strip("_") or "file"


@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply("👋 أرسل لي أي ملف وسأعطيك رابطًا مباشرًا له.")


@app.on_message(
    (filters.document | filters.video | filters.audio) & filters.private
)
async def handle_file(client, message):
    media = message.document or message.video or message.audio

    if media.file_size and media.file_size > MAX_SIZE:
        await message.reply("❌ الملف أكبر من الحد المسموح.")
        return

    sent_msg = await message.reply("⏳ جاري تحميل الملف ورفعه...")
    file_path = None
    try:
        file_path = await message.download(
            file_name=os.path.join(DOWNLOAD_DIR, f"{message.id}_")
        )
        original_name = getattr(media, "file_name", None) or os.path.basename(file_path)
        key = f"{uuid.uuid4().hex[:8]}/{clean_name(original_name)}"

        link = await asyncio.to_thread(upload_sync, file_path, key)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ مسح رسالة الرابط", callback_data="delete_msg")]
        ])
        expiry_note = "\n⏱ الرابط صالح 7 أيام." if PRIVATE_LINKS else ""
        await sent_msg.edit_text(
            f"✅ **تم رفع الملف بنجاح!**\n\n"
            f"📁 **اسم الملف:** `{original_name}`\n\n"
            f"🔗 **الرابط المباشر (IDM):**\n{link}{expiry_note}",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except Exception as e:
        await sent_msg.edit_text(f"❌ حدث خطأ: `{str(e)[:300]}`")
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
    app.run()
