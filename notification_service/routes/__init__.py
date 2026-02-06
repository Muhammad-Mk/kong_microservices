"""
Routes package for Notification Service
Kong strips /v1 prefix, so services receive clean paths: /notifications/*, /channels/*
"""
from flask import Blueprint

# Create blueprints with clean prefixes (Kong strips /v1)
# External: /v1/notifications/list → Internal: /notifications/list
# External: /v1/channels/list → Internal: /channels/list
notification_bp = Blueprint('notifications', __name__, url_prefix='/notifications')
channel_bp = Blueprint('channels', __name__, url_prefix='/channels')
health_bp = Blueprint('health', __name__, url_prefix='/notifications')

# Import routes to register them
from . import notification_routes
from . import channel_routes
from . import health_routes
