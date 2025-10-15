#!/usr/bin/env python3
"""
Telegram Question Collection Bot for Render Hosting
Optimized for Render deployment with UptimeRobot monitoring
"""

import os
import logging
import sys
import asyncio
import signal
from datetime import datetime
import time

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger("telegram_bot")

# Global status
app_status = {
    'start_time': time.time(),
    'bot_running': False,
    'last_error': None
}

def create_web_server():
    """Create Flask web server for health checks"""
    from flask import Flask, jsonify
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        uptime = time.time() - app_status['start_time']
        return jsonify({
            "status": "بوت التجميعات - Question Collection Bot",
            "uptime_seconds": uptime,
            "uptime_formatted": f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s",
            "bot_running": app_status['bot_running'],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "environment": "Render",
            "description": "Telegram bot for collecting Qiyas exam questions"
        })
    
    @app.route('/ping')
    def ping():
        """Health check for UptimeRobot"""
        logger.info("Health check ping received")
        return jsonify({
            "status": "ok",
            "message": "pong", 
            "bot_running": app_status['bot_running'],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    @app.route('/status')
    def status():
        """Detailed status"""
        uptime = time.time() - app_status['start_time']
        return jsonify({
            "status": "ok",
            "uptime": uptime,
            "bot_running": app_status['bot_running'],
            "last_error": app_status['last_error'],
            "render_url": os.environ.get('RENDER_EXTERNAL_URL', 'Not available'),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "python_version": sys.version,
            "environment": "Render"
        })
    
    return app

async def start_web_server():
    """Start web server in background"""
    import threading
    
    def run_server():
        app = create_web_server()
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"Starting web server on port {port}")
        
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_url:
            logger.info(f"Bot URL: {render_url}")
            logger.info(f"Health check: {render_url}/ping")
        
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    # Start server in daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info("Web server started in background")
    
    # Give server time to start
    await asyncio.sleep(2)

async def run_telegram_bot():
    """Run the Telegram bot"""
    try:
        logger.info("Importing bot module...")
        import bot
        from telegram import Update
        from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
        
        # Validate environment variables
        if not bot.BOT_TOKEN:
            raise ValueError("BOT_TOKEN not set in environment")
        if not bot.ADMIN_GROUP_ID:
            raise ValueError("ADMIN_GROUP_ID not set in environment")
        
        logger.info("Creating bot application...")
        
        # Create application
        application = Application.builder().token(bot.BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", bot.start_command))
        application.add_handler(CommandHandler("help", bot.help_command))
        application.add_handler(CommandHandler("stats", bot.stats_command))
        application.add_handler(CommandHandler("export", bot.export_command))
        application.add_handler(CommandHandler("broadcast", bot.broadcast_command))
        application.add_handler(CommandHandler("ban", bot.ban_command))
        application.add_handler(CommandHandler("unban", bot.unban_command))
        application.add_handler(CommandHandler("banned", bot.banned_list_command))
        
        # Callback query handler for inline buttons
        application.add_handler(CallbackQueryHandler(bot.button_handler))
        
        # Admin group message handlers
        async def admin_group_handler(update, context):
            if update.message and update.message.reply_to_message:
                # Check if this is a reply to a broadcast initiation message
                reply_text = update.message.reply_to_message.text or ""
                if "وضع البث الجماعي" in reply_text or "عدد المستقبلين:" in reply_text:
                    await bot.handle_broadcast_message(update, context)
                else:
                    await bot.handle_admin_reply(update, context)
            else:
                await bot.handle_broadcast_message(update, context)
        
        application.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.GROUPS,
            admin_group_handler
        ))
        
        application.add_handler(MessageHandler(
            (filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.VIDEO | filters.Sticker.ALL) & filters.ChatType.GROUPS,
            admin_group_handler
        ))
        
        # User message handlers (private chats)
        application.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE,
            bot.handle_user_message
        ))
        
        application.add_handler(MessageHandler(
            (filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.VIDEO | filters.Sticker.ALL) & filters.ChatType.PRIVATE,
            bot.handle_user_message
        ))
        
        # Setup commands
        application.post_init = bot.setup_commands
        
        # Update status
        app_status['bot_running'] = True
        app_status['last_error'] = None
        
        logger.info("Starting bot polling...")
        
        # Start polling
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        # Keep the bot running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            await application.stop()
            await application.shutdown()
        
    except Exception as e:
        error_msg = f"Bot error: {str(e)}"
        logger.error(error_msg)
        logger.exception("Full error traceback:")
        app_status['bot_running'] = False
        app_status['last_error'] = error_msg
        raise

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    app_status['bot_running'] = False
    sys.exit(0)

async def main():
    """Main application entry point"""
    logger.info("🚀 Starting بوت التجميعات - Question Collection Bot for Render")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Render URL: {os.environ.get('RENDER_EXTERNAL_URL', 'Not available')}")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start web server first
        await start_web_server()
        
        # Then start the bot
        await run_telegram_bot()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)

if __name__ == "__main__":
    # Run the main application
    asyncio.run(main())
