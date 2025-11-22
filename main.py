"""
M-Pesa Telegram Bot - Main Application Entry Point

This module orchestrates the entire application by:
- Loading configuration
- Initializing database and logger
- Setting up Telegram bot with handlers
- Running FastAPI callback server in background
- Managing graceful shutdown
"""

import asyncio
import logging
import signal
import sys
import threading
from typing import Optional
from datetime import datetime

# Third-party imports
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import uvicorn

# Local imports
try:
    from config import Config, load_config
    from database import Database, init_database
    from handlers import (
        start_handler,
        help_handler,
        pay_handler,
        confirm_handler,
        status_handler,
        cancel_handler,
        info_handler,
        service_handler,
        payment_details_handler,
        echo_handler,
    )
    from callback_server import app as fastapi_app, set_telegram_bot
    from utils import setup_logger, format_startup_banner
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    print("Please ensure all required modules are available.")
    sys.exit(1)


# Global variables
logger: Optional[logging.Logger] = None
bot_application: Optional[Application] = None
fastapi_thread: Optional[threading.Thread] = None
shutdown_event = threading.Event()


def setup_bot(config: Config, database: Database) -> Application:
    """
    Configure and set up the Telegram bot application with all handlers.

    Args:
        config: Application configuration object
        database: Database connection object

    Returns:
        Configured Application instance
    """
    logger.info("Setting up Telegram bot application...")

    try:
        # Create bot application
        application = Application.builder().token(config.telegram_bot_token).build()

        # Register command handlers
        logger.info("Registering command handlers...")
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("help", help_handler))
        application.add_handler(CommandHandler("pay", pay_handler))
        application.add_handler(CommandHandler("confirm", confirm_handler))
        application.add_handler(CommandHandler("status", status_handler))
        application.add_handler(CommandHandler("cancel", cancel_handler))
        application.add_handler(CommandHandler("info", info_handler))
        application.add_handler(CommandHandler("service", service_handler))

        # Register callback query handler for inline button presses
        logger.info("Registering callback query handler...")
        from handlers import button_callback_handler
        application.add_handler(CallbackQueryHandler(button_callback_handler))

        # Register message handlers (for payment details and general messages)
        logger.info("Registering message handlers...")
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                payment_details_handler
            )
        )
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                echo_handler
            )
        )

        # Store database reference in bot_data for access in handlers
        application.bot_data["database"] = database
        application.bot_data["config"] = config

        logger.info(f"✓ Telegram bot configured successfully with {len(application.handlers[0])} handlers")
        return application

    except Exception as e:
        logger.error(f"Failed to setup bot application: {e}", exc_info=True)
        raise


def start_callback_server(config: Config, bot: Application) -> None:
    """
    Start FastAPI callback server in a background thread.

    Args:
        config: Application configuration object
        bot: Telegram bot application instance
    """
    logger.info("Starting FastAPI callback server in background thread...")

    try:
        # Set the telegram bot reference in FastAPI app
        set_telegram_bot(bot.bot)

        # Configure uvicorn server
        uvicorn_config = uvicorn.Config(
            app=fastapi_app,
            host=config.callback_host,
            port=config.callback_port,
            log_level=config.log_level.lower(),
            access_log=True,
            use_colors=True,
        )

        server = uvicorn.Server(uvicorn_config)

        # Run server in the current thread (will be called from background thread)
        logger.info(f"✓ FastAPI server starting on {config.callback_host}:{config.callback_port}")
        server.run()

    except Exception as e:
        logger.error(f"Failed to start FastAPI server: {e}", exc_info=True)
        shutdown_event.set()


