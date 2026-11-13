import os
import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import threading

API_ID = int(os.environ.get("API_ID", 31124352))
API_HASH = os.environ.get("API_HASH", "832029294d40cb38e94a3f1be77c5c59")
SESSION_STRING = os.environ.get("SESSION_STRING", "BAHa64AAeNUiRuUdZ3zFe-U0UPgS0yeq_fLBdcJmXWFChLwVhwzmoy8OZAkQiyI8YOivF5grGNbSpdlPCEe8-1YXV9KeEtJGbh3Sw8fVg1qJpMIJKvxi69mgZIvIAnobU0aOgj_ouawNsn3vlRikf9UxmAo0nDbHADG8aIiCHrB958ItF-FXkdM56prh-p0NmGKystmUKbbvv5H29-PLLXVJrkIvEVmBXeFZdGRIOY6I3xoehvasfjQR8cIVJ04WmoxSQ-E3VW6rLpl8bcbst1q8_1nBzh-qm59C-tCprF-xV6jh-hQxv7hGXgCWKyV5LodBMwvQJYx89aH7ImDM6_3mf0VC7QAAAAHOdfidAA")

app = Client("my_bot_session", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
flask_app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.on_message(filters.document | filters.video | filters.audio)
async def handle_file(client, message):
    sent_msg = await message.reply("⏳ جاري تحميل الملف ورفعه إلى Pixeldrain...")
    
    # تحميل الملف مؤقتاً على سيرفر Render
    file_path = await message.download(file_name=DOWNLOAD_DIR + "/")
    file_name = os.path.basename(file_path)
    
    try:
        # رفع الملف إلى Pixeldrain مجاناً وبدون حساب
        url = "https://pixeldrain.com/api/file"
        with open(file_path, "rb") as f:
            response = requests.post(url, files={"file": f})
        
        if response.status_code == 201:
            res_data = response.json()
            file_id = res_data.get("id")
            
            # الرابط المباشر السريع (جاهز لـ IDM)
            direct_link = f"https://pixeldrain.com/api/file/{file_id}"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ مسح رسالة الرابط", callback_data="delete_msg")]
            ])
            
            await sent_msg.edit_text(
                f"✅ **تم رفع الملف بنجاح إلى Pixeldrain!**\n\n"
                f"📁 **اسم الملف:** `{file_name}`\n"
                f"🔗 **الرابط المباشر (IDM):**\n{direct_link}",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await sent_msg.edit_text(f"❌ فشل الرفع (كود الخطأ: {response.status_code})")
            
    except Exception as e:
        await sent_msg.edit_text(f"❌ حدث خطأ: `{str(e)}`", parse_mode="Markdown")
    finally:
        # مسح النسخة المؤقتة من سيرفر Render فوراً لتفريغ المساحة
        if os.path.exists(file_path):
            os.remove(file_path)

@app.on_callback_query(filters.regex("^delete_msg$"))
async def delete_message_handler(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception:
        await callback_query.answer("عذراً، لم أتمكن من مسح الرسالة", show_alert=True)

@flask_app.route('/')
def home():
    return "Pixeldrain Telegram Bot is running successfully on Render!"

def run_telegram():
    app.run()

if __name__ == "__main__":
    t = threading.Thread(target=run_telegram)
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
