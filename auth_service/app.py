"""
Auth Service - Main Application Entry Point
Handles user authentication, JWT token generation and validation
"""
import os
import logging
import sys
from flask import Flask, jsonify
from pythonjsonlogger import jsonlogger

from config import get_config
from routes import auth_bp, health_bp, token_bp


def setup_logging(app):
    """Configure structured JSON logging"""
    log_handler = logging.StreamHandler(sys.stdout)
    
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    log_handler.setFormatter(formatter)
    
    # Set log level
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    log_handler.setLevel(getattr(logging, log_level))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(log_handler)
    root_logger.setLevel(getattr(logging, log_level))
    
    # Configure Flask app logger
    app.logger.handlers = []
    app.logger.addHandler(log_handler)
    app.logger.setLevel(getattr(logging, log_level))
    
    return app


def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Load configuration
    config_class = get_config()
    app.config.from_object(config_class)
    
    # Setup logging
    setup_logging(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(token_bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Resource not found',
            'code': 'NOT_FOUND'
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'success': False,
            'error': 'Method not allowed',
            'code': 'METHOD_NOT_ALLOWED'
        }), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
    
    app.logger.info(f"Auth Service started - Version {app.config.get('SERVICE_VERSION', '1.0.0')}")
    
    return app


# Create application instance
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
