import json
import logging
import os
from datetime import datetime
from io import BytesIO
from jinja2 import Template
import requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, constants, InputFile
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# === НАСТРОЙКИ ===
TOKEN = "7518855628:AAHRUxCEsKYbK7kQr-N74yGKqCycS5Uc7UA"
CHANNEL_USERNAME = "@findiumnews"
ADMIN_IDS = [5953261422]
DAILY_LIMIT = 10
API_TOKEN = "HJkFuGjNu9aFtEv2DIwL3zTCgVmIAgV"
API_BASE_URL = "https://infosearch54321.xyz"

# === ДАННЫЕ ===
REQUESTS_FILE = "user_requests.json"
JOINS_FILE = "user_joins.json"
user_requests = {}
user_joins = {}

# === ЛОГГИРОВАНИЕ ===
logging.basicConfig(filename="logs.txt", level=logging.INFO, format="%(asctime)s - %(message)s")

# === ЗАГРУЗКА И СОХРАНЕНИЕ ===
def load_data():
    global user_requests, user_joins
    if os.path.exists(REQUESTS_FILE):
        with open(REQUESTS_FILE, "r") as f:
            user_requests.update(json.load(f))
    if os.path.exists(JOINS_FILE):
        with open(JOINS_FILE, "r") as f:
            user_joins.update(json.load(f))

def save_data():
    with open(REQUESTS_FILE, "w") as f:
        json.dump(user_requests, f)
    with open(JOINS_FILE, "w") as f:
        json.dump(user_joins, f)

# === HTML ОТЧЁТ ===
def render_html(query: str, date: str, results: dict) -> BytesIO:
    with open("templates/report_template.html", "r", encoding="utf-8") as f:
        template = Template(f.read())
    html = template.render(query=query, date=date, results=results)
    file = BytesIO(html.encode("utf-8"))
    file.name = "findium_report.html"
    return file

# === ПОДПИСКА ===
async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# === СТАРТ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in user_joins:
        user_joins[user_id] = datetime.now().strftime("%Y-%m-%d")
        save_data()

    if not await check_subscription(user_id, context):
        keyboard = [
            [InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub")]
        ]
        await update.message.reply_text(
            "👋 Добро пожаловать!\n\nДля доступа к Findium, подпишитесь на наш канал 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await send_main_menu(update, context)

# === МЕНЮ ===
async def send_main_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("🧭 Сделать запрос", callback_data="back_to_query")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📖 Инструкция", callback_data="instruction")]
    ]
    if update.effective_user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🛠 Админ-панель", callback_data="admin_menu")])

    text = (
        "🛰 <b>Findium Intelligence</b>\n"
        "Добро пожаловать, <b>{}</b>!\n\n"
        "Вы можете начать поиск по номеру, email, IP или ФИО.\n"
        f"🧭 Вам доступно {DAILY_LIMIT} бесплатных запросов в день."
    ).format(update.effective_user.first_name)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=constants.ParseMode.HTML,
                                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup(keyboard))

