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

# MODIFIED: Load Topic IDs from .env
TOPIC_IDS = {
    '1': int(os.getenv("TOPIC_ID_BANK_1", "0")),
    '2': int(os.getenv("TOPIC_ID_BANK_2", "0")),
    '3': int(os.getenv("TOPIC_ID_BANK_3", "0")),
    '4': int(os.getenv("TOPIC_ID_BANK_4", "0")),
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

# Load/Save data functions (unchanged)
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

# Helper functions for Ban management (unchanged)
def is_user_banned(user_id: int) -> bool: return str(user_id) in banned_users
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
    
def get_all_user_ids() -> List[int]:
    question_user_ids = set(q['user_id'] for q in questions_data.values())
    active_user_ids = set(int(uid) for uid in active_users.keys())
    return list(question_user_ids.union(active_user_ids))

# --- BOT COMMANDS AND HANDLERS ---

# MODIFIED: start_command now shows question banks
async def start_command(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if not user: return
    
    # Reset user state
    context.user_data.pop('selected_bank', None)
    
    keyboard = [
        [InlineKeyboardButton("🏦 البنك الأول", callback_data="select_bank:1"), InlineKeyboardButton("🏦 البنك الثاني", callback_data="select_bank:2")],
        [InlineKeyboardButton("🏦 البنك الثالث", callback_data="select_bank:3"), InlineKeyboardButton("🏦 البنك الرابع", callback_data="select_bank:4")],
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

# NEW: Handler for bank selection buttons
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

# NEW: Handler for the caption help button (popup)
async def caption_help_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    if not query: return
    help_text = "عند اختيارك للصورة من معرض الصور، ستجد خانة لإضافة شرح أو تعليق قبل الضغط على زر الإرسال. اكتب استفسارك في هذه الخانة."
    await query.answer(text=help_text, show_alert=True)
    
# MODIFIED: Button handler for main menu and instructions
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

# NEW: Main handler for user photo submissions
async def handle_photo_question(update: Update, context: CallbackContext) -> None:
    user, message = update.effective_user, update.message
    if not user or not message or is_user_banned(user.id):
        if is_user_banned(user.id): await message.reply_text("🚫 عذراً، لقد تم حظرك من استخدام هذا البوت.")
        return

    # 1. Check if a bank has been selected
    selected_bank = context.user_data.get('selected_bank')
    if not selected_bank:
        await message.reply_text("⚠️ لم تختر البنك بعد! الرجاء الضغط على /start واختيار البنك أولاً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ابدأ الآن", callback_data="main_menu")]]))
        return
        
    # 2. Check if the photo has a caption
    if not message.caption:
        await message.reply_text("❌ عذراً، يجب إضافة استفسارك في **شرح الصورة (الكابشن)**. يرجى إعادة إرسال الصورة مع الشرح.", parse_mode=ParseMode.MARKDOWN)
        return

    # 3. Process the question
    question_id = str(uuid.uuid4())
    question_data = {
        'question_id': question_id,
        'user_id': user.id,
        'username': user.username or "",
        'fullname': user.full_name,
        'message_type': 'صورة',
        'content': message.caption, # Caption is the content
        'file_id': message.photo[-1].file_id,
        'timestamp': datetime.now().isoformat(),
        'message_id': message.message_id,
        'bank_number': selected_bank,
    }
    questions_data[question_id] = question_data
    save_data(questions_data, DATA_FILE)
    
    # Update user stats
    str_user_id = str(user.id)
    if str_user_id not in active_users: active_users[str_user_id] = {"first_name": user.first_name, "last_name": user.last_name or "", "username": user.username or "", "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "message_count": 0}
    active_users[str_user_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_users[str_user_id]["message_count"] = active_users[str_user_id].get("message_count", 0) + 1
    save_users_data()

    # Reset state and confirm
    context.user_data.pop('selected_bank', None)
    await message.reply_text("👍 استفسارك وصل بنجاح، شكراً لك! سيتم الرد عليك قريباً.\n\nيمكنك إرسال استفسار جديد بالضغط على /start.")
    
    # Forward to the correct topic in the admin group
    topic_id = TOPIC_IDS.get(selected_bank)
    if topic_id and topic_id != 0:
        await forward_to_admin_topic(context, question_data, topic_id)
    else:
        logger.warning(f"No valid Topic ID found for bank {selected_bank}. Forwarding to main group.")
        await forward_to_admin_topic(context, question_data, None) # Forward to general group if topic not found

# NEW: Handler to guide users sending text instead of photos
async def handle_text_message(update: Update, context: CallbackContext) -> None:
    user, message = update.effective_user, update.message
    if not user or not message or is_user_banned(user.id): return

    # If user has selected a bank, guide them to send a photo
    if context.user_data.get('selected_bank'):
        await message.reply_text("⏳ في انتظار الصورة... الرجاء إرسال **صورة** السؤال الآن.", parse_mode=ParseMode.MARKDOWN)
    else: # If no bank selected, guide them to start
        await message.reply_text("لبدء إرسال استفسار، يرجى الضغط على /start واختيار البنك أولاً.")


# MODIFIED: forward_to_admin_topic now accepts a topic_id
async def forward_to_admin_topic(context: CallbackContext, q_data: Dict, topic_id: int or None):
    safe_fullname = escape_legacy_markdown(q_data['fullname'])
    safe_username = escape_legacy_markdown(q_data['username']) if q_data['username'] else "غير متوفر"
    
    caption = (f"**استفسار جديد - بنك رقم {q_data['bank_number']}** 📥\n"
               f"**من:** {safe_fullname}\n"
               f"**يوزر:** @{safe_username}\n"
               f"**ID:** `{q_data['user_id']}`\n\n"
               f"**نص الاستفسار:**\n{q_data.get('content') or ''}")

    replies_data[q_data['question_id']] = {'user_id': q_data['user_id'], 'user_message_id': q_data['message_id'], 'admin_message_id': None}
    
    try:
        sent_message = await context.bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=q_data['file_id'],
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            message_thread_id=topic_id  # This is the key for sending to a topic
        )

        if sent_message:
            replies_data[q_data['question_id']]['admin_message_id'] = sent_message.message_id
            save_data(replies_data, REPLIES_FILE)
    except Exception as e:
        logger.error(f"Error forwarding to admin group topic {topic_id}: {e}")
        # Fallback: try sending to the main group if topic fails
        try:
            await context.bot.send_message(ADMIN_GROUP_ID, text=f"⚠️ فشل الإرسال للتوبيك. رسالة للطوارئ:\n{caption}")
        except Exception as fallback_e:
            logger.error(f"Fallback sending also failed: {fallback_e}")

# --- ADMIN AND OTHER FUNCTIONS (Mostly Unchanged) ---
# The admin reply logic should work as is, as it replies based on message_id, which is unique across topics.
# Other admin commands like /stats, /ban, /export remain the same.

async def handle_admin_reply(update: Update, context: CallbackContext) -> None:
    if not update.message or not update.message.reply_to_message: return
    replied_msg_id = update.message.reply_to_message.message_id
    question_id = next((qid for qid, data in replies_data.items() if data.get('admin_message_id') == replied_msg_id or replied_msg_id in data.get('admin_thread_message_ids', [])), None)
    if not question_id: return
    
    reply_data = replies_data[question_id]
    user_id, user_msg_id = reply_data['user_id'], reply_data['user_message_id']
    
    try:
        # Replying to the user doesn't need special handling, it goes to the private chat
        await update.message.copy(chat_id=user_id, reply_to_message_id=user_msg_id)
        await update.message.reply_text("✅ تم إرسال ردك للطالب بنجاح.")
    except Exception as e:
        logger.error(f"Error sending reply to user: {e}")
        await update.message.reply_text(f"❌ فشل إرسال الرد. قد يكون المستخدم قد حظر البوت.\nالخطأ: {e}")

# All other functions like stats_command, export_command, broadcast_command, ban_command, etc. can remain here without changes.
async def stats_command(update: Update, context: CallbackContext) -> None:
    if update.effective_chat.id != ADMIN_GROUP_ID: return
    
    total_questions = len(questions_data)
    unique_users = len(get_all_user_ids())
    
    # NEW: Stats by bank
    bank_counts = {}
    for q in questions_data.values():
        bank_num = q.get('bank_number', 'غير محدد')
        bank_counts[bank_num] = bank_counts.get(bank_num, 0) + 1

    stats_text = f"📈 **نظرة على إحصائيات البوت:**\n\n"
    stats_text += f"📥 إجمالي الاستفسارات: {total_questions}\n"
    stats_text += f"👥 عدد المستخدمين الفريدين: {unique_users}\n\n"
    stats_text += f"🏦 **تصنيف الاستفسارات حسب البنك:**\n"
    stats_text += "\n".join([f"• البنك رقم {bank}: {count}" for bank, count in bank_counts.items()])
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

# --- Main application setup ---
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    # ... other admin commands are unchanged ...
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("banned", banned_list_command))
    application.add_handler(CommandHandler("import", import_command))
    
    # MODIFIED: New callback query handlers
    application.add_handler(CallbackQueryHandler(select_bank_handler, pattern="^select_bank:"))
    application.add_handler(CallbackQueryHandler(caption_help_handler, pattern="^caption_help$"))
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(instructions|main_menu)"))
    
    # MODIFIED: New specific message handlers for private chats
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO & ~filters.COMMAND, handle_photo_question))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Admin group handler (unchanged)
    application.add_handler(MessageHandler(filters.Chat(ADMIN_GROUP_ID) & filters.REPLY & ~filters.COMMAND, handle_admin_reply))

    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        exit(1)
    if not ADMIN_GROUP_ID or ADMIN_GROUP_ID == 0:
        logger.error("ADMIN_GROUP_ID environment variable is not set or invalid!")
        exit(1)
    
    # NEW: Check if Topic IDs are set
    for bank, topic_id in TOPIC_IDS.items():
        if topic_id == 0:
            logger.warning(f"TOPIC_ID_BANK_{bank} is not set in .env file. Submissions for this bank will go to the main group.")
            
    main()
