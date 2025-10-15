#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import uuid
import asyncio
from typing import Dict, List, Union, Tuple, Set
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

# Initialize data
questions_data = load_data(DATA_FILE)
replies_data = load_data(REPLIES_FILE)
banned_users = load_data(BANS_FILE)
active_users = load_users_data()

# Helper functions for question management
def get_user_questions(user_id: int) -> List[Dict]:
    """Get all questions from a specific user"""
    return [q for q in questions_data.values() if q['user_id'] == user_id]

def get_all_user_ids() -> List[int]:
    """Get all unique user IDs who have sent questions"""
    return list(set(q['user_id'] for q in questions_data.values()))

def is_user_banned(user_id: int) -> bool:
    """Check if a user is banned"""
    return str(user_id) in banned_users

def ban_user(user_id: int, admin_id: int, reason: str = "No reason provided") -> bool:
    """Ban a user"""
    try:
        banned_users[str(user_id)] = {
            'banned_at': datetime.now().isoformat(),
            'banned_by': admin_id,
            'reason': reason
        }
        save_data(banned_users, BANS_FILE)
        return True
    except Exception as e:
        logger.error(f"Failed to ban user {user_id}: {e}")
        return False

def unban_user(user_id: int) -> bool:
    """Unban a user"""
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
    """Get list of all banned users with details"""
    banned_list = []
    for user_id, ban_data in banned_users.items():
        banned_list.append({
            'user_id': int(user_id),
            'banned_at': ban_data.get('banned_at', 'Unknown'),
            'banned_by': ban_data.get('banned_by', 'Unknown'),
            'reason': ban_data.get('reason', 'No reason provided')
        })
    return banned_list

async def set_menu_button(application: Application) -> None:
    """Set the menu button to show commands."""
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonCommands(type="commands")
        )
        logger.info("Menu button set to commands")
    except Exception as e:
        logger.error(f"Failed to set menu button: {e}")

async def start_command(update: Update, context: CallbackContext) -> None:
    """Send welcome message when the command /start is issued."""
    user = update.effective_user
    if not user or not update.message:
        return
    
    keyboard = [
        [InlineKeyboardButton("📬 أسئلتي المرسلة", callback_data="orders_list")],
        [InlineKeyboardButton("💡 كيف أستخدم البوت؟", callback_data="instructions")]
    ]
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
        active_users[str(user_id)] = {
            "first_name": user.first_name,
            "last_name": user.last_name or "",
            "username": user.username or "",
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": 0
        }
    else:
        active_users[str(user_id)]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_users_data()
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def button_handler(update: Update, context: CallbackContext) -> None:
    """Handle inline keyboard button presses"""
    query = update.callback_query
    if not query or not query.from_user:
        return
    await query.answer()
    
    if query.data == "orders_list":
        user_id = query.from_user.id
        user_questions = get_user_questions(user_id)
        
        if not user_questions:
            await query.edit_message_text("📪 ليس لديك أي أسئلة مرسلة بعد.")
            return
        
        orders_text = f"📬 **قائمة أسئلتك التي أرسلتها:** (العدد: {len(user_questions)})\n\n"
        
        for i, question in enumerate(user_questions, 1):
            timestamp = datetime.fromisoformat(question['timestamp']).strftime('%Y-%m-%d %H:%M')
            content_preview = question['content'][:50] + "..." if len(question['content']) > 50 else question['content']
            orders_text += f"{i}. **نوع:** {question['message_type']} - **تاريخ:** {timestamp}\n   `{content_preview}`\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            orders_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
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
        
        keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            instructions_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "main_menu":
        user = query.from_user
        if not user:
            return
        
        keyboard = [
            [InlineKeyboardButton("📬 أسئلتي المرسلة", callback_data="orders_list")],
            [InlineKeyboardButton("💡 كيف أستخدم البوت؟", callback_data="instructions")]
        ]
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
        
        await query.edit_message_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def how_to_reply_callback(update: Update, context: CallbackContext) -> None:
    """Handles the 'how_to_reply' button click and shows an alert."""
    query = update.callback_query
    if not query:
        return

    alert_text = "💡 يمكنك الرد بعمل رد (Reply) على هذه الرسالة لإيصالها للمشرف."
    await query.answer(text=alert_text, show_alert=True)


