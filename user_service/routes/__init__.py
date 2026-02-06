"""
Routes package for User Service
Kong strips /v1 prefix, so services receive clean paths: /users/*
"""
from flask import Blueprint

# Create blueprints with /users prefix (Kong strips /v1)
# External: /v1/users/profile → Internal: /users/profile
user_bp = Blueprint('users', __name__, url_prefix='/users')
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
health_bp = Blueprint('health', __name__, url_prefix='/users')

# Import routes to register them
from . import user_routes
from . import admin_routes
from . import health_routes
