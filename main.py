"""
M-Pesa Telegram Bot - Main Application Entry Point

This module orchestrates the entire application by:
- Loading configuration
- Initializing database and logger
- Setting up Telegram bot with handlers
- Running FastAPI callback server in background
- Managing escrow system with background tasks
- Managing graceful shutdown
"""

import asyncio
import logging
import signal
import sys
import threading
from typing import Optional
from datetime import datetime, time

# Third-party imports
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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

# Escrow system imports
escrow_available = False
try:
    import escrow_database
    import escrow_service
    import escrow_handlers_buyer
    import escrow_handlers_seller
    import escrow_handlers_admin
    import escrow_automation
    escrow_available = True
    logger_import = logging.getLogger(__name__)
    logger_import.info("✓ Escrow modules imported successfully")
except ImportError as e:
    logger_import = logging.getLogger(__name__)
    logger_import.warning(f"Escrow modules not available: {e}")
    logger_import.warning("Bot will run without escrow functionality")


# Global variables
logger: Optional[logging.Logger] = None
bot_application: Optional[Application] = None
fastapi_thread: Optional[threading.Thread] = None
shutdown_event = threading.Event()
escrow_scheduler: Optional[AsyncIOScheduler] = None
escrow_db: Optional[any] = None


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

        # Register standard payment command handlers
        logger.info("Registering payment command handlers...")
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("help", help_handler))
        application.add_handler(CommandHandler("pay", pay_handler))
        application.add_handler(CommandHandler("confirm", confirm_handler))
        application.add_handler(CommandHandler("status", status_handler))
        application.add_handler(CommandHandler("cancel", cancel_handler))
        application.add_handler(CommandHandler("info", info_handler))
        application.add_handler(CommandHandler("service", service_handler))

        # Register escrow command handlers if available
        if escrow_available:
            logger.info("Registering escrow command handlers...")

            # Buyer commands
            logger.info("  - Registering buyer commands...")
            application.add_handler(CommandHandler("buy", escrow_handlers_buyer.buy_handler))
            application.add_handler(CommandHandler("my_purchases", escrow_handlers_buyer.my_purchases_handler))
            application.add_handler(CommandHandler("confirm_delivery", escrow_handlers_buyer.confirm_delivery_handler))
            application.add_handler(CommandHandler("dispute", escrow_handlers_buyer.dispute_handler))
            application.add_handler(CommandHandler("track", escrow_handlers_buyer.track_handler))
            application.add_handler(CommandHandler("cancel_order", escrow_handlers_buyer.cancel_order_handler))

            # Seller commands
            logger.info("  - Registering seller commands...")
            application.add_handler(CommandHandler("register_seller", escrow_handlers_seller.register_seller_handler))
            application.add_handler(CommandHandler("my_sales", escrow_handlers_seller.my_sales_handler))
            application.add_handler(CommandHandler("mark_shipped", escrow_handlers_seller.mark_shipped_handler))
            application.add_handler(CommandHandler("request_release", escrow_handlers_seller.request_release_handler))
            application.add_handler(CommandHandler("seller_stats", escrow_handlers_seller.seller_stats_handler))
            application.add_handler(CommandHandler("withdraw", escrow_handlers_seller.withdraw_handler))
            application.add_handler(CommandHandler("seller_help", escrow_handlers_seller.seller_help_handler))

            # Admin commands
            logger.info("  - Registering admin commands...")
            application.add_handler(CommandHandler("verify_seller", escrow_handlers_admin.verify_seller_handler))
            application.add_handler(CommandHandler("suspend_seller", escrow_handlers_admin.suspend_seller_handler))
            application.add_handler(CommandHandler("resolve_dispute", escrow_handlers_admin.resolve_dispute_handler))
            application.add_handler(CommandHandler("escrow_dashboard", escrow_handlers_admin.escrow_dashboard_handler))
            application.add_handler(CommandHandler("disputed_transactions", escrow_handlers_admin.disputed_transactions_handler))
            application.add_handler(CommandHandler("suspicious_users", escrow_handlers_admin.suspicious_users_handler))
            application.add_handler(CommandHandler("freeze_transaction", escrow_handlers_admin.freeze_transaction_handler))
            application.add_handler(CommandHandler("manual_refund", escrow_handlers_admin.manual_refund_handler))
            application.add_handler(CommandHandler("manual_release", escrow_handlers_admin.manual_release_handler))

            logger.info("✓ Escrow command handlers registered successfully")

        # Register callback query handlers for inline buttons
        logger.info("Registering callback query handlers...")
        from handlers import button_callback_handler

        if escrow_available:
            # Create combined callback handler that routes to appropriate handler
            async def combined_callback_handler(update, context):
                """Route callback queries to appropriate handler based on data prefix."""
                query = update.callback_query
                callback_data = query.data

                # Escrow callback handlers
                escrow_callbacks = {
                    "confirm_escrow_payment": escrow_handlers_buyer.confirm_escrow_payment_callback,
                    "cancel_escrow_payment": escrow_handlers_buyer.cancel_escrow_payment_callback,
                    "confirm_delivery_button": escrow_handlers_buyer.confirm_delivery_callback,
                    "dispute_transaction_button": escrow_handlers_buyer.dispute_transaction_callback,
                    "rate_seller_button": escrow_handlers_buyer.rate_seller_callback,
                }

                # Check if it's an escrow callback
                for prefix, handler in escrow_callbacks.items():
                    if callback_data.startswith(prefix):
                        return await handler(update, context)

                # Otherwise use standard button callback handler
                return await button_callback_handler(update, context)

            application.add_handler(CallbackQueryHandler(combined_callback_handler))
        else:
            # Use standard callback handler only
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

        # Store escrow database reference if available
        if escrow_available and escrow_db:
            application.bot_data["escrow_db"] = escrow_db

        total_handlers = sum(len(handlers) for handlers in application.handlers.values())
        logger.info(f"✓ Telegram bot configured successfully with {total_handlers} handlers")
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


