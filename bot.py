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

# In-memory storage for question tracking
questions_data: Dict[str, dict] = {}
replies_data: Dict[str, dict] = {}
waiting_for_broadcast: Dict[int, bool] = {}
banned_users: Dict[str, dict] = {}

# User tracking
active_users: Dict[int, dict] = {}

# Load data from files
def load_data(filename: str) -> Dict:
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return {}

# Save data to files
def save_data(data: Dict, filename: str):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {filename}: {e}")

# Load existing users data if available
def load_users_data():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as file:
                return json.load(file)
        return {}
    except Exception as e:
        logger.error(f"Failed to load users data: {e}")
        return {}

# Save users data to file
def save_users_data():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as file:
            json.dump(active_users, file, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save users data: {e}")

# HELPER FUNCTION to escape markdown characters
def escape_legacy_markdown(text: str) -> str:
    """Escapes characters for Telegram's legacy Markdown."""
    escape_chars = r'_*`['
    return ''.join(['\\' + char if char in escape_chars else char for char in text])

# Initialize data from files on startup
questions_data = load_data(DATA_FILE)
replies_data = load_data(REPLIES_FILE)
banned_users = load_data(BANS_FILE)
active_users = load_users_data()

# Helper functions for question management
def get_user_questions(user_id: int) -> List[Dict]:
    user_q = [q for q in questions_data.values() if q['user_id'] == user_id]
    return sorted(user_q, key=lambda x: x['timestamp'], reverse=True)

def get_all_user_ids() -> List[int]:
    question_user_ids = set(q['user_id'] for q in questions_data.values())
    active_user_ids = set(int(uid) for uid in active_users.keys())
    return list(question_user_ids.union(active_user_ids))

def is_user_banned(user_id: int) -> bool:
    return str(user_id) in banned_users

def ban_user(user_id: int, admin_id: int, reason: str = "No reason provided") -> bool:
    try:
        banned_users[str(user_id)] = {'banned_at': datetime.now().isoformat(), 'banned_by': admin_id, 'reason': reason}
        save_data(banned_users, BANS_FILE)
        return True
    except Exception as e:
        logger.error(f"Failed to ban user {user_id}: {e}")
        return False

def unban_user(user_id: int) -> bool:
    try:
        if str(user_id) in banned_users:
            del banned_users[str(user_id)]
            save_data(banned_users, BANS_FILE)
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to unban user {user_id}: {e}")
        return False

def get_banned_users() -> List[Dict]:
    banned_list = []
    for user_id, ban_data in banned_users.items():
        banned_list.append({'user_id': int(user_id), **ban_data})
    return banned_list

async def set_menu_button(application: Application) -> None:
    try:
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands(type="commands"))
        logger.info("Menu button set to commands")
    except Exception as e:
        logger.error(f"Failed to set menu button: {e}")

