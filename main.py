import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# =============================================
# ⚙️  SOZLAMALAR - BU YERDA O'ZGARTIRING
# =============================================
BOT_TOKEN = "8582166992:AAFseKC-YLXlUw4eBnUVSn_I8yStvek-2i0"
CHANNEL_USERNAME = "@yoldoshevoo"
ADMIN_ID = 1632268347                                 # Sizning Telegram ID raqamingiz
MOVIES_FILE = "movies.json"                           # Kinolar saqlanadigan fayl
# =============================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------- Ma'lumotlar bazasi (JSON fayl) ----------

def load_movies() -> dict:
    if os.path.exists(MOVIES_FILE):
        with open(MOVIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_movies(movies: dict):
    with open(MOVIES_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)


# ---------- Kanalga obuna tekshirish ----------

async def is_subscribed(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


def subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("✅ Obuna bo'ldim!", callback_data="check_sub")]
    ])


# ---------- Handlerlar ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_subscribed(user.id, context):
        await update.message.reply_text(
            f"👋 Salom, {user.first_name}!\n\n"
            "🎬 Kino botga xush kelibsiz!\n\n"
            "⚠️ Botdan foydalanish uchun avval kanalga obuna bo'lishingiz shart!\n\n"
            "👇 Quyidagi tugmani bosib obuna bo'ling:",
            reply_markup=subscription_keyboard()
        )
        return

    await update.message.reply_text(
        f"👋 Salom, {user.first_name}!\n\n"
        "🎬 *Kino Botga Xush Kelibsiz!*\n\n"
        "📩 Kino raqamini yuboring va kino sizga yuboriladi!\n\n"
        "Misol: `5` yozing → 5-raqamdagi kino keladi",
        parse_mode="Markdown"
    )


async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if await is_subscribed(user.id, context):
        await query.edit_message_text(
            "✅ Rahmat! Obuna bo'ldingiz!\n\n"
            "🎬 Endi kino raqamini yuboring!"
        )
    else:
        await query.edit_message_text(
            "❌ Siz hali obuna bo'lmadingiz!\n\n"
            "Avval kanalga obuna bo'ling, so'ng qayta tekshiring.",
            reply_markup=subscription_keyboard()
        )


async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    # Obuna tekshirish
    if not await is_subscribed(user.id, context):
        await update.message.reply_text(
            "⚠️ Avval kanalga obuna bo'ling!",
            reply_markup=subscription_keyboard()
        )
        return

    # Raqammi?
    if not text.isdigit():
        await update.message.reply_text("❗ Iltimos, faqat raqam yuboring. Masalan: `5`", parse_mode="Markdown")
        return

    movies = load_movies()
    movie_code = text

    if movie_code not in movies:
        await update.message.reply_text(
            f"😔 {movie_code}-raqamdagi kino topilmadi.\n"
            "Boshqa raqam kiriting!"
        )
        return

    movie = movies[movie_code]
    file_id = movie["file_id"]
    title = movie.get("title", f"Kino #{movie_code}")
    file_type = movie.get("type", "video")

    await update.message.reply_text(f"🎬 *{title}* yuborilmoqda...", parse_mode="Markdown")

    try:
        if file_type == "video":
            await update.message.reply_video(video=file_id, caption=f"🎬 {title}")
        elif file_type == "document":
            await update.message.reply_document(document=file_id, caption=f"🎬 {title}")
    except Exception as e:
        logger.error(f"Fayl yuborishda xato: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi. Admin bilan bog'laning.")


# ---------- Admin komandalar ----------

async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ishlatish: /add 5 Kino nomi
    So'ng kino faylini yuboring (bot uni saqlaydi)
    """
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komanda faqat admin uchun!")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❗ To'g'ri format:\n`/add [raqam] [kino nomi]`\n\nMisol:\n`/add 5 Avatar 2`",
            parse_mode="Markdown"
        )
        return

    code = args[0]
    title = " ".join(args[1:])
    context.user_data["pending_add"] = {"code": code, "title": title}

    await update.message.reply_text(
        f"✅ Tayyor! Endi *{title}* (#{code}) kino faylini yuboring:",
        parse_mode="Markdown"
    )


async def receive_movie_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    pending = context.user_data.get("pending_add")
    if not pending:
        return

    code = pending["code"]
    title = pending["title"]

    if update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
    else:
        await update.message.reply_text("❗ Faqat video yoki dokument fayl yuboring!")
        return

    movies = load_movies()
    movies[code] = {"title": title, "file_id": file_id, "type": file_type}
    save_movies(movies)

    context.user_data.pop("pending_add", None)

    await update.message.reply_text(
        f"✅ *{title}* muvaffaqiyatli saqlandi!\n"
        f"📌 Raqam: `{code}`\n"
        f"Foydalanuvchilar `{code}` yozsa bu kino yuboriladi.",
        parse_mode="Markdown"
    )


async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Faqat admin!")
        return

    movies = load_movies()
    if not movies:
        await update.message.reply_text("📭 Hozircha hech qanday kino yo'q.")
        return

    text = "🎬 *Barcha kinolar:*\n\n"
    for code, info in sorted(movies.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        text += f"• `{code}` — {info['title']}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Faqat admin!")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Misol: `/del 5`", parse_mode="Markdown")
        return

    code = args[0]
    movies = load_movies()

    if code not in movies:
        await update.message.reply_text(f"❌ #{code} raqamli kino topilmadi.")
        return

    title = movies[code]["title"]
    del movies[code]
    save_movies(movies)

    await update.message.reply_text(f"🗑 *{title}* (#{code}) o'chirildi.", parse_mode="Markdown")


# ---------- Asosiy funksiya ----------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Komandalar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_movie))
    app.add_handler(CommandHandler("list", list_movies))
    app.add_handler(CommandHandler("del", delete_movie))

    # Callback (obuna tekshirish tugmasi)
    app.add_handler(CallbackQueryHandler(check_subscription, pattern="check_sub"))

    # Admin fayl qabul qilish
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, receive_movie_file))

    # Foydalanuvchi raqam yuborganda
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number))

    print("🤖 Bot ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    main()