async def setup_escrow_scheduler(application: Application) -> AsyncIOScheduler:
    """
    Setup and start background scheduler for escrow automation tasks.

    Args:
        application: Telegram bot application instance

    Returns:
        Configured AsyncIOScheduler instance
    """
    logger.info("Setting up escrow automation scheduler...")

    try:
        scheduler = AsyncIOScheduler()

        # Schedule auto-release task (every 1 hour)
        scheduler.add_job(
            escrow_automation.auto_release_task,
            trigger=IntervalTrigger(hours=1),
            args=[application.bot, escrow_db],
            id="auto_release",
            name="Auto-release completed deliveries",
            replace_existing=True,
        )
        logger.info("  ✓ Scheduled auto-release task (every 1 hour)")

        # Schedule auto-refund task (every 6 hours)
        scheduler.add_job(
            escrow_automation.auto_refund_task,
            trigger=IntervalTrigger(hours=6),
            args=[application.bot, escrow_db],
            id="auto_refund",
            name="Auto-refund expired/cancelled orders",
            replace_existing=True,
        )
        logger.info("  ✓ Scheduled auto-refund task (every 6 hours)")

        # Schedule reminder notifications (every 12 hours)
        scheduler.add_job(
            escrow_automation.send_reminder_notifications,
            trigger=IntervalTrigger(hours=12),
            args=[application.bot, escrow_db],
            id="reminders",
            name="Send reminder notifications",
            replace_existing=True,
        )
        logger.info("  ✓ Scheduled reminder notifications (every 12 hours)")

        # Schedule fraud detection (daily at midnight)
        scheduler.add_job(
            escrow_automation.fraud_detection_task,
            trigger=CronTrigger(hour=0, minute=0),
            args=[application.bot, escrow_db],
            id="fraud_detection",
            name="Fraud detection scan",
            replace_existing=True,
        )
        logger.info("  ✓ Scheduled fraud detection (daily at midnight)")

        # Schedule seller rating updates (daily at 1 AM)
        scheduler.add_job(
            escrow_automation.update_seller_ratings,
            trigger=CronTrigger(hour=1, minute=0),
            args=[escrow_db],
            id="seller_ratings",
            name="Update seller ratings",
            replace_existing=True,
        )
        logger.info("  ✓ Scheduled seller rating updates (daily at 1 AM)")

        # Start the scheduler
        scheduler.start()
        logger.info("✓ Escrow automation scheduler started successfully")

        return scheduler

    except Exception as e:
        logger.error(f"Failed to setup escrow scheduler: {e}", exc_info=True)
        raise


async def initialize_escrow_database(config: Config, database: Database):
    """
    Initialize escrow database and return connection.

    Args:
        config: Application configuration object
        database: Main database instance

    Returns:
        Escrow database connection
    """
    logger.info("Initializing escrow database...")

    try:
        escrow_db_instance = await escrow_database.init_escrow_database(config, database)
        logger.info("✓ Escrow database initialized successfully")
        return escrow_db_instance
    except Exception as e:
        logger.error(f"Failed to initialize escrow database: {e}", exc_info=True)
        raise


async def get_escrow_stats():
    """
    Get current escrow system statistics.

    Returns:
        Dictionary with escrow stats
    """
    if not escrow_available or not escrow_db:
        return {
            "active_transactions": 0,
            "total_held": 0.0,
            "pending_disputes": 0,
        }

    try:
        stats = await escrow_service.get_escrow_statistics(escrow_db)
        return stats
    except Exception as e:
        logger.error(f"Failed to get escrow stats: {e}")
        return {
            "active_transactions": 0,
            "total_held": 0.0,
            "pending_disputes": 0,
        }


