-- Database schema for M-Pesa Bot
-- This schema supports the callback server and bot functionality

CREATE DATABASE IF NOT EXISTS mpesa_bot;
USE mpesa_bot;

-- Transactions table to store M-Pesa payment records
CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    checkout_request_id VARCHAR(100) UNIQUE NOT NULL,
    merchant_request_id VARCHAR(100) NOT NULL,
    result_code INT DEFAULT NULL,
    result_desc VARCHAR(255) DEFAULT NULL,
    amount DECIMAL(10, 2) DEFAULT NULL,
    mpesa_receipt_number VARCHAR(50) DEFAULT NULL,
    phone_number VARCHAR(15) DEFAULT NULL,
    transaction_date DATETIME DEFAULT NULL,
    status ENUM('Pending', 'Success', 'Failed', 'Cancelled') DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_checkout_request_id (checkout_request_id),
    INDEX idx_phone_number (phone_number),
    INDEX idx_status (status),
    INDEX idx_transaction_date (transaction_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Users table to store Telegram user information
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_chat_id BIGINT UNIQUE NOT NULL,
    telegram_username VARCHAR(100) DEFAULT NULL,
    phone_number VARCHAR(15) DEFAULT NULL,
    first_name VARCHAR(100) DEFAULT NULL,
    last_name VARCHAR(100) DEFAULT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_telegram_chat_id (telegram_chat_id),
    INDEX idx_phone_number (phone_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Payment requests table to track initiated payments
CREATE TABLE IF NOT EXISTS payment_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    checkout_request_id VARCHAR(100) UNIQUE DEFAULT NULL,
    merchant_request_id VARCHAR(100) DEFAULT NULL,
    phone_number VARCHAR(15) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    account_reference VARCHAR(100) DEFAULT NULL,
    transaction_desc VARCHAR(255) DEFAULT NULL,
    status ENUM('Initiated', 'Pending', 'Completed', 'Failed', 'Cancelled') DEFAULT 'Initiated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_checkout_request_id (checkout_request_id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Callback logs table to store all incoming callbacks for debugging
CREATE TABLE IF NOT EXISTS callback_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    checkout_request_id VARCHAR(100) DEFAULT NULL,
    raw_payload TEXT NOT NULL,
    result_code INT DEFAULT NULL,
    result_desc VARCHAR(255) DEFAULT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_checkout_request_id (checkout_request_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Admin notifications table to track sent notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id INT DEFAULT NULL,
    notification_type ENUM('admin', 'user', 'receipt') NOT NULL,
    recipient VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    status ENUM('sent', 'failed') DEFAULT 'sent',
    error_message TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE SET NULL,
    INDEX idx_transaction_id (transaction_id),
    INDEX idx_notification_type (notification_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
