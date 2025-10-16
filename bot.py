#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import uuid
import asyncio
import math
from typing import Dict, List
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode
import json
from datetime import datetime

# --- استدعاء المحلل الذكي والمولد ---
from smart_parser_ai import parse_question_with_ai
from pdf_generator import create_questions_pdf

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))

# Data storage files
DATA_FILE = 'questions_data.json'
REPLIES_FILE = 'replies_data.json'
USERS_FILE = "users_data.json"
BANS_FILE = "banned_users.json"

# In-memory storage
questions_data: Dict[str, dict] = {}
replies_data: Dict[str, dict] = {}
waiting_for_broadcast: Dict[int, bool] = {}
banned_users: Dict[str, dict] = {}
active_users: Dict[int, dict] = {}

# --- Helper Functions for Data Handling ---
def load_data(filename: str) -> Dict:
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}"); return {}

def save_data(data: Dict, filename: str):
    try:
        with open(filename, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {filename}: {e}")

def load_users_data():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as file: return json.load(file)
        return {}
    except Exception as e:
        logger.error(f"Failed to load users data: {e}"); return {}

def save_users_data():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as file: json.dump(active_users, file, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save users data: {e}")

def escape_legacy_markdown(text: str) -> str:
    escape_chars = r'_*`['
    return ''.join(['\\' + char if char in escape_chars else char for char in text])

questions_data = load_data(DATA_FILE)
replies_data = load_data(REPLIES_FILE)
banned_users = load_data(BANS_FILE)
active_users = load_users_data()

def get_user_questions(user_id: int) -> List[Dict]:
    user_q = [q for q in questions_data.values() if q['user_id'] == user_id]
    return sorted(user_q, key=lambda x: x['timestamp'], reverse=True)

def get_all_user_ids() -> List[int]:
    question_user_ids = set(q['user_id'] for q in questions_data.values())
    active_user_ids = set(int(uid) for uid in active_users.keys())
    return list(question_user_ids.union(active_user_ids))

def is_user_banned(user_id: int) -> bool: return str(user_id) in banned_users

def ban_user(user_id: int, admin_id: int, reason: str = "No reason provided"):
    try:
        banned_users[str(user_id)] = {'banned_at': datetime.now().isoformat(), 'banned_by': admin_id, 'reason': reason}
        save_data(banned_users, BANS_FILE)
        return True
    except Exception as e:
        logger.error(f"Failed to ban user {user_id}: {e}"); return False

def unban_user(user_id: int):
    try:
        if str(user_id) in banned_users:
            del banned_users[str(user_id)]
            save_data(banned_users, BANS_FILE)
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to unban user {user_id}: {e}"); return False

def get_banned_users():
    return [{'user_id': int(user_id), **ban_data} for user_id, ban_data in banned_users.items()]

async def set_menu_button(application: Application):
    try:
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands(type="commands"))
        logger.info("Menu button set to commands")
    except Exception as e:
        logger.error(f"Failed to set menu button: {e}")

# --- Command Handlers ---
async def start_command(update: Update, context: CallbackContext):
    user = update.effective_user
    if not user: return
    keyboard = [[InlineKeyboardButton("📬 أسئلتي المرسلة", callback_data="orders_list:page:0")], [InlineKeyboardButton("💡 كيف أستخدم البوت؟", callback_data="instructions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    user_name = user.first_name or "عزيزي"
    welcome_message = f"🎯 أهلاً بك يا {user_name}!\n\nمرحباً في **بوت هدفك**، منصتك لمشاركة وتجميع أسئلة اختبار القدرات الحديثة.\n\n📝 **شاركنا بما لديك:**\n- نص السؤال\n- صورة واضحة\n- ملف PDF\n- تسجيل صوتي\n\nفريقنا سيستلم مشاركتك لمراجعتها وإضافتها. شكراً لمساهمتك!\n\n👇 استخدم الأزرار للاطلاع على المزيد."
    user_id = user.id
    if str(user_id) not in active_users:
        active_users[str(user_id)] = {"first_name": user.first_name, "last_name": user.last_name or "", "username": user.username or "", "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "message_count": 0}
    else:
        active_users[str(user_id)]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_users_data()
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

# --- ADDING THE MISSING HELP COMMAND ---
async def help_command(update: Update, context: CallbackContext) -> None:
    is_admin = update.effective_chat and update.effective_chat.id == ADMIN_GROUP_ID
    admin_help = (
        "**🛠️ قائمة أوامر المشرفين:**\n\n"
        "/stats - عرض الإحصائيات\n"
        "/export - استخراج البيانات\n"
        "/import - استيراد البيانات (بالرد على الملف)\n"
        "/makepdf - إنشاء PDF للأسئلة\n"
        "/broadcast - إرسال رسالة جماعية\n"
        "/ban `user_id` `[reason]` - حظر مستخدم\n"
        "/unban `user_id` - رفع الحظر\n"
        "/banned - عرض قائمة المحظورين"
    )
    user_help = (
        "**👋 مرحباً بك في قسم المساعدة!**\n\n"
        "/start - بدء/عودة للقائمة الرئيسية\n"
        "/help - عرض هذه الرسالة"
    )
    help_text = admin_help if is_admin else user_help
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if not query or not query.from_user: return
    await query.answer()
    if query.data.startswith("orders_list"):
        user_id = query.from_user.id
        user_questions = get_user_questions(user_id)
        if not user_questions:
            await query.edit_message_text("📪 ليس لديك أي أسئلة مرسلة بعد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]))
            return
        try:
            page = int(query.data.split(':')[-1])
        except (ValueError, IndexError):
            page = 0
        QUESTIONS_PER_PAGE = 5
        total_pages = math.ceil(len(user_questions) / QUESTIONS_PER_PAGE)
        start_index = page * QUESTIONS_PER_PAGE
        end_index = start_index + QUESTIONS_PER_PAGE
        questions_on_page = user_questions[start_index:end_index]
        orders_text = f"📬 *قائمة أسئلتك (الأحدث أولاً):*\n\n"
        for i, q in enumerate(questions_on_page, start=start_index + 1):
            ts = datetime.fromisoformat(q['timestamp']).strftime('%Y-%m-%d %H:%M')
            raw_preview = q.get('raw_content', '')[:40] + "..." if len(q.get('raw_content', '')) > 40 else q.get('raw_content', '')
            safe_preview = escape_legacy_markdown(raw_preview) if raw_preview else "محتوى وسائط"
            orders_text += f"*{i}.* *نوع:* {q['message_type']} - *تاريخ:* {ts}\n   `{safe_preview}`\n\n"
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"orders_list:page:{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"صفحة {page + 1}/{total_pages}", callback_data="noop"))
        if end_index < len(user_questions):
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"orders_list:page:{page + 1}"))
        keyboard = [nav_buttons, [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(orders_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    elif query.data == "instructions":
        await query.edit_message_text("💡 **طريقة استخدام البوت:**...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]), parse_mode=ParseMode.MARKDOWN)
    elif query.data == "main_menu":
        await start_command(update, context)

# --- Admin Command Handlers ---
async def stats_command(update: Update, context: CallbackContext):
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    total_questions = len(questions_data)
    unique_users = len(get_all_user_ids())
    type_counts = {}
    for q in questions_data.values():
        type_counts[q['message_type']] = type_counts.get(q['message_type'], 0) + 1
    stats_text = f"📈 **نظرة على إحصائيات البوت:**\n\n📥 إجمالي المشاركات: {total_questions}\n👥 عدد المستخدمين الفريدين: {unique_users}\n\n📂 **تصنيف المشاركات حسب النوع:**\n" + "\n".join([f"• {msg_type}: {count}" for msg_type, count in type_counts.items()])
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def export_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        for file_path, name in {DATA_FILE: "questions", REPLIES_FILE: "replies", USERS_FILE: "users", BANS_FILE: "banned"}.items():
            if os.path.exists(file_path):
                await update.message.reply_document(document=open(file_path, 'rb'), filename=f"{name}_{timestamp}.json")
        await update.message.reply_text(f"✅ **اكتمل تصدير البيانات بنجاح**", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء التصدير: {e}")

async def import_command(update: Update, context: CallbackContext) -> None:
    global questions_data, replies_data, active_users, banned_users
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    try:
        chat_admins = await context.bot.get_chat_administrators(ADMIN_GROUP_ID)
        if update.effective_user.id not in [admin.user.id for admin in chat_admins]:
            return await update.message.reply_text("🚫 هذا الأمر مخصص لمشرفي الجروب فقط.")
    except Exception as e:
        return await update.message.reply_text(f"خطأ في التحقق من صلاحيات المشرف: {e}")
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        return await update.message.reply_text("⚠️ لاستخدام هذا الأمر، أرسل ملف الـ JSON أولاً، ثم قم بالرد (Reply) على رسالة الملف بالأمر `/import`.")
    doc = update.message.reply_to_message.document
    file_name = doc.file_name.lower()
    target_file = None
    if "questions" in file_name: target_file = DATA_FILE
    elif "replies" in file_name: target_file = REPLIES_FILE
    elif "users" in file_name: target_file = USERS_FILE
    elif "banned" in file_name: target_file = BANS_FILE
    else: return await update.message.reply_text("❌ لم يتم التعرف على الملف.")
    try:
        json_file = await doc.get_file()
        file_bytes = await json_file.download_as_bytearray()
        json.loads(file_bytes.decode('utf-8'))
        with open(target_file, 'wb') as f: f.write(file_bytes)
        questions_data, replies_data, active_users, banned_users = load_data(DATA_FILE), load_data(REPLIES_FILE), load_users_data(), load_data(BANS_FILE)
        await update.message.reply_text(f"✅ تم استيراد وتحديث ملف `{target_file}` بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ غير متوقع: {e}")

async def makepdf_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    try:
        wait_message = await update.message.reply_text("⏳ جارٍ تجميع كافة الأسئلة في ملف PDF، قد تستغرق هذه العملية بعض الوقت...")
        output_filename = f"tجميع_اسئلة_{datetime.now().strftime('%Y%m%d')}.pdf"
        pdf_path = create_questions_pdf(questions_data, output_filename)
        if pdf_path and os.path.exists(pdf_path):
            await update.message.reply_document(document=open(pdf_path, 'rb'), filename=output_filename, caption="✅ تم إنشاء ملف تجميع الأسئلة بنجاح.")
            os.remove(pdf_path)
        else:
            await update.message.reply_text("❌ حدث خطأ أثناء إنشاء ملف الـ PDF.")
        await wait_message.delete()
    except Exception as e:
        logger.error(f"Error in makepdf_command: {e}")
        await update.message.reply_text(f"❌ فشلت العملية. الخطأ: {e}")

async def broadcast_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID or not update.effective_user: return
    waiting_for_broadcast[update.effective_user.id] = True
    await update.message.reply_text(f"📡 **وضع الإرسال الجماعي**\n\nالآن، أرسل الرسالة التي تود بثها.")

async def ban_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID or not update.effective_user: return
    if not context.args: return await update.message.reply_text("الصيغة: /ban <user_id> [السبب]")
    try:
        user_id, reason = int(context.args[0]), " ".join(context.args[1:]) or "بدون سبب"
        if is_user_banned(user_id): return await update.message.reply_text(f"المستخدم {user_id} محظور بالفعل.")
        if ban_user(user_id, update.effective_user.id, reason): await update.message.reply_text(f"🚫 تم حظر المستخدم {user_id}.")
    except (ValueError, IndexError): await update.message.reply_text("معرف المستخدم غير صحيح.")

async def unban_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    if not context.args: return await update.message.reply_text("الصيغة: /unban <user_id>")
    try:
        user_id = int(context.args[0])
        if not is_user_banned(user_id): return await update.message.reply_text(f"المستخدم {user_id} ليس محظوراً.")
        if unban_user(user_id): await update.message.reply_text(f"✅ تم رفع الحظر عن المستخدم {user_id}.")
    except (ValueError, IndexError): await update.message.reply_text("معرف المستخدم غير صحيح.")

async def banned_list_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    banned_list = get_banned_users()
    if not banned_list: return await update.message.reply_text("لا يوجد مستخدمون محظورون حالياً.")
    message = f"**🚫 قائمة المحظورين ({len(banned_list)}):**\n\n"
    for item in banned_list:
        banned_at = datetime.fromisoformat(item['banned_at']).strftime('%Y-%m-%d')
        message += f"- ID: `{item['user_id']}`\n  - السبب: {item['reason']}\n"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

# --- Message Handlers ---
async def handle_user_message(update: Update, context: CallbackContext) -> None:
    user, message = update.effective_user, update.message
    if not user or not message or update.effective_chat.id == ADMIN_GROUP_ID: return
    if is_user_banned(user.id): return await message.reply_text("🚫 عذراً، لقد تم حظرك من استخدام هذا البوت.")
    if message.reply_to_message and message.reply_to_message.from_user.is_bot: return await handle_user_reply(update, context)
    
    question_id, raw_content, file_id, message_type, parsed_data, text_to_parse = str(uuid.uuid4()), None, None, "غير معروف", None, None
    
    if message.text: message_type, raw_content, text_to_parse = "نص", message.text, message.text
    elif message.photo: message_type, raw_content, file_id, text_to_parse = "صورة", message.caption or "", message.photo[-1].file_id, message.caption
    elif message.video: message_type, raw_content, file_id, text_to_parse = "فيديو", message.caption or "", message.video.file_id, message.caption
    elif message.voice: message_type, file_id = "رسالة صوتية", message.voice.file_id
    else: return

    if text_to_parse:
        logger.info(f"Sending text to AI for parsing: {text_to_parse[:100]}...")
        parsed_data = parse_question_with_ai(text_to_parse)

    question_data = {'question_id': question_id, 'user_id': user.id, 'username': user.username or "", 'fullname': user.full_name, 'message_type': message_type, 'timestamp': datetime.now().isoformat(), 'message_id': message.message_id, 'file_id': file_id, 'raw_content': raw_content}
    if parsed_data:
        logger.info(f"AI returned: {parsed_data}")
        question_data['question_text'], question_data['options'] = parsed_data.get('question_text'), parsed_data.get('options', [])
    else:
        question_data['question_text'], question_data['options'] = (raw_content if not file_id else ""), []
    questions_data[question_id] = question_data
    save_data(questions_data, DATA_FILE)
    
    str_user_id = str(user.id)
    if str_user_id not in active_users: active_users[str_user_id] = {"first_name": user.first_name, "last_name": user.last_name or "", "username": user.username or "", "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "message_count": 0}
    active_users[str_user_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_users[str_user_id]["message_count"] = active_users[str_user_id].get("message_count", 0) + 1
    save_users_data()
    
    await message.reply_text("👍 رسالتك وصلت بنجاح، شكراً لمساهمتك!")
    await forward_to_admin_group_new(context, question_data)

async def forward_to_admin_group_new(context: CallbackContext, q_data: Dict):
    safe_fullname = escape_legacy_markdown(q_data['fullname'])
    safe_username = escape_legacy_markdown(q_data.get('username', '')) if q_data.get('username') else "غير متوفر"
    user_info = f"**مشاركة جديدة** 📥\n**من:** {safe_fullname}\n**يوزر:** @{safe_username}\n**ID:** `{q_data['user_id']}`\n\n"
    replies_data[q_data['question_id']] = {'user_id': q_data['user_id'], 'user_message_id': q_data['message_id'], 'admin_message_id': None}
    try:
        sent_message, caption = None, user_info + (q_data.get('raw_content') or "")
        if q_data['message_type'] == "نص": sent_message = await context.bot.send_message(ADMIN_GROUP_ID, text=caption, parse_mode=ParseMode.MARKDOWN)
        elif q_data['file_id']:
            if q_data['message_type'] == "صورة": sent_message = await context.bot.send_photo(ADMIN_GROUP_ID, photo=q_data['file_id'], caption=caption, parse_mode=ParseMode.MARKDOWN)
        if sent_message:
            replies_data[q_data['question_id']]['admin_message_id'] = sent_message.message_id
            save_data(replies_data, REPLIES_FILE)
    except Exception as e:
        logger.error(f"Error forwarding to admin group: {e}")

async def handle_user_reply(update: Update, context: CallbackContext) -> None:
    # Logic for user replying to an admin's message
    pass

async def handle_admin_reply_or_broadcast(update: Update, context: CallbackContext) -> None:
    if not update.effective_user: return
    user_id = update.effective_user.id
    if update.message and waiting_for_broadcast.get(user_id, False):
        # Handle broadcast logic
        pass
    elif update.message and update.message.reply_to_message:
        # Handle admin reply logic
        pass
        
async def setup_commands(application: Application) -> None:
    user_commands = [BotCommand("start", "🚀 بدء/عودة للقائمة"), BotCommand("help", "❓ مساعدة")]
    await application.bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())
    admin_commands = [
        BotCommand("stats", "📊 الإحصائيات"), BotCommand("export", "📁 تصدير البيانات"),
        BotCommand("import", "📥 استيراد البيانات"), BotCommand("makepdf", "📄 إنشاء PDF للأسئلة"),
        BotCommand("broadcast", "📡 رسالة جماعية"), BotCommand("ban", "🚫 حظر"),
        BotCommand("unban", "✅ رفع الحظر"), BotCommand("banned", "📋 المحظورين"),
        BotCommand("help", "ℹ️ أوامر المساعدة")
    ]
    if ADMIN_GROUP_ID != 0:
        await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_GROUP_ID))
    await application.bot.set_my_commands([], scope=None)
    logger.info("Bot commands have been set successfully.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Add all command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("import", import_command))
    application.add_handler(CommandHandler("makepdf", makepdf_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("banned", banned_list_command))

    # Add callback and message handlers
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(orders_list|instructions|main_menu|noop)"))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_user_message))
    application.add_handler(MessageHandler(filters.Chat(ADMIN_GROUP_ID) & ~filters.COMMAND, handle_admin_reply_or_broadcast))

    application.post_init = setup_commands
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!"); exit(1)
    if not ADMIN_GROUP_ID or ADMIN_GROUP_ID == 0:
        logger.error("ADMIN_GROUP_ID not set or invalid!"); exit(1)
    main()