async def stats_command(update: Update, context: CallbackContext) -> None:
    """Show bot statistics."""
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if not update.message:
        return
    
    total_questions = len(questions_data)
    unique_users = len(get_all_user_ids())
    
    type_counts = {}
    for question in questions_data.values():
        msg_type = question['message_type']
        type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
    
    stats_text = f"""📈 **نظرة على إحصائيات البوت:**

📥 إجمالي المشاركات: {total_questions}
👥 عدد المستخدمين الفريدين: {unique_users}

📂 **تصنيف المشاركات حسب النوع:**
"""
    
    for msg_type, count in type_counts.items():
        stats_text += f"• {msg_type}: {count}\n"
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def export_command(update: Update, context: CallbackContext) -> None:
    """Export all data as JSON files (admin only)"""
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if not update.message:
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # Export files...
        files_to_export = {
            DATA_FILE: "questions_data",
            REPLIES_FILE: "replies_data",
            USERS_FILE: "users_data",
            BANS_FILE: "banned_users"
        }
        
        for file_path, name in files_to_export.items():
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=f"{name}_{timestamp}.json"
                    )
        
        await update.message.reply_text(
            f"✅ **اكتمل تصدير البيانات بنجاح**\n\n"
            f"📦 **المحتويات:**\n"
            f"• المشاركات: {len(questions_data)}\n"
            f"• المحادثات: {len(replies_data)}\n"
            f"• المستخدمون: {len(active_users)}\n"
            f"• المحظورون: {len(banned_users)}\n\n"
            f"🕰️ **توقيت التصدير:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء التصدير: {e}")