def signal_handler(signum: int, frame) -> None:
    """
    Handle shutdown signals (SIGINT, SIGTERM) for graceful shutdown.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    signal_name = signal.Signals(signum).name
    logger.info(f"\n{'='*60}")
    logger.info(f"Received {signal_name} signal. Initiating graceful shutdown...")
    logger.info(f"{'='*60}")

    shutdown_event.set()

    # Stop bot if running
    if bot_application and bot_application.running:
        logger.info("Stopping Telegram bot...")
        try:
            asyncio.create_task(bot_application.stop())
        except RuntimeError:
            # If no event loop is running, use run_until_complete
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(bot_application.stop())
            loop.close()

    logger.info("Shutdown complete. Goodbye!")
    sys.exit(0)


async def initialize_application() -> tuple[Config, Database]:
    """
    Initialize application configuration and database.

    Returns:
        Tuple of (Config, Database) instances
    """
    logger.info("Initializing application components...")

    # Load configuration
    logger.info("Loading configuration...")
    config = load_config()
    logger.info("✓ Configuration loaded successfully")

    # Initialize database
    logger.info("Initializing database connection...")
    database = await init_database(config)
    logger.info("✓ Database initialized successfully")

    return config, database


def display_startup_banner(config: Config) -> None:
    """
    Display startup banner with configuration information.

    Args:
        config: Application configuration object
    """
    banner = f"""
╔{'='*58}╗
║{' '*18}M-PESA TELEGRAM BOT{' '*19}║
╚{'='*58}╝

📅 Startup Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔧 Configuration:
   • Environment:        {config.environment}
   • M-Pesa Mode:        {config.mpesa_mode.upper()}
   • Bot Token:          {config.telegram_bot_token[:20]}...
   • Callback URL:       {config.callback_url}
   • Callback Server:    {config.callback_host}:{config.callback_port}
   • Database:           {config.db_host}:{config.db_port}/{config.db_name}
   • Log Level:          {config.log_level}

🚀 Starting services...
"""
    print(banner)
    logger.info("Application startup initiated")


async def run_bot(application: Application) -> None:
    """
    Run the Telegram bot in polling mode.

    Args:
        application: Configured bot application
    """
    logger.info("Starting Telegram bot in polling mode...")

    try:
        # Initialize the application
        await application.initialize()
        await application.start()

        logger.info("✓ Telegram bot is now running and polling for updates")
        logger.info(f"{'='*60}")
        logger.info("🤖 Bot is ready to accept commands!")
        logger.info(f"{'='*60}\n")

        # Start polling
        await application.updater.start_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )

        # Keep the bot running until shutdown
        while not shutdown_event.is_set():
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
        raise
    finally:
        logger.info("Stopping bot polling...")
        if application.updater.running:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("✓ Bot stopped successfully")


async def async_main() -> None:
    """
    Main asynchronous function that orchestrates the entire application.
    """
    global bot_application, fastapi_thread

    try:
        # Initialize configuration and database
        config, database = await initialize_application()

        # Display startup banner
        display_startup_banner(config)

        # Setup Telegram bot
        bot_application = setup_bot(config, database)

        # Start FastAPI callback server in background thread
        logger.info("Launching FastAPI callback server thread...")
        fastapi_thread = threading.Thread(
            target=start_callback_server,
            args=(config, bot_application),
            daemon=True,
            name="FastAPI-Server"
        )
        fastapi_thread.start()
        logger.info("✓ FastAPI thread started successfully")

        # Give FastAPI server time to start
        await asyncio.sleep(2)

        # Run Telegram bot (blocking)
        await run_bot(bot_application)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        logger.info("Performing cleanup...")

        if database:
            logger.info("Closing database connections...")
            await database.close()
            logger.info("✓ Database connections closed")

        if fastapi_thread and fastapi_thread.is_alive():
            logger.info("Waiting for FastAPI thread to terminate...")
            fastapi_thread.join(timeout=5)

        logger.info("✓ Cleanup complete")


def main() -> None:
    """
    Main entry point for the application.
    Sets up logging, signal handlers, and runs the async main function.
    """
    global logger

    try:
        # Setup logger first
        logger = setup_logger()
        logger.info("Logger initialized successfully")

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers registered (SIGINT, SIGTERM)")

        # Run the async main function
        asyncio.run(async_main())

    except Exception as e:
        if logger:
            logger.critical(f"Application failed to start: {e}", exc_info=True)
        else:
            print(f"CRITICAL ERROR: Application failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