# === КНОПКИ ===
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = str(query.from_user.id)

    if data == "check_sub":
        if await check_subscription(user_id, context):
            await send_main_menu(update, context)
        else:
            await query.edit_message_text("❌ Подписка не найдена. Подпишитесь и попробуйте снова.")

    elif data == "back_to_query":
        await query.edit_message_text("✏️ Введите номер, email или имя для поиска:")

    elif data == "instruction":
        await query.edit_message_text(
            "📘 Просто введите номер, email или имя для начала поиска.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]])
        )

    elif data == "stats":
        joined = user_joins.get(user_id, "n/a")
        req_data = user_requests.get(user_id, {"count": 0})
        used = req_data["count"]
        await query.edit_message_text(
            f"📊 Ваша статистика:\n\n"
            f"📅 Дата присоединения: <b>{joined}</b>\n"
            f"📈 Использовано сегодня: <b>{used}/{DAILY_LIMIT}</b>",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]])
        )

    elif data == "back_to_menu":
        await send_main_menu(update, context)

    elif data == "get_html":
        result_data = context.user_data.get("last_result")
        if not result_data:
            await query.answer("⚠️ Нет данных", show_alert=True)
            return

        html_file = render_html(result_data["query"], result_data["date"], result_data["data"])
        await context.bot.send_document(chat_id=query.message.chat.id,
                                        document=InputFile(html_file),
                                        caption="📄 HTML-отчёт")

    elif data == "admin_menu":
        if int(user_id) not in ADMIN_IDS:
            await query.answer("⛔️ Доступ запрещён", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("📈 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("📤 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("➕ Выдать запросы", callback_data="admin_give")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]
        ]
        await query.edit_message_text("🛠 <b>Админ-панель</b>", parse_mode=constants.ParseMode.HTML,
                                      reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_stats":
        total_users = len(user_joins)
        active_today = sum(1 for u in user_requests.values() if u.get("date") == datetime.now().strftime("%Y-%m-%d"))
        await query.edit_message_text(
            f"📊 Статистика:\n\n"
            f"👥 Всего пользователей: <b>{total_users}</b>\n"
            f"📅 Активны сегодня: <b>{active_today}</b>",
            parse_mode=constants.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_menu")]])
        )

    elif data == "admin_broadcast":
        context.user_data["awaiting_broadcast"] = True
        await query.edit_message_text("✉️ Введите текст рассылки:",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_menu")]]))

    elif data == "admin_give":
        context.user_data["awaiting_grant"] = True
        await query.edit_message_text("🧾 Введите ID пользователя и кол-во запросов через пробел\nПример: 12345678 5",
                                      parse_mode=constants.ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_menu")]]))

# === ПОИСК ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    # Админ команды
    if int(user_id) in ADMIN_IDS:
        if context.user_data.get("awaiting_broadcast"):
            context.user_data["awaiting_broadcast"] = False
            msg = text
            count = 0
            for uid in user_joins:
                try:
                    await context.bot.send_message(chat_id=int(uid), text=f"📢 <b>Сообщение от Findium:</b>\n\n{msg}",
                                                   parse_mode=constants.ParseMode.HTML)
                    count += 1
                except:
                    continue
            await update.message.reply_text(f"✅ Рассылка завершена. Доставлено: {count}")
            return

        if context.user_data.get("awaiting_grant"):
            context.user_data["awaiting_grant"] = False
            try:
                uid, count = text.split()
                count = int(count)
                rec = user_requests.setdefault(uid, {"count": 0, "date": datetime.now().strftime("%Y-%m-%d")})
                rec["count"] += count
                save_data()
                await update.message.reply_text(f"✅ Пользователю {uid} выдано {count} запросов.")
            except:
                await update.message.reply_text("❌ Ошибка формата. Используй: 123456 5")
            return

    # Пользовательские запросы
    today_str = datetime.now().strftime("%Y-%m-%d")
    data = user_requests.get(user_id, {"date": today_str, "count": 0})

    if data["date"] != today_str:
        data = {"date": today_str, "count": 0}

    if data["count"] >= DAILY_LIMIT:
        await update.message.reply_text("🚫 Вы исчерпали дневной лимит.")
        return

    data["count"] += 1
    user_requests[user_id] = data
    save_data()

    sent = await update.message.reply_text("🔎 Поиск...")

    try:
        url = f"{API_BASE_URL}/api/{API_TOKEN}/search/{text}"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        result = response.json()
        raw_result = result.get("result", {})

        if isinstance(raw_result, list):
            results = {str(i + 1): item for i, item in enumerate(raw_result)}
        elif isinstance(raw_result, dict):
            results = raw_result
        else:
            results = {}

        if not results:
            await sent.edit_text("😕 Данные не найдены по вашему запросу.")
            return

        context.user_data["last_result"] = {
            "query": text,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data": results
        }

        msg = "<b>📊 Результаты:</b>\n\n"
        for i, item in results.items():
            for k, v in item.items():
                msg += f"✦ <b>{k}</b>: <code>{v}</code>\n"
            msg += "\n"

        if len(msg) > 4000:
            html_file = render_html(text, datetime.now().strftime("%Y-%m-%d %H:%M"), results)
            await sent.edit_text("⚠️ Результат слишком большой. Отправляю HTML-файл.")
            await context.bot.send_document(chat_id=update.effective_chat.id,
                                            document=InputFile(html_file),
                                            caption="📄 HTML-отчёт")
        else:
            keyboard = [
                [InlineKeyboardButton("📄 HTML-отчёт", callback_data="get_html")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]
            ]
            await sent.edit_text(msg, parse_mode=constants.ParseMode.HTML,
                                 reply_markup=InlineKeyboardMarkup(keyboard))

        logging.info(f"{user_id} запросил: {text}")

    except Exception as e:
        await sent.edit_text(f"❌ Ошибка: {e}")

# === MAIN ===
def main():
    load_data()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.run_polling()

if __name__ == "__main__":
    main()