async def broadcast_command(update: Update, context: CallbackContext) -> None:
    """Start broadcast mode (admin only)"""
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID:
        return
    
    if not update.effective_user or not update.message:
        return
    
    user_count = len(get_all_user_ids())
    
    waiting_for_broadcast[update.effective_user.id] = True
    await update.message.reply_text(
        f"📡 **وضع الإرسال الجماعي**\n\n"
        f"👥 سيتم الإرسال إلى: {user_count} مستخدم\n\n"
        f"الآن، أرسل الرسالة التي تود بثها (نص، صورة، ملف، الخ...)"
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    """Help command handler"""
    if not update.message:
        return
    
    chat = update.effective_chat
    if chat and chat.id == ADMIN_GROUP_ID:
        help_text = (
            "**🛠️ قائمة أوامر المشرفين:**\n\n"
            "/stats - عرض إحصائيات البوت.\n"
            "/export - استخراج جميع البيانات كملفات JSON.\n"
            "/broadcast - إرسال رسالة جماعية لجميع المستخدمين.\n"
            "/ban `user_id` `[reason]` - حظر مستخدم.\n"
            "/unban `user_id` - رفع الحظر عن مستخدم.\n"
            "/banned - عرض قائمة المستخدمين المحظورين.\n\n"
            "**للتواصل مع الطلاب:** قم بالرد (Reply) على رسائلهم في هذه المجموعة، وسيتم توجيه ردك إليهم مباشرة."
        )
    else:
        help_text = (
            "**👋 مرحباً بك في قسم المساعدة!**\n\n"
            "/start - لإعادة تشغيل البوت وعرض القائمة الرئيسية.\n"
            "/help - لعرض هذه الرسالة.\n\n"
            "لإرسال سؤال أو مساهمة، فقط أرسلها مباشرة هنا. يمكنك إرسال نصوص، صور، ملفات، أو رسائل صوتية."
        )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Ban/Unban/Banned list commands (no text changes needed, functionality is internal)
async def ban_command(update: Update, context: CallbackContext) -> None:
    """Ban a user (admin only)"""
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if not update.message or not context.args:
        await update.message.reply_text("استخدام خاطئ. الصيغة: /ban <user_id> [السبب]")
        return
    try:
        user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "بدون سبب"
        if is_user_banned(user_id):
            await update.message.reply_text(f"المستخدم {user_id} محظور بالفعل.")
            return
        if ban_user(user_id, update.effective_user.id, reason):
            await update.message.reply_text(f"🚫 تم حظر المستخدم {user_id} بنجاح.\nالسبب: {reason}")
    except ValueError:
        await update.message.reply_text("معرف المستخدم يجب أن يكون رقماً.")

async def unban_command(update: Update, context: CallbackContext) -> None:
    """Unban a user (admin only)"""
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if not update.message or not context.args:
        await update.message.reply_text("استخدام خاطئ. الصيغة: /unban <user_id>")
        return
    try:
        user_id = int(context.args[0])
        if not is_user_banned(user_id):
            await update.message.reply_text(f"المستخدم {user_id} ليس محظوراً.")
            return
        if unban_user(user_id):
            await update.message.reply_text(f"✅ تم رفع الحظر عن المستخدم {user_id}.")
    except ValueError:
        await update.message.reply_text("معرف المستخدم يجب أن يكون رقماً.")

async def banned_list_command(update: Update, context: CallbackContext) -> None:
    """Show list of banned users (admin only)"""
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if not update.message:
        return
    banned_list = get_banned_users()
    if not banned_list:
        await update.message.reply_text("لا يوجد مستخدمون محظورون حالياً.")
        return
    message = f"**🚫 قائمة المحظورين ({len(banned_list)}):**\n\n"
    for item in banned_list:
        banned_at = datetime.fromisoformat(item['banned_at']).strftime('%Y-%m-%d')
        message += f"- ID: `{item['user_id']}`\n  - السبب: {item['reason']}\n  - تاريخ الحظر: {banned_at}\n"
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def handle_user_message(update: Update, context: CallbackContext) -> None:
    """Handle messages from users"""
    user = update.effective_user
    message = update.message
    
    if not user or not message or update.effective_chat.id == ADMIN_GROUP_ID:
        return
    
    if is_user_banned(user.id):
        await message.reply_text("🚫 عذراً، لقد تم حظرك من استخدام هذا البوت.")
        return
    
    if (message.reply_to_message and 
        message.reply_to_message.from_user and 
        message.reply_to_message.from_user.is_bot):
        await handle_user_reply(update, context)
        return
    
    question_id = str(uuid.uuid4())
    
    message_type = "نص"
    content = ""
    file_info = None
    
    if message.text:
        message_type = "نص"
        content = message.text
    elif message.photo:
        message_type = "صورة"
        content = message.caption or ""
        file_info = message.photo[-1].file_id
    elif message.document:
        message_type = "ملف"
        content = message.caption or f"{message.document.file_name}"
        file_info = message.document.file_id
    elif message.voice:
        message_type = "رسالة صوتية"
        content = ""
        file_info = message.voice.file_id
    elif message.audio:
        message_type = "ملف صوتي"
        content = message.caption or ""
        file_info = message.audio.file_id
    
    question_data = {
        'question_id': question_id, 'user_id': user.id,
        'username': user.username or "", 'fullname': user.full_name,
        'message_type': message_type, 'content': content,
        'file_id': file_info, 'timestamp': datetime.now().isoformat(),
        'message_id': message.message_id
    }
    
    questions_data[question_id] = question_data
    save_data(questions_data, DATA_FILE)
    
    str_user_id = str(user.id)
    if str_user_id not in active_users:
        active_users[str_user_id] = {
            "first_name": user.first_name, "last_name": user.last_name or "",
            "username": user.username or "", "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "message_count": 1
        }
    else:
        active_users[str_user_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        active_users[str_user_id]["message_count"] = active_users[str_user_id].get("message_count", 0) + 1
    
    save_users_data()
    
    await message.reply_text("👍 رسالتك وصلت بنجاح، شكراً لمساهمتك!")
    
    await forward_to_admin_group_new(context, question_data)
    
    total_questions = len(questions_data)
    if total_questions > 0 and total_questions % 50 == 0:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"🎉 تهانينا! وصلنا إلى المشاركة رقم {total_questions}."
        )

async def forward_to_admin_group_new(context: CallbackContext, question_data: Dict):
    """Forward question to admin group"""
    user_info = (f"**مشاركة جديدة** 📥\n"
                 f"**من:** {question_data['fullname']}\n"
                 f"**يوزر:** @{question_data['username']}\n"
                 f"**ID:** `{question_data['user_id']}`\n"
                 f"**الوقت:** {datetime.fromisoformat(question_data['timestamp']).strftime('%Y-%m-%d %H:%M')}\n\n")

    replies_data[question_data['question_id']] = {
        'user_id': question_data['user_id'],
        'user_message_id': question_data['message_id'],
        'admin_message_id': None
    }
    
    try:
        sent_message = None
        caption = user_info + question_data['content']
        
        if question_data['message_type'] == "نص":
            sent_message = await context.bot.send_message(ADMIN_GROUP_ID, text=caption, parse_mode=ParseMode.MARKDOWN)
        elif question_data['message_type'] == "صورة":
            sent_message = await context.bot.send_photo(ADMIN_GROUP_ID, photo=question_data['file_id'], caption=caption, parse_mode=ParseMode.MARKDOWN)
        elif question_data['message_type'] == "ملف":
            sent_message = await context.bot.send_document(ADMIN_GROUP_ID, document=question_data['file_id'], caption=caption, parse_mode=ParseMode.MARKDOWN)
        elif question_data['message_type'] == "رسالة صوتية":
            await context.bot.send_message(ADMIN_GROUP_ID, text=user_info, parse_mode=ParseMode.MARKDOWN)
            sent_message = await context.bot.send_voice(ADMIN_GROUP_ID, voice=question_data['file_id'])
        elif question_data['message_type'] == "ملف صوتي":
            sent_message = await context.bot.send_audio(ADMIN_GROUP_ID, audio=question_data['file_id'], caption=caption, parse_mode=ParseMode.MARKDOWN)

        if sent_message:
            replies_data[question_data['question_id']]['admin_message_id'] = sent_message.message_id
            save_data(replies_data, REPLIES_FILE)
            
    except Exception as e:
        logger.error(f"Error forwarding to admin group: {e}")

async def handle_user_reply(update: Update, context: CallbackContext) -> None:
    """Handle user replies to admin messages"""
    if not update.message or not update.message.reply_to_message:
        return
    
    user_reply_message_id = update.message.reply_to_message.message_id
    
    question_id, admin_message_id = None, None
    for qid, data in replies_data.items():
        if 'admin_replies' in data:
            for reply in data['admin_replies']:
                if reply.get('user_reply_message_id') == user_reply_message_id:
                    question_id = qid
                    admin_message_id = reply['admin_message_id']
                    break
        if question_id: break
    
    if not question_id or not admin_message_id:
        return
    
    try:
        reply_caption = f"رد من الطالب (ID: `{replies_data[question_id]['user_id']}`)"
        
        if update.message.text:
            sent_to_admin = await context.bot.send_message(ADMIN_GROUP_ID, text=f"{reply_caption}\n\n{update.message.text}", reply_to_message_id=admin_message_id, parse_mode=ParseMode.MARKDOWN)
        elif update.message.photo:
            sent_to_admin = await context.bot.send_photo(ADMIN_GROUP_ID, photo=update.message.photo[-1].file_id, caption=f"{reply_caption}\n\n{update.message.caption or ''}", reply_to_message_id=admin_message_id, parse_mode=ParseMode.MARKDOWN)
        # Add other message types if needed
        else:
            sent_to_admin = await context.bot.forward_message(ADMIN_GROUP_ID, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            await context.bot.send_message(ADMIN_GROUP_ID, text=reply_caption, reply_to_message_id=sent_to_admin.message_id, parse_mode=ParseMode.MARKDOWN)

        if 'admin_thread_message_ids' not in replies_data[question_id]:
            replies_data[question_id]['admin_thread_message_ids'] = []
        replies_data[question_id]['admin_thread_message_ids'].append(sent_to_admin.message_id)
        save_data(replies_data, REPLIES_FILE)

        await update.message.reply_text("✅ تم إرسال ردك.")
            
    except Exception as e:
        logger.error(f"Error forwarding user reply to admin: {e}")

async def handle_admin_reply(update: Update, context: CallbackContext) -> None:
    """Handle replies from admin group"""
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID or not update.message or not update.message.reply_to_message:
        return
    
    replied_message_id = update.message.reply_to_message.message_id
    question_id = None
    
    for qid, data in replies_data.items():
        if data.get('admin_message_id') == replied_message_id or replied_message_id in data.get('admin_thread_message_ids', []):
            question_id = qid
            break
    
    if not question_id: return
    
    reply_data = replies_data[question_id]
    user_id = reply_data['user_id']
    user_message_id = reply_data['user_message_id']
    
    # Create the inline keyboard for the reply
    keyboard = [[InlineKeyboardButton("💡 كيفية الرد", callback_data="how_to_reply")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        sent_message = None
        if update.message.text:
            sent_message = await context.bot.send_message(user_id, text=update.message.text, reply_to_message_id=user_message_id, reply_markup=reply_markup)
        elif update.message.photo:
            sent_message = await context.bot.send_photo(user_id, photo=update.message.photo[-1].file_id, caption=update.message.caption, reply_to_message_id=user_message_id, reply_markup=reply_markup)
        elif update.message.document:
            sent_message = await context.bot.send_document(user_id, document=update.message.document.file_id, caption=update.message.caption, reply_to_message_id=user_message_id, reply_markup=reply_markup)
        elif update.message.voice:
            sent_message = await context.bot.send_voice(user_id, voice=update.message.voice.file_id, reply_to_message_id=user_message_id, reply_markup=reply_markup)
        elif update.message.audio:
            sent_message = await context.bot.send_audio(user_id, audio=update.message.audio.file_id, caption=update.message.caption, reply_to_message_id=user_message_id, reply_markup=reply_markup)

        if sent_message:
            if 'admin_replies' not in reply_data:
                reply_data['admin_replies'] = []
            
            reply_data['admin_replies'].append({
                'admin_message_id': update.message.message_id,
                'user_reply_message_id': sent_message.message_id
            })
            save_data(replies_data, REPLIES_FILE)
            await update.message.reply_text("✅ تم إرسال ردك للطالب بنجاح.")
        
    except Exception as e:
        logger.error(f"Error sending reply to user: {e}")
        await update.message.reply_text(f"❌ فشل إرسال الرد. قد يكون المستخدم قد حظر البوت.\nالخطأ: {e}")

async def handle_broadcast_message(update: Update, context: CallbackContext) -> None:
    """Handle broadcast message from admin"""
    if not update.effective_chat or update.effective_chat.id != ADMIN_GROUP_ID or not update.effective_user or not update.message:
        return
    
    is_initiating_user = waiting_for_broadcast.get(update.effective_user.id, False)
    is_reply_to_prompt = False
    if update.message.reply_to_message:
        if "وضع الإرسال الجماعي" in (update.message.reply_to_message.text or ""):
            is_reply_to_prompt = True
            waiting_for_broadcast[update.effective_user.id] = True
            is_initiating_user = True

    if not is_initiating_user and not is_reply_to_prompt:
        return
    
    waiting_for_broadcast[update.effective_user.id] = False
    
    user_ids = get_all_user_ids()
    if not user_ids:
        await update.message.reply_text("لا يوجد مستخدمون لإرسال الرسالة إليهم.")
        return
    
    await update.message.reply_text(f"⏳ جارٍ بدء الإرسال إلى {len(user_ids)} مستخدم...")
    
    successful_sends, failed_sends = 0, 0
    
    for user_id in user_ids:
        try:
            await context.bot.copy_message(chat_id=user_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            successful_sends += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user_id}: {e}")
            failed_sends += 1
    
    await update.message.reply_text(
        f"**📣 اكتمل الإرسال الجماعي:**\n"
        f"👍 نجح: {successful_sends}\n"
        f"👎 فشل: {failed_sends}\n"
        f"👥 الإجمالي: {len(user_ids)}",
        parse_mode=ParseMode.MARKDOWN
    )

async def setup_commands(application: Application) -> None:
    """Set bot commands that will appear in the menu."""
    user_commands = [
        BotCommand("start", "🚀 بدء/عودة للقائمة"),
        BotCommand("help", "❓ مساعدة")
    ]
    await application.bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())

    admin_commands = [
        BotCommand("stats", "📊 الإحصائيات"),
        BotCommand("export", "📁 تصدير البيانات"),
        BotCommand("broadcast", "📡 رسالة جماعية"),
        BotCommand("ban", "🚫 حظر مستخدم"),
        BotCommand("unban", "✅ رفع الحظر"),
        BotCommand("banned", "📋 قائمة المحظورين")
    ]
    await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_GROUP_ID))

    await application.bot.set_my_commands([])
    logger.info("Bot commands have been set successfully.")

def main():
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("banned", banned_list_command))
    
    # Callback query handlers for inline buttons
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(orders_list|instructions|main_menu)$"))
    application.add_handler(CallbackQueryHandler(how_to_reply_callback, pattern="^how_to_reply$"))
    
    # Message handlers
    # Admin group messages (replies or broadcast messages)
    application.add_handler(MessageHandler(filters.Chat(ADMIN_GROUP_ID) & (filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO | filters.DOCUMENT.ALL ), handle_admin_reply_or_broadcast))

    # User messages (private chats)
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_user_message))

    # Setup bot on startup
    application.post_init = setup_commands
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

async def handle_admin_reply_or_broadcast(update: Update, context: CallbackContext) -> None:
    """A helper function to decide if an admin message is a reply or part of a broadcast."""
    if update.message and update.message.reply_to_message:
        reply_text = update.message.reply_to_message.text or ""
        if "وضع الإرسال الجماعي" in reply_text:
            await handle_broadcast_message(update, context)
        else:
            await handle_admin_reply(update, context)
    else:
        # If it's not a reply, it might be a message intended for broadcast
        if waiting_for_broadcast.get(update.effective_user.id, False):
            await handle_broadcast_message(update, context)


if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        exit(1)
    if not ADMIN_GROUP_ID or ADMIN_GROUP_ID == 0:
        logger.error("ADMIN_GROUP_ID environment variable is not set or invalid!")
        exit(1)
    main()
