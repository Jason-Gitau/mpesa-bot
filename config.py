"""
Configuration management module for M-Pesa Bot.

This module handles loading and validating environment variables,
providing a centralized Config class for all application settings.
Supports both sandbox and production M-Pesa environments.
"""

import os
from typing import Optional, Literal
from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class Config:
    """
    Configuration class that loads and validates all application settings.

    Supports both sandbox and production M-Pesa environments.
    All required configuration values are validated on initialization.

    Attributes:
        telegram_bot_token: Telegram bot API token
        seller_chat_id: Chat ID for seller notifications
        mpesa_environment: Either 'sandbox' or 'production'
        mpesa_consumer_key: M-Pesa API consumer key
        mpesa_consumer_secret: M-Pesa API consumer secret
        mpesa_shortcode: M-Pesa business shortcode
        mpesa_passkey: M-Pesa passkey for password generation
        mpesa_callback_url: URL for M-Pesa payment callbacks
        min_amount: Minimum payment amount allowed
        max_amount: Maximum payment amount allowed
    """

    # M-Pesa API endpoints
    MPESA_ENDPOINTS = {
        'sandbox': {
            'auth': 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            'stk_push': 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
            'query': 'https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query',
            'b2c': 'https://sandbox.safaricom.co.ke/mpesa/b2c/v1/paymentrequest',
            'c2b_register': 'https://sandbox.safaricom.co.ke/mpesa/c2b/v1/registerurl',
            'transaction_status': 'https://sandbox.safaricom.co.ke/mpesa/transactionstatus/v1/query',
            'account_balance': 'https://sandbox.safaricom.co.ke/mpesa/accountbalance/v1/query',
        },
        'production': {
            'auth': 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
            'stk_push': 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
            'query': 'https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query',
            'b2c': 'https://api.safaricom.co.ke/mpesa/b2c/v1/paymentrequest',
            'c2b_register': 'https://api.safaricom.co.ke/mpesa/c2b/v1/registerurl',
            'transaction_status': 'https://api.safaricom.co.ke/mpesa/transactionstatus/v1/query',
            'account_balance': 'https://api.safaricom.co.ke/mpesa/accountbalance/v1/query',
        }
    }

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration by loading environment variables.

        Args:
            env_file: Optional path to .env file. If not provided, uses default .env

        Raises:
            ConfigError: If required configuration is missing or invalid
        """
        # Load environment variables
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        # Telegram Configuration
        self.telegram_bot_token: str = self._get_required_env('TELEGRAM_BOT_TOKEN')
        self.seller_chat_id: str = self._get_required_env('SELLER_CHAT_ID')
        self.admin_chat_id: Optional[str] = os.getenv('ADMIN_CHAT_ID')

        # M-Pesa Configuration
        self.mpesa_environment: Literal['sandbox', 'production'] = self._get_mpesa_environment()
        self.mpesa_consumer_key: str = self._get_required_env('MPESA_CONSUMER_KEY')
        self.mpesa_consumer_secret: str = self._get_required_env('MPESA_CONSUMER_SECRET')
        self.mpesa_shortcode: str = self._get_required_env('MPESA_SHORTCODE')
        self.mpesa_passkey: str = self._get_required_env('MPESA_PASSKEY')
        self.mpesa_callback_url: str = os.getenv('CALLBACK_URL', 'https://your-domain.com/mpesa-callback')

        # M-Pesa Transaction Settings
        self.mpesa_transaction_type: str = os.getenv('MPESA_TRANSACTION_TYPE', 'CustomerPayBillOnline')
        self.mpesa_account_reference: str = os.getenv('MPESA_ACCOUNT_REFERENCE', 'Payment')
        self.mpesa_transaction_desc: str = os.getenv('MPESA_TRANSACTION_DESC', 'Payment for services')

        # Amount Limits
        self.min_amount: int = int(os.getenv('MIN_PAYMENT_AMOUNT', '1'))
        self.max_amount: int = int(os.getenv('MAX_PAYMENT_AMOUNT', '500000'))

        # Database Configuration (Optional)
        self.db_host: Optional[str] = os.getenv('DB_HOST')
        self.db_port: int = int(os.getenv('DB_PORT', '3306'))
        self.db_user: Optional[str] = os.getenv('DB_USER')
        self.db_password: Optional[str] = os.getenv('DB_PASSWORD')
        self.db_name: Optional[str] = os.getenv('DB_NAME')
        self.db_charset: str = os.getenv('DB_CHARSET', 'utf8mb4')

        # Supabase Configuration (Optional)
        self.supabase_url: Optional[str] = os.getenv('SUPABASE_URL')
        self.supabase_key: Optional[str] = os.getenv('SUPABASE_KEY')

        # Application Settings
        self.app_env: str = os.getenv('APP_ENV', 'development')
        self.app_debug: bool = os.getenv('APP_DEBUG', 'True').lower() in ('true', '1', 'yes')
        self.app_name: str = os.getenv('APP_NAME', 'MPESA_BOT')
        self.app_version: str = os.getenv('APP_VERSION', '1.0.0')

        # Logging Configuration
        self.log_level: str = os.getenv('LOG_LEVEL', 'INFO')
        self.log_format: str = os.getenv('LOG_FORMAT', 'json')
        self.log_file: str = os.getenv('LOG_FILE', 'logs/app.log')
        self.log_max_size: int = int(os.getenv('LOG_MAX_SIZE', '10485760'))  # 10MB
        self.log_backup_count: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))

        # Rate Limiting
        self.rate_limit_enabled: bool = os.getenv('RATE_LIMIT_ENABLED', 'True').lower() in ('true', '1', 'yes')
        self.rate_limit_per_minute: int = int(os.getenv('RATE_LIMIT_REQUESTS_PER_MINUTE', '30'))
        self.rate_limit_per_hour: int = int(os.getenv('RATE_LIMIT_REQUESTS_PER_HOUR', '500'))

        # Payment Settings
        self.payment_request_timeout: int = int(os.getenv('PAYMENT_REQUEST_TIMEOUT', '300'))
        self.enable_payment_notifications: bool = os.getenv('ENABLE_PAYMENT_NOTIFICATIONS', 'True').lower() in ('true', '1', 'yes')
        self.enable_transaction_logging: bool = os.getenv('ENABLE_TRANSACTION_LOGGING', 'True').lower() in ('true', '1', 'yes')

        # API Configuration
        self.api_host: str = os.getenv('API_HOST', '0.0.0.0')
        self.api_port: int = int(os.getenv('API_PORT', '8000'))
        self.api_timeout: int = int(os.getenv('TIMEOUT', '30'))

        # Security
        self.secret_key: str = os.getenv('SECRET_KEY', 'change-me-in-production')

        # Set M-Pesa URLs based on environment
        self._set_mpesa_urls()

        # Validate configuration
        self._validate_config()

    def _get_required_env(self, key: str) -> str:
        """
        Get a required environment variable.

        Args:
            key: Environment variable name

        Returns:
            Value of the environment variable

        Raises:
            ConfigError: If the environment variable is not set
        """
        value = os.getenv(key)
        if not value:
            raise ConfigError(f"Required environment variable '{key}' is not set")
        return value

    def _get_mpesa_environment(self) -> Literal['sandbox', 'production']:
        """
        Get and validate M-Pesa environment setting.

        Returns:
            Either 'sandbox' or 'production'

        Raises:
            ConfigError: If environment is invalid
        """
        env = os.getenv('ENVIRONMENT', 'development').lower()
        # Map app environment to M-Pesa environment
        if env == 'production':
            return 'production'
        return 'sandbox'

    def _set_mpesa_urls(self) -> None:
        """Set M-Pesa API URLs based on the environment."""
        endpoints = self.MPESA_ENDPOINTS[self.mpesa_environment]
        self.mpesa_auth_url: str = endpoints['auth']
        self.mpesa_stk_push_url: str = endpoints['stk_push']
        self.mpesa_query_url: str = endpoints['query']
        self.mpesa_b2c_url: str = endpoints['b2c']
        self.mpesa_c2b_register_url: str = endpoints['c2b_register']
        self.mpesa_transaction_status_url: str = endpoints['transaction_status']
        self.mpesa_account_balance_url: str = endpoints['account_balance']

    def _validate_config(self) -> None:
        """
        Validate configuration values.

        Raises:
            ConfigError: If any configuration value is invalid
        """
        # Validate amount limits
        if self.min_amount < 1:
            raise ConfigError(f"MIN_PAYMENT_AMOUNT must be at least 1, got {self.min_amount}")

        if self.max_amount < self.min_amount:
            raise ConfigError(
                f"MAX_PAYMENT_AMOUNT ({self.max_amount}) must be greater than "
                f"MIN_PAYMENT_AMOUNT ({self.min_amount})"
            )

        # Validate M-Pesa shortcode format
        if not self.mpesa_shortcode.isdigit():
            raise ConfigError(f"MPESA_SHORTCODE must be numeric, got '{self.mpesa_shortcode}'")

        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_log_levels:
            raise ConfigError(
                f"LOG_LEVEL must be one of {valid_log_levels}, got '{self.log_level}'"
            )

        # Validate seller chat ID format
        if not self.seller_chat_id.lstrip('-').isdigit():
            raise ConfigError(
                f"SELLER_CHAT_ID must be numeric (can start with -), "
                f"got '{self.seller_chat_id}'"
            )

        # Validate port ranges
        if not 1 <= self.api_port <= 65535:
            raise ConfigError(f"API_PORT must be between 1 and 65535, got {self.api_port}")

        if not 1 <= self.db_port <= 65535:
            raise ConfigError(f"DB_PORT must be between 1 and 65535, got {self.db_port}")

    @property
    def has_database_config(self) -> bool:
        """Check if database configuration is complete."""
        return all([
            self.db_host,
            self.db_user,
            self.db_password,
            self.db_name
        ])

    @property
    def has_supabase_config(self) -> bool:
        """Check if Supabase configuration is complete."""
        return bool(self.supabase_url and self.supabase_key)

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.mpesa_environment == 'production'

    @property
    def is_sandbox(self) -> bool:
        """Check if running in sandbox environment."""
        return self.mpesa_environment == 'sandbox'

    @property
    def is_debug(self) -> bool:
        """Check if debug mode is enabled."""
        return self.app_debug

    def __repr__(self) -> str:
        """String representation of Config (hiding sensitive data)."""
        return (
            f"Config(environment={self.mpesa_environment}, "
            f"shortcode={self.mpesa_shortcode}, "
            f"app_env={self.app_env}, "
            f"has_db={self.has_database_config})"
        )


# Singleton instance for easy access
_config_instance: Optional[Config] = None


def get_config(env_file: Optional[str] = None, reload: bool = False) -> Config:
    """
    Get or create the global Config instance.

    Args:
        env_file: Optional path to .env file
        reload: If True, force reload configuration

    Returns:
        Config instance

    Raises:
        ConfigError: If configuration is invalid

    Example:
        >>> config = get_config()
        >>> print(config.mpesa_environment)
        sandbox
    """
    global _config_instance

    if _config_instance is None or reload:
        _config_instance = Config(env_file)

    return _config_instance


if __name__ == '__main__':
    # Test configuration loading
    try:
        config = get_config()
        print("✓ Configuration loaded successfully!")
        print(f"\n{config}")
        print(f"\nEnvironment: {config.mpesa_environment}")
        print(f"Shortcode: {config.mpesa_shortcode}")
        print(f"Database configured: {config.has_database_config}")
        print(f"Supabase configured: {config.has_supabase_config}")
        print(f"Amount range: {config.min_amount} - {config.max_amount} KES")
        print(f"Debug mode: {config.is_debug}")
    except ConfigError as e:
        print(f"✗ Configuration error: {e}")
