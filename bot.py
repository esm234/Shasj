#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re 
import logging
import uuid
import asyncio
import threading
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
from flask import Flask

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

# Load Topic IDs from .env for six banks
TOPIC_IDS = {
    '1': int(os.getenv("TOPIC_ID_BANK_1", "0")),
    '2': int(os.getenv("TOPIC_ID_BANK_2", "0")),
    '3': int(os.getenv("TOPIC_ID_BANK_3", "0")),
    '4': int(os.getenv("TOPIC_ID_BANK_4", "0")),
    '5': int(os.getenv("TOPIC_ID_BANK_5", "0")),
    '6': int(os.getenv("TOPIC_ID_BANK_6", "0")),
}

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

# --- DATA HANDLING FUNCTIONS ---
def load_data(filename: str) -> Dict:
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return {}

def save_data(data: Dict, filename: str):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {filename}: {e}")

def load_users_data():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as file:
                return json.load(file)
        return {}
    except Exception as e:
        logger.error(f"Failed to load users data: {e}")
        return {}

def save_users_data():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as file:
            json.dump(active_users, file, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save users data: {e}")

def escape_legacy_markdown(text: str) -> str:
    escape_chars = r'_*`['
    return ''.join(['\\' + char if char in escape_chars else char for char in text])

# Initialize data from files on startup
questions_data = load_data(DATA_FILE)
replies_data = load_data(REPLIES_FILE)
banned_users = load_data(BANS_FILE)
active_users = load_users_data()

# --- HELPER FUNCTIONS ---
def is_user_banned(user_id: int) -> bool: return str(user_id) in banned_users
def get_all_user_ids() -> List[int]:
    question_user_ids = set(q['user_id'] for q in questions_data.values())
    active_user_ids = set(int(uid) for uid in active_users.keys())
    return list(question_user_ids.union(active_user_ids))

# --- USER-FACING COMMANDS AND HANDLERS ---
async def start_command(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if not user: return

    if is_user_banned(user.id):
        if update.message:
            await update.message.reply_text("🚫 عذراً، لقد تم حظرك من استخدام هذا البوت.")
        elif update.callback_query:
            await update.callback_query.answer(text="🚫 عذراً، لقد تم حظرك من استخدام هذا البوت.", show_alert=True)
        return

    context.user_data.pop('selected_bank', None)
    
    keyboard = [
        [InlineKeyboardButton("🏦 البنك الأول", callback_data="select_bank:1"), InlineKeyboardButton("🏦 البنك الثاني", callback_data="select_bank:2")],
        [InlineKeyboardButton("🏦 البنك الثالث", callback_data="select_bank:3"), InlineKeyboardButton("🏦 البنك الرابع", callback_data="select_bank:4")],
        [InlineKeyboardButton("🏦 البنك الخامس", callback_data="select_bank:5"), InlineKeyboardButton("🏦 البنك السادس", callback_data="select_bank:6")],
        [InlineKeyboardButton("💡 كيف أستخدم البوت؟", callback_data="instructions")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_name = user.first_name or "عزيزي"
    welcome_message = f"""
👋 أهلاً بك يا {user_name}!

هذا البوت مخصص للاستفسار عن أسئلة البنوك.

**خطوات الاستفسار:**
1.  اختر البنك الذي ينتمي إليه سؤالك من الأزرار بالأسفل.
2.  أرسل **صورة** السؤال.
3.  اكتب استفسارك في **شرح الصورة (الكابشن)**.

سيتم توجيه سؤالك مباشرةً للقسم المختص للرد عليك.
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

async def select_bank_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query or not query.from_user: return
    await query.answer()

    bank_number = query.data.split(':')[-1]
    context.user_data['selected_bank'] = bank_number
    
    message_text = f"""
✅ تم اختيار **البنك رقم ({bank_number})**.

الآن، قم بإرسال **صورة السؤال** الذي تود الاستفسار عنه.

⚠️ **هام جداً:** يجب أن تكتب استفسارك في **شرح الصورة (الكابشن)** قبل إرسالها.
"""
    keyboard = [
        [InlineKeyboardButton("❓ كيف أضيف شرح (كابشن)؟", callback_data="caption_help")],
        [InlineKeyboardButton("🔙 تغيير البنك", callback_data="main_menu")]
    ]
    await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def caption_help_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query: return
    help_text = "عند اختيارك للصورة من معرض الصور، ستجد خانة لإضافة شرح أو تعليق قبل الضغط على زر الإرسال. اكتب استفسارك في هذه الخانة."
    await query.answer(text=help_text, show_alert=True)
    
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query or not query.from_user: return
    await query.answer()

    if query.data == "instructions":
        instructions_text = """
💡 **طريقة استخدام البوت:**

1️⃣ *اختر البنك*:
   - من القائمة الرئيسية، اضغط على زر البنك الذي يحتوي على سؤالك.

2️⃣ *أرسل السؤال*:
   - اختر **صورة** واضحة للسؤال من جهازك.

3️⃣ *أضف استفسارك (هام)*:
   - قبل أن تضغط على إرسال، اكتب استفسارك في **خانة الشرح (الكابشن)** المرفقة مع الصورة. **لن يتم قبول أي صورة بدون شرح.**

✅ *تم الإرسال!*
   - ستصلك رسالة تأكيد، وسيتم تحويل استفسارك مباشرةً للفريق المختص.

🔄 **للعودة للقائمة الرئيسية**:
- أرسل /start في أي وقت.
"""
        await query.edit_message_text(instructions_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]), parse_mode=ParseMode.MARKDOWN)
    
    elif query.data == "main_menu":
        await start_command(update, context)

# --- NEW: Handler for the "How to Reply" button ---
async def how_to_reply_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query: return
    reply_instructions = "للرد على المشرف، قم بعمل 'رد' (Reply) على هذه الرسالة وسيصل ردك إليه مباشرةً."
    await query.answer(text=reply_instructions, show_alert=True)

# --- CORE MESSAGE HANDLING LOGIC ---
async def handle_user_reply(update: Update, context: CallbackContext) -> None:
    if not update.message or not update.message.reply_to_message or not update.effective_user: return
    if is_user_banned(update.effective_user.id): return

    replied_to_msg_id = str(update.message.reply_to_message.message_id)
    question_id, originating_admin_msg_id = None, None

    for qid, data in replies_data.items():
        if replied_to_msg_id in data.get('message_map', {}):
            question_id = qid
            originating_admin_msg_id = data['message_map'][replied_to_msg_id]
            break
            
    if not question_id: return
    try:
        question_info = questions_data.get(question_id)
        if not question_info: return logger.error(f"Data inconsistency for QID {question_id}")
        topic_id = TOPIC_IDS.get(question_info.get('bank_number'))

        new_admin_msg = await update.message.copy(
            chat_id=ADMIN_GROUP_ID, message_thread_id=topic_id, reply_to_message_id=originating_admin_msg_id
        )

        replies_data[question_id]['message_map'][str(update.message.message_id)] = new_admin_msg.message_id
        replies_data[question_id]['admin_thread_ids'].append(new_admin_msg.message_id)
        save_data(replies_data, REPLIES_FILE)
        await update.message.reply_text("✅ تم إرسال ردك.")
    except Exception as e:
        logger.error(f"Failed to forward user reply for QID {question_id}: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء إرسال ردك.")

async def handle_photo_question(update: Update, context: CallbackContext) -> None:
    user, message = update.effective_user, update.message
    if not user or not message or is_user_banned(user.id):
        if user and is_user_banned(user.id): await message.reply_text("🚫 عذراً، لقد تم حظرك من استخدام هذا البوت.")
        return

    selected_bank = context.user_data.get('selected_bank')
    if not selected_bank:
        await message.reply_text("⚠️ لم تختر البنك بعد! الرجاء الضغط على /start واختيار البنك أولاً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ابدأ الآن", callback_data="main_menu")]]))
        return
        
    if not message.caption:
        await message.reply_text("❌ عذراً، يجب إضافة استفسارك في **شرح الصورة (الكابشن)**. يرجى إعادة إرسال الصورة مع الشرح.", parse_mode=ParseMode.MARKDOWN)
        return

    question_id = str(uuid.uuid4())
    question_data = {
        'question_id': question_id, 'user_id': user.id, 'username': user.username or "", 'fullname': user.full_name,
        'message_type': 'صورة', 'content': message.caption, 'file_id': message.photo[-1].file_id,
        'timestamp': datetime.now().isoformat(), 'message_id': message.message_id, 'bank_number': selected_bank,
    }
    questions_data[question_id] = question_data
    save_data(questions_data, DATA_FILE)
    
    str_user_id = str(user.id)
    if str_user_id not in active_users: active_users[str_user_id] = {"first_name": user.first_name, "last_name": user.last_name or "", "username": user.username or "", "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "message_count": 0}
    active_users[str_user_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_users[str_user_id]["message_count"] = active_users[str_user_id].get("message_count", 0) + 1
    save_users_data()

    context.user_data.pop('selected_bank', None)
    await message.reply_text("👍 استفسارك وصل بنجاح، شكراً لك! سيتم الرد عليك قريباً.\n\nيمكنك إرسال استفسار جديد بالضغط على /start.")
    
    topic_id = TOPIC_IDS.get(selected_bank)
    await forward_to_admin_topic(context, question_data, topic_id if topic_id and topic_id != 0 else None)

async def handle_text_message(update: Update, context: CallbackContext) -> None:
    user, message = update.effective_user, update.message
    if not user or not message: return
    if is_user_banned(user.id): 
        await message.reply_text("🚫 عذراً، لقد تم حظرك من استخدام هذا البوت.")
        return

    if context.user_data.get('selected_bank'):
        await message.reply_text("⏳ في انتظار الصورة... الرجاء إرسال **صورة** السؤال الآن.", parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_text("لبدء إرسال استفسار، يرجى الضغط على /start واختيار البنك أولاً.")


async def forward_to_admin_topic(context: CallbackContext, q_data: Dict, topic_id: int or None):
    safe_fullname = escape_legacy_markdown(q_data['fullname'])
    safe_username = escape_legacy_markdown(q_data['username']) if q_data['username'] else "غير متوفر"
    
    caption = (f"**استفسار جديد - بنك رقم {q_data['bank_number']}** 📥\n"
               f"**التوجيه إلى Topic ID:** `{topic_id}`\n"
               f"**من:** {safe_fullname}\n"
               f"**يوزر:** @{safe_username}\n"
               f"**ID المستخدم:** `{q_data['user_id']}`\n\n"
               f"**نص الاستفسار:**\n{q_data.get('content') or ''}")

    replies_data[q_data['question_id']] = {'user_id': q_data['user_id'], 'user_message_id': q_data['message_id'], 'admin_message_id': None}
    
    try:
        sent_message = await context.bot.send_photo(
            chat_id=ADMIN_GROUP_ID, photo=q_data['file_id'], caption=caption,
            parse_mode=ParseMode.MARKDOWN, message_thread_id=topic_id
        )
        if sent_message:
            replies_data[q_data['question_id']]['admin_message_id'] = sent_message.message_id
            save_data(replies_data, REPLIES_FILE)
    except Exception as e:
        logger.error(f"Error forwarding to admin group topic {topic_id}: {e}")
        
### MODIFIED ###
async def handle_admin_reply(update: Update, context: CallbackContext) -> None:
    admin_message = update.message
    if not admin_message or not admin_message.reply_to_message: return
    
    replied_msg_id = admin_message.reply_to_message.message_id
    question_id = None
    
    for qid, data in replies_data.items():
        if data.get('admin_message_id') == replied_msg_id or replied_msg_id in data.get('admin_thread_ids', []):
            question_id = qid
            break
            
    if not question_id: return
    
    reply_data = replies_data[question_id]
    user_id = reply_data['user_id']
    sent_message_to_user = None
    
    # Create the "How to Reply" button
    reply_button = InlineKeyboardButton("💡 كيفية الرد", callback_data="how_to_reply")
    reply_markup = InlineKeyboardMarkup([[reply_button]])

    try:
        if admin_message.text:
            sent_message_to_user = await context.bot.send_message(chat_id=user_id, text=admin_message.text, reply_markup=reply_markup)
        elif admin_message.photo:
            sent_message_to_user = await context.bot.send_photo(chat_id=user_id, photo=admin_message.photo[-1].file_id, caption=admin_message.caption, reply_markup=reply_markup)
        elif admin_message.sticker:
            sent_message_to_user = await context.bot.send_sticker(chat_id=user_id, sticker=admin_message.sticker.file_id, reply_markup=reply_markup)
        elif admin_message.voice:
            sent_message_to_user = await context.bot.send_voice(chat_id=user_id, voice=admin_message.voice.file_id, reply_markup=reply_markup)
        elif admin_message.video:
             sent_message_to_user = await context.bot.send_video(chat_id=user_id, video=admin_message.video.file_id, caption=admin_message.caption, reply_markup=reply_markup)
        else:
             sent_message_to_user = await admin_message.copy(chat_id=user_id, reply_markup=reply_markup)

        if not sent_message_to_user:
            raise ValueError("Failed to send message to user.")

        if 'admin_thread_ids' not in reply_data: reply_data['admin_thread_ids'] = []
        if 'message_map' not in reply_data: reply_data['message_map'] = {}
        
        reply_data['message_map'][str(sent_message_to_user.message_id)] = admin_message.message_id
        reply_data['admin_thread_ids'].append(admin_message.message_id)
        save_data(replies_data, REPLIES_FILE)
        
        await admin_message.reply_text("✅ تم إرسال ردك للطالب بنجاح.")

    except Exception as e:
        logger.error(f"Error sending reply to user: {e}")
        await admin_message.reply_text(f"❌ فشل إرسال الرد. قد يكون المستخدم قد حظر البوت.\nالخطأ: {e}")

def _get_user_id_from_thread(replied_msg_id: int) -> int or None:
    question_id = None
    for qid, data in replies_data.items():
        if data.get('admin_message_id') == replied_msg_id or replied_msg_id in data.get('admin_thread_ids', []):
            question_id = qid
            break
    if question_id and question_id in questions_data:
        return questions_data[question_id].get('user_id')
    return None

async def ban_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID or not update.effective_user: return
    
    user_id_to_ban, reason = None, "بدون سبب"

    if update.message.reply_to_message:
        replied_msg_id = update.message.reply_to_message.message_id
        user_id_to_ban = _get_user_id_from_thread(replied_msg_id)
        reason = " ".join(context.args) if context.args else "بدون سبب"
    else:
        if not context.args:
            return await update.message.reply_text("الصيغة: /ban <user_id> [السبب]\nأو قم بالرد على رسالة المستخدم بالأمر /ban")
        try:
            user_id_to_ban = int(context.args[0])
            reason = " ".join(context.args[1:]) or "بدون سبب"
        except (ValueError, IndexError):
            return await update.message.reply_text("معرف المستخدم غير صحيح.")

    if not user_id_to_ban:
        return await update.message.reply_text("لم يتم العثور على ID المستخدم. تأكد من الرد على رسالة داخل محادثة.")

    if is_user_banned(user_id_to_ban):
        return await update.message.reply_text(f"المستخدم {user_id_to_ban} محظور بالفعل.")
        
    banned_users[str(user_id_to_ban)] = {'banned_at': datetime.now().isoformat(), 'banned_by': update.effective_user.id, 'reason': reason}
    save_data(banned_users, BANS_FILE)
    await update.message.reply_text(f"🚫 تم حظر المستخدم `{user_id_to_ban}`.\nالسبب: {reason}", parse_mode=ParseMode.MARKDOWN)

async def unban_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    user_id_to_unban = None

    if update.message.reply_to_message:
        replied_msg_id = update.message.reply_to_message.message_id
        user_id_to_unban = _get_user_id_from_thread(replied_msg_id)
    else:
        if not context.args:
            return await update.message.reply_text("الصيغة: /unban <user_id>\nأو قم بالرد على رسالة المستخدم بالأمر /unban")
        try:
            user_id_to_unban = int(context.args[0])
        except (ValueError, IndexError):
            return await update.message.reply_text("معرف المستخدم غير صحيح.")

    if not user_id_to_unban:
        return await update.message.reply_text("لم يتم العثور على ID المستخدم. تأكد من الرد على رسالة داخل محادثة.")

    if not is_user_banned(user_id_to_unban):
        return await update.message.reply_text(f"المستخدم {user_id_to_unban} ليس محظوراً.")
        
    if str(user_id_to_unban) in banned_users:
        del banned_users[str(user_id_to_unban)]
    save_data(banned_users, BANS_FILE)
    await update.message.reply_text(f"✅ تم رفع الحظر عن المستخدم `{user_id_to_unban}`.", parse_mode=ParseMode.MARKDOWN)
    
async def stats_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    total_questions, unique_users, bank_counts = len(questions_data), len(get_all_user_ids()), {}
    for q in questions_data.values():
        bank_num = q.get('bank_number', 'N/A'); bank_counts[bank_num] = bank_counts.get(bank_num, 0) + 1
    stats_text = (f"📈 **إحصائيات البوت:**\n\n📥 إجمالي الاستفسارات: {total_questions}\n👥 المستخدمون الفريدون: {unique_users}\n\n"
                  f"🏦 **الاستفسارات حسب البنك:**\n" + "\n".join([f"• بنك {b}: {c}" for b, c in bank_counts.items()]))
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def export_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        for file_path, name in {DATA_FILE: "questions", REPLIES_FILE: "replies", USERS_FILE: "users", BANS_FILE: "banned"}.items():
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    await update.message.reply_document(document=f, filename=f"{name}_{timestamp}.json")
        await update.message.reply_text("✅ **اكتمل تصدير البيانات بنجاح**", parse_mode=ParseMode.MARKDOWN)
    except Exception as e: await update.message.reply_text(f"❌ حدث خطأ أثناء التصدير: {e}")

async def import_command(update: Update, context: CallbackContext) -> None:
    global questions_data, replies_data, active_users, banned_users
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        return await update.message.reply_text("⚠️ لاستخدام هذا الأمر، أرسل ملف JSON ثم قم بالرد عليه بالأمر `/import`.")
    doc = update.message.reply_to_message.document; file_name = doc.file_name.lower()
    target_file = None
    if "questions" in file_name: target_file = DATA_FILE
    elif "replies" in file_name: target_file = REPLIES_FILE
    elif "users" in file_name: target_file = USERS_FILE
    elif "banned" in file_name: target_file = BANS_FILE
    else: return await update.message.reply_text("❌ لم يتم التعرف على الملف.")
    try:
        file_bytes = await (await doc.get_file()).download_as_bytearray()
        json.loads(file_bytes.decode('utf-8'))
        with open(target_file, 'wb') as f: f.write(file_bytes)
        questions_data, replies_data, active_users, banned_users = load_data(DATA_FILE), load_data(REPLIES_FILE), load_users_data(), load_data(BANS_FILE)
        await update.message.reply_text(f"✅ تم استيراد وتحديث `{target_file}` بنجاح.")
    except Exception as e: await update.message.reply_text(f"❌ حدث خطأ: {e}")

async def broadcast_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID or not update.effective_user: return
    user_count = len(get_all_user_ids())
    waiting_for_broadcast[update.effective_user.id] = True
    await update.message.reply_text(f"📡 **وضع الإرسال الجماعي**\nسيتم الإرسال إلى: {user_count} مستخدم.\n\nأرسل الآن الرسالة التي تود بثها.")

async def handle_broadcast_message(update: Update, context: CallbackContext) -> None:
    if not update.message or not update.effective_user: return
    admin_id = update.effective_user.id
    if waiting_for_broadcast.get(admin_id):
        user_ids = get_all_user_ids()
        if not user_ids: await update.message.reply_text("لا يوجد مستخدمون لإرسال الرسالة إليهم.")
        else:
            await update.message.reply_text(f"⏳ جارٍ بدء الإرسال إلى {len(user_ids)} مستخدم...")
            successful, failed = 0, 0
            for user_id in user_ids:
                try:
                    await context.bot.copy_message(user_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
                    successful += 1; await asyncio.sleep(0.05)
                except Exception as e: logger.error(f"Failed to broadcast to {user_id}: {e}"); failed += 1
            await update.message.reply_text(f"**📣 اكتمل الإرسال:**\n👍 نجح: {successful}\n👎 فشل: {failed}", parse_mode=ParseMode.MARKDOWN)
        waiting_for_broadcast[admin_id] = False

async def help_command(update: Update, context: CallbackContext) -> None:
    is_admin = update.effective_chat and update.effective_chat.id == ADMIN_GROUP_ID
    help_text = ("**🛠️ أوامر المشرفين:**\n/stats\n/export\n/import\n/broadcast\n/ban `id` `[reason]`\n/unban `id`\n/banned") if is_admin else ("**👋 للمساعدة:**\n/start - بدء/عودة للقائمة الرئيسية")
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def banned_list_command(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID: return
    if not banned_users: return await update.message.reply_text("لا يوجد مستخدمون محظورون حالياً.")
    message = f"**🚫 قائمة المحظورين ({len(banned_users)}):**\n\n" + "\n".join([f"- ID: `{uid}` | السبب: {data['reason']}" for uid, data in banned_users.items()])
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def handle_admin_messages(update: Update, context: CallbackContext) -> None:
    if not update.message or not update.effective_user: return
    if update.message.reply_to_message:
        await handle_admin_reply(update, context)
    elif waiting_for_broadcast.get(update.effective_user.id):
        await handle_broadcast_message(update, context)

app = Flask(__name__)
@app.route('/')
def index(): return "Bot is running!"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    commands = {"start": start_command, "help": help_command, "stats": stats_command, "export": export_command, 
                "import": import_command, "broadcast": broadcast_command, "ban": ban_command, 
                "unban": unban_command, "banned": banned_list_command}
    for cmd, func in commands.items(): application.add_handler(CommandHandler(cmd, func))

    # Add the new callback handler for the reply button
    application.add_handler(CallbackQueryHandler(how_to_reply_callback, pattern="^how_to_reply$"))
    
    application.add_handler(CallbackQueryHandler(select_bank_handler, pattern="^select_bank:"))
    application.add_handler(CallbackQueryHandler(caption_help_handler, pattern="^caption_help$"))
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(instructions|main_menu)"))
    
    all_media_filters = (filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL | filters.VIDEO | filters.Sticker.ALL)
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.REPLY & ~filters.COMMAND & all_media_filters, handle_user_reply))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO & ~filters.COMMAND, handle_photo_question))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    application.add_handler(MessageHandler(filters.Chat(ADMIN_GROUP_ID) & ~filters.COMMAND, handle_admin_messages))

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    if not BOT_TOKEN or not ADMIN_GROUP_ID:
        logger.error("BOT_TOKEN or ADMIN_GROUP_ID environment variables are not set!")
        exit(1)
    
    threading.Thread(target=run_web_server, daemon=True).start()
    main()