async def perform_health_checks():
    """
    Perform health checks on escrow system.
    Alerts if there are issues that need attention.
    """
    if not escrow_available or not escrow_db:
        return

    try:
        # Check for excessive disputes
        stats = await get_escrow_stats()

        if stats.get("pending_disputes", 0) > 10:
            logger.warning(f"⚠️  HIGH DISPUTE COUNT: {stats['pending_disputes']} pending disputes!")

        # Check auto-release failures
        failed_releases = await escrow_automation.get_failed_auto_releases(escrow_db)
        if failed_releases > 5:
            logger.warning(f"⚠️  AUTO-RELEASE FAILURES: {failed_releases} failed attempts")

        # Check for frozen transactions older than 7 days
        old_frozen = await escrow_service.get_old_frozen_transactions(escrow_db, days=7)
        if old_frozen > 0:
            logger.warning(f"⚠️  OLD FROZEN TRANSACTIONS: {old_frozen} transactions frozen >7 days")

        logger.info("✓ Health checks completed")

    except Exception as e:
        logger.error(f"Failed to perform health checks: {e}", exc_info=True)


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

    # Stop scheduler if running
    if escrow_scheduler and escrow_scheduler.running:
        logger.info("Stopping escrow scheduler...")
        escrow_scheduler.shutdown(wait=False)

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


async def display_startup_banner(config: Config) -> None:
    """
    Display startup banner with configuration information.

    Args:
        config: Application configuration object
    """
    # Get escrow stats if available
    escrow_status = "DISABLED"
    escrow_info = ""

    if escrow_available:
        try:
            stats = await get_escrow_stats()
            escrow_status = "ENABLED"
            escrow_info = f"""
💰 Escrow System Status:
   • Status:             {escrow_status}
   • Active Transactions: {stats.get('active_transactions', 0)}
   • Total Held (KES):   {stats.get('total_held', 0):,.2f}
   • Pending Disputes:   {stats.get('pending_disputes', 0)}
   • Background Tasks:   RUNNING"""
        except Exception as e:
            logger.warning(f"Could not fetch escrow stats: {e}")
            escrow_status = "ERROR"
            escrow_info = f"""
💰 Escrow System Status:
   • Status:             {escrow_status} (Stats unavailable)"""
    else:
        escrow_info = f"""
💰 Escrow System Status:
   • Status:             {escrow_status}"""

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
{escrow_info}

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
        # Perform health checks every 30 minutes
        health_check_interval = 1800  # 30 minutes in seconds
        last_health_check = 0

        while not shutdown_event.is_set():
            await asyncio.sleep(1)

            # Perform periodic health checks
            if escrow_available and escrow_db:
                current_time = asyncio.get_event_loop().time()
                if current_time - last_health_check >= health_check_interval:
                    try:
                        await perform_health_checks()
                        last_health_check = current_time
                    except Exception as e:
                        logger.error(f"Health check failed: {e}")

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
    global bot_application, fastapi_thread, escrow_scheduler, escrow_db

    try:
        # Initialize configuration and database
        config, database = await initialize_application()

        # Initialize escrow database if available
        if escrow_available:
            try:
                escrow_db = await initialize_escrow_database(config, database)
            except Exception as e:
                logger.error(f"Escrow database initialization failed: {e}")
                logger.warning("Continuing without escrow functionality...")

        # Display startup banner (now async to fetch escrow stats)
        await display_startup_banner(config)

        # Setup Telegram bot
        bot_application = setup_bot(config, database)

        # Setup escrow scheduler if available
        if escrow_available and escrow_db:
            try:
                escrow_scheduler = await setup_escrow_scheduler(bot_application)
            except Exception as e:
                logger.error(f"Escrow scheduler setup failed: {e}")
                logger.warning("Continuing without escrow automation...")

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

        # Perform initial health checks
        if escrow_available and escrow_db:
            await perform_health_checks()

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

        # Stop escrow scheduler gracefully
        if escrow_scheduler and escrow_scheduler.running:
            logger.info("Stopping escrow scheduler...")
            try:
                # Complete pending auto-releases before shutdown
                if escrow_available and escrow_db:
                    logger.info("Completing pending auto-releases...")
                    await escrow_automation.complete_pending_releases(escrow_db)
                    logger.info("✓ Pending auto-releases completed")

                escrow_scheduler.shutdown(wait=True)
                logger.info("✓ Escrow scheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping escrow scheduler: {e}")

        # Close escrow database connection
        if escrow_db and escrow_available:
            try:
                logger.info("Closing escrow database connections...")
                await escrow_database.close_escrow_database(escrow_db)
                logger.info("✓ Escrow database connections closed")
            except Exception as e:
                logger.error(f"Error closing escrow database: {e}")

        # Close main database
        if database:
            logger.info("Closing database connections...")
            await database.close()
            logger.info("✓ Database connections closed")

        # Wait for FastAPI thread
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
