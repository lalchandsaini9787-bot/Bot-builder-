import asyncio
import os
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIG from Render Env ---
MASTER_TOKEN = os.getenv("MASTER_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# --- WEB SERVER (Render ke liye) ---
web = Flask(__name__)
@web.route('/')
def home(): return "Bot Live!"
Thread(target=lambda: web.run(host='0.0.0.0', port=10000), daemon=True).start()

# --- DB ---
client = MongoClient(MONGO_URI)
bots_col = client["bot_factory"]["user_bots"]

# --- BOT TEMPLATES ---
def template_selling():
    from telegram.ext import CommandHandler
    async def start(u,c): await u.message.reply_text("🛍️ Welcome to My Shop! /products dekho")
    async def products(u,c): await u.message.reply_text("1. Shoes - ₹999\n2. Watch - ₹1499")
    return [CommandHandler("start", start), CommandHandler("products", products)]

def template_gaming():
    from telegram.ext import CommandHandler
    async def start(u,c): await u.message.reply_text("🎮 Game Bot Ready! /play karo")
    async def play(u,c): await u.message.reply_text("Dice roll ho raha... 🎲 6 aaya!")
    return [CommandHandler("start", start), CommandHandler("play", play)]

ALL_TYPES = {"selling": template_selling, "gaming": template_gaming}
user_data = {}

async def launch_bot(token, btype):
    app2 = ApplicationBuilder().token(token).build()
    for h in ALL_TYPES[btype](): app2.add_handler(h)
    await app2.initialize(); await app2.start()
    asyncio.create_task(app2.updater.start_polling())

async def start_master(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("Apna bot token bhejo pehle:")

async def handle_token(u: Update, c: ContextTypes.DEFAULT_TYPE):
    token = u.message.text.strip()
    user_data[u.effective_user.id] = token
    kb = [[InlineKeyboardButton("🛍️ Selling", callback_data="type_selling")],
          [InlineKeyboardButton("🎮 Gaming", callback_data="type_gaming")]]
    await u.message.reply_text("Type chuno:", reply_markup=InlineKeyboardMarkup(kb))

async def button_click(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer()
    btype = q.data.replace("type_","")
    token = user_data.get(q.from_user.id)
    try:
        await launch_bot(token, btype)
        bots_col.update_one({"user_id": q.from_user.id},
            {"$set": {"token": token, "btype": btype, "expiry": datetime.now() + timedelta(days=7)}}, upsert=True)
        await q.edit_message_text(f"✅ Tera {btype} Bot LIVE hai! 7 din free.")
    except Exception as e: await q.edit_message_text(f"❌ Error: {e}")

async def broadcast(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.effective_user.id != ADMIN_ID: return
    msg = " ".join(c.args)
    cnt=0
    for doc in bots_col.find():
        try: await c.bot.send_message(chat_id=doc["user_id"], text=f"📢 {msg}"); cnt+=1
        except: pass
    await u.message.reply_text(f"✅ {cnt} ko bheja")

async def post_init(app):
    for doc in bots_col.find():
        try: await launch_bot(doc["token"], doc["btype"])
        except: pass

app = ApplicationBuilder().token(MASTER_TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start_master))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(CallbackQueryHandler(button_click))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token))
print("Master Bot Started...")
app.run_polling()