async def start_command(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if not user: return
    
    keyboard = [[InlineKeyboardButton("📬 أسئلتي المرسلة", callback_data="orders_list:page:0")], [InlineKeyboardButton("💡 كيف أستخدم البوت؟", callback_data="instructions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_name = user.first_name or "عزيزي"
    welcome_message = f"""
🎯 أهلاً بك يا {user_name}!

مرحباً في **بوت هدفك**، منصتك لمشاركة وتجميع أسئلة اختبار القدرات الحديثة.

📝 **شاركنا بما لديك:**
- نص السؤال
- صورة واضحة
- ملف PDF
- تسجيل صوتي

فريقنا سيستلم مشاركتك لمراجعتها وإضافتها. شكراً لمساهمتك!

👇 استخدم الأزرار للاطلاع على المزيد.
"""
    
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

async def button_handler(update: Update, context: CallbackContext) -> None:
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
            raw_preview = q.get('content', '')[:40] + "..." if len(q.get('content', '')) > 40 else q.get('content', '')
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
        instructions_text = """
💡 **طريقة استخدام البوت:**

📨 **لإرسال سؤال:**
- ببساطة، أرسل أي شيء (نص، صورة، ملف، تسجيل صوتي) مباشرة إلى البوت.

👍 **ماذا يحدث بعد الإرسال؟**
- ستصلك رسالة تأكيد فورية.
- يتم تحويل مساهمتك إلى فريق العمل للمراجعة.

💬 **التواصل مع الإدارة:**
- إذا قام أحد المشرفين بالرد عليك، سيصلك الرد هنا.
- يمكنك الرد عليه مباشرةً وسيتم إيصال ردك إليهم.

📜 **متابعة مساهماتك:**
- اضغط على زر "أسئلتي المرسلة" لرؤية كل ما أرسلته.

🔄 **العودة للقائمة:**
- أرسل /start في أي وقت للعودة إلى هذه القائمة.
"""
        await query.edit_message_text(instructions_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "main_menu":
        await start_command(update, context)

async def how_to_reply_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query: return
    await query.answer(text="💡 يمكنك الرد بعمل رد (Reply) على هذه الرسالة لإيصالها للمشرف.", show_alert=True)

async def stats_command(update: Update, context: CallbackContext) -> None:
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    
    total_questions = len(questions_data)
    unique_users = len(get_all_user_ids())
    type_counts = {}
    for q in questions_data.values():
        type_counts[q['message_type']] = type_counts.get(q['message_type'], 0) + 1
    
    stats_text = f"📈 **نظرة على إحصائيات البوت:**\n\n📥 إجمالي المشاركات: {total_questions}\n👥 عدد المستخدمين الفريدين: {unique_users}\n\n📂 **تصنيف المشاركات حسب النوع:**\n"
    stats_text += "\n".join([f"• {msg_type}: {count}" for msg_type, count in type_counts.items()])
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def export_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        for file_path, name in {DATA_FILE: "questions", REPLIES_FILE: "replies", USERS_FILE: "users", BANS_FILE: "banned"}.items():
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    await update.message.reply_document(document=f, filename=f"{name}_{timestamp}.json")
        await update.message.reply_text(f"✅ **اكتمل تصدير البيانات بنجاح**", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء التصدير: {e}")

async def import_command(update: Update, context: CallbackContext) -> None:
    """Handles the /import command to restore data from a JSON file by replying to the file."""
    global questions_data, replies_data, active_users, banned_users

    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return

    try:
        chat_admins = await context.bot.get_chat_administrators(ADMIN_GROUP_ID)
        admin_ids = [admin.user.id for admin in chat_admins]
        if update.effective_user.id not in admin_ids:
            await update.message.reply_text("🚫 هذا الأمر مخصص لمشرفي الجروب فقط.")
            return
    except Exception as e:
        await update.message.reply_text(f"خطأ في التحقق من صلاحيات المشرف: {e}")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text(
            "⚠️ لاستخدام هذا الأمر، أرسل ملف الـ JSON أولاً، ثم قم بالرد (Reply) على رسالة الملف بالأمر `/import`."
        )
        return

    doc = update.message.reply_to_message.document
    file_name = doc.file_name.lower()
    target_file = None

    if "questions" in file_name: target_file = DATA_FILE
    elif "replies" in file_name: target_file = REPLIES_FILE
    elif "users" in file_name: target_file = USERS_FILE
    elif "banned" in file_name: target_file = BANS_FILE
    else:
        await update.message.reply_text("❌ لم يتم التعرف على الملف. يجب أن يحتوي اسم الملف على `questions`, `replies`, `users`, or `banned`.")
        return

    try:
        json_file = await doc.get_file()
        file_bytes = await json_file.download_as_bytearray()
        json.loads(file_bytes.decode('utf-8'))
        
        with open(target_file, 'wb') as f:
            f.write(file_bytes)
        
        questions_data = load_data(DATA_FILE)
        replies_data = load_data(REPLIES_FILE)
        active_users = load_users_data()
        banned_users = load_data(BANS_FILE)
        
        await update.message.reply_text(f"✅ تم استيراد وتحديث ملف `{target_file}` بنجاح.")

    except json.JSONDecodeError:
        await update.message.reply_text("❌ خطأ: الملف المرفق ليس ملف JSON صالح.")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ غير متوقع: {e}")

async def broadcast_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID or not update.effective_user: return
    user_count = len(get_all_user_ids())
    waiting_for_broadcast[update.effective_user.id] = True
    await update.message.reply_text(f"📡 **وضع الإرسال الجماعي**\n\n👥 سيتم الإرسال إلى: {user_count} مستخدم\n\nالآن، أرسل الرسالة التي تود بثها.")

async def help_command(update: Update, context: CallbackContext) -> None:
    is_admin = update.effective_chat and update.effective_chat.id == ADMIN_GROUP_ID
    help_text = ("**🛠️ قائمة أوامر المشرفين:**\n\n/stats - عرض الإحصائيات\n/export - استخراج البيانات\n/import - استيراد البيانات\n/broadcast - إرسال رسالة جماعية\n/ban `user_id` `[reason]`\n/unban `user_id`\n/banned - قائمة المحظورين") if is_admin else ("**👋 مرحباً بك في قسم المساعدة!**\n\n/start - بدء/عودة للقائمة الرئيسية\n/help - عرض هذه الرسالة")
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def ban_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID or not update.effective_user: return
    if not context.args: return await update.message.reply_text("الصيغة: /ban <user_id> [السبب]")
    try:
        user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) or "بدون سبب"
        if is_user_banned(user_id): return await update.message.reply_text(f"المستخدم {user_id} محظور بالفعل.")
        if ban_user(user_id, update.effective_user.id, reason): await update.message.reply_text(f"🚫 تم حظر المستخدم {user_id}.\nالسبب: {reason}")
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
        message += f"- ID: `{item['user_id']}` (بواسطة {item.get('banned_by', 'غير معروف')})\n  - السبب: {item['reason']} | التاريخ: {banned_at}\n"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def handle_user_message(update: Update, context: CallbackContext) -> None:
    user, message = update.effective_user, update.message
    if not user or not message or update.effective_chat.id == ADMIN_GROUP_ID: return
    if is_user_banned(user.id): return await message.reply_text("🚫 عذراً، لقد تم حظرك من استخدام هذا البوت.")
    if message.reply_to_message and message.reply_to_message.from_user.is_bot: return await handle_user_reply(update, context)
    
    question_id, file_info, content, message_type = str(uuid.uuid4()), None, "", "غير معروف"
    
    if message.text: message_type, content = "نص", message.text
    elif message.photo: message_type, content, file_info = "صورة", message.caption or "", message.photo[-1].file_id
    elif message.video: message_type, content, file_info = "فيديو", message.caption or "", message.video.file_id
    elif message.document: message_type, content, file_info = "ملف", message.caption or message.document.file_name, message.document.file_id
    elif message.voice: message_type, file_info = "رسالة صوتية", message.voice.file_id
    elif message.audio: message_type, content, file_info = "ملف صوتي", message.caption or "", message.audio.file_id
    elif message.sticker: message_type, content, file_info = "ملصق", message.sticker.emoji or "", message.sticker.file_id
    else: return

    question_data = {'question_id': question_id, 'user_id': user.id, 'username': user.username or "", 'fullname': user.full_name, 'message_type': message_type, 'content': content, 'file_id': file_info, 'timestamp': datetime.now().isoformat(), 'message_id': message.message_id}
    questions_data[question_id] = question_data
    save_data(questions_data, DATA_FILE)
    
    str_user_id = str(user.id)
    if str_user_id not in active_users: active_users[str_user_id] = {"first_name": user.first_name, "last_name": user.last_name or "", "username": user.username or "", "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "message_count": 0}
    active_users[str_user_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_users[str_user_id]["message_count"] = active_users[str_user_id].get("message_count", 0) + 1
    save_users_data()
    
    await message.reply_text("👍 رسالتك وصلت بنجاح، شكراً لمساهمتك!")
    await forward_to_admin_group_new(context, question_data)
    
    if len(questions_data) > 0 and len(questions_data) % 50 == 0:
        await context.bot.send_message(ADMIN_GROUP_ID, text=f"🎉 تهانينا! وصلنا إلى المشاركة رقم {len(questions_data)}.")

async def forward_to_admin_group_new(context: CallbackContext, q_data: Dict):
    safe_fullname = escape_legacy_markdown(q_data['fullname'])
    safe_username = escape_legacy_markdown(q_data['username']) if q_data['username'] else "غير متوفر"
    
    user_info = f"**مشاركة جديدة** 📥\n**من:** {safe_fullname}\n**يوزر:** @{safe_username}\n**ID:** `{q_data['user_id']}`\n\n"
    replies_data[q_data['question_id']] = {'user_id': q_data['user_id'], 'user_message_id': q_data['message_id'], 'admin_message_id': None}
    
    try:
        sent_message, caption = None, user_info + (q_data.get('content') or "")
        if q_data['message_type'] == "نص": sent_message = await context.bot.send_message(ADMIN_GROUP_ID, text=caption, parse_mode=ParseMode.MARKDOWN)
        elif q_data['message_type'] == "صورة": sent_message = await context.bot.send_photo(ADMIN_GROUP_ID, photo=q_data['file_id'], caption=caption, parse_mode=ParseMode.MARKDOWN)
        elif q_data['message_type'] == "فيديو": sent_message = await context.bot.send_video(ADMIN_GROUP_ID, video=q_data['file_id'], caption=caption, parse_mode=ParseMode.MARKDOWN)
        elif q_data['message_type'] == "ملف": sent_message = await context.bot.send_document(ADMIN_GROUP_ID, document=q_data['file_id'], caption=caption, parse_mode=ParseMode.MARKDOWN)
        elif q_data['message_type'] == "ملصق": 
            await context.bot.send_message(ADMIN_GROUP_ID, text=user_info, parse_mode=ParseMode.MARKDOWN)
            sent_message = await context.bot.send_sticker(ADMIN_GROUP_ID, sticker=q_data['file_id'])
        else: # Voice, Audio
            await context.bot.send_message(ADMIN_GROUP_ID, text=user_info, parse_mode=ParseMode.MARKDOWN)
            if q_data['message_type'] == "رسالة صوتية": sent_message = await context.bot.send_voice(ADMIN_GROUP_ID, voice=q_data['file_id'])
            elif q_data['message_type'] == "ملف صوتي": sent_message = await context.bot.send_audio(ADMIN_GROUP_ID, audio=q_data['file_id'])

        if sent_message:
            replies_data[q_data['question_id']]['admin_message_id'] = sent_message.message_id
            save_data(replies_data, REPLIES_FILE)
    except Exception as e:
        logger.error(f"Error forwarding to admin group: {e}")

async def handle_user_reply(update: Update, context: CallbackContext) -> None:
    if not update.message or not update.message.reply_to_message: return
    
    user_reply_msg_id = update.message.reply_to_message.message_id
    question_id, admin_msg_id = None, None
    for qid, data in replies_data.items():
        if any(reply.get('user_reply_message_id') == user_reply_msg_id for reply in data.get('admin_replies', [])):
            question_id = qid
            admin_msg_id = next(reply['admin_message_id'] for reply in data['admin_replies'] if reply.get('user_reply_message_id') == user_reply_msg_id)
            break
    if not question_id or not admin_msg_id: return
    
    try:
        reply_header = f"رد من الطالب (ID: `{replies_data[question_id]['user_id']}`)"
        
        sent_to_admin_id_obj = await update.message.copy(
            chat_id=ADMIN_GROUP_ID, 
            reply_to_message_id=admin_msg_id
        )
        
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=reply_header,
            reply_to_message_id=sent_to_admin_id_obj.message_id,
            parse_mode=ParseMode.MARKDOWN
        )

        if 'admin_thread_message_ids' not in replies_data[question_id]:
            replies_data[question_id]['admin_thread_message_ids'] = []
        replies_data[question_id]['admin_thread_message_ids'].append(sent_to_admin_id_obj.message_id)
        save_data(replies_data, REPLIES_FILE)
        
        await update.message.reply_text("✅ تم إرسال ردك.")
    except Exception as e:
        logger.error(f"Error forwarding user reply to admin: {e}")

async def handle_admin_reply(update: Update, context: CallbackContext) -> None:
    if not update.message or not update.message.reply_to_message: return
    replied_msg_id = update.message.reply_to_message.message_id
    question_id = next((qid for qid, data in replies_data.items() if data.get('admin_message_id') == replied_msg_id or replied_msg_id in data.get('admin_thread_message_ids', [])), None)
    if not question_id: return
    
    reply_data = replies_data[question_id]
    user_id, user_msg_id = reply_data['user_id'], reply_data['user_message_id']
    
    keyboard = [[InlineKeyboardButton("💡 كيفية الرد", callback_data="how_to_reply")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        sent_message = await update.message.copy(chat_id=user_id, reply_to_message_id=user_msg_id, reply_markup=reply_markup)
        
        if sent_message:
            if 'admin_replies' not in reply_data: reply_data['admin_replies'] = []
            reply_data['admin_replies'].append({'admin_message_id': update.message.message_id, 'user_reply_message_id': sent_message.message_id})
            save_data(replies_data, REPLIES_FILE)
            await update.message.reply_text("✅ تم إرسال ردك للطالب بنجاح.")
    except Exception as e:
        logger.error(f"Error sending reply to user: {e}")
        await update.message.reply_text(f"❌ فشل إرسال الرد. قد يكون المستخدم قد حظر البوت.\nالخطأ: {e}")

async def handle_broadcast_message(update: Update, context: CallbackContext) -> None:
    if not update.message: return
    user_ids = get_all_user_ids()
    if not user_ids: return await update.message.reply_text("لا يوجد مستخدمون لإرسال الرسالة إليهم.")
    
    await update.message.reply_text(f"⏳ جارٍ بدء الإرسال إلى {len(user_ids)} مستخدم...")
    successful, failed = 0, 0
    for user_id in user_ids:
        try:
            await context.bot.copy_message(user_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            successful += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user_id}: {e}")
            failed += 1
    
    await update.message.reply_text(f"**📣 اكتمل الإرسال الجماعي:**\n👍 نجح: {successful}\n👎 فشل: {failed}", parse_mode=ParseMode.MARKDOWN)

async def setup_commands(application: Application) -> None:
    user_commands = [BotCommand("start", "🚀 بدء/عودة للقائمة"), BotCommand("help", "❓ مساعدة")]
    await application.bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())
    
    admin_commands = [
        BotCommand("stats", "📊 الإحصائيات"), BotCommand("export", "📁 تصدير البيانات"),
        BotCommand("import", "📥 استيراد البيانات"), BotCommand("broadcast", "📡 رسالة جماعية"),
        BotCommand("ban", "🚫 حظر"), BotCommand("unban", "✅ رفع الحظر"),
        BotCommand("banned", "📋 المحظورين")
    ]
    if ADMIN_GROUP_ID != 0:
      await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_GROUP_ID))
    
    await application.bot.set_my_commands([], scope=None)
    logger.info("Bot commands have been set successfully.")

async def handle_admin_reply_or_broadcast(update: Update, context: CallbackContext) -> None:
    if not update.effective_user: return
    user_id = update.effective_user.id
    if update.message and waiting_for_broadcast.get(user_id, False):
        await handle_broadcast_message(update, context)
        waiting_for_broadcast[user_id] = False
    elif update.message and update.message.reply_to_message:
        await handle_admin_reply(update, context)

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("banned", banned_list_command))
    application.add_handler(CommandHandler("import", import_command))
    
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(orders_list|instructions|main_menu)"))
    application.add_handler(CallbackQueryHandler(how_to_reply_callback, pattern="^how_to_reply$"))
    
    # Message Handlers
    all_media_filters = (filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL | filters.VIDEO | filters.Sticker.ALL)
    
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND & all_media_filters, handle_user_message))
    application.add_handler(MessageHandler(filters.Chat(ADMIN_GROUP_ID) & ~filters.COMMAND & all_media_filters, handle_admin_reply_or_broadcast))

    application.post_init = setup_commands
    application.run_polling(allowed_updates=Update.ALL_TYPES)
from flask import Flask
import threading

# Flask web server for Render health check
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running fine!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Start the web server in a separate thread
threading.Thread(target=run_web_server).start()
if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        exit(1)
    if not ADMIN_GROUP_ID or ADMIN_GROUP_ID == 0:
        logger.error("ADMIN_GROUP_ID environment variable is not set or invalid!")
        exit(1)
    main()
