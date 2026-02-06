"""
Configuration module for Notification Service
"""
import os


class Config:
    """Base configuration"""
    DEBUG = False
    TESTING = False
    
    # JWT Configuration (for token validation)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-super-secret-key-change-in-production')
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    
    # Service Configuration
    SERVICE_NAME = 'notification_service'
    SERVICE_VERSION = '1.0.0'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = 'json'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True


def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development')
    config_map = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
        'testing': TestingConfig
    }
    return config_map.get(env, DevelopmentConfig)
