"""
Routes package for Auth Service
Kong strips /v1 prefix, so services receive clean paths: /auth/*
"""
from flask import Blueprint

# Create blueprints with /auth prefix (Kong strips /v1)
# External: /v1/auth/login → Internal: /auth/login
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
token_bp = Blueprint('token', __name__, url_prefix='/auth')
health_bp = Blueprint('health', __name__, url_prefix='/auth')

# Import routes to register them
from . import auth_routes
from . import health_routes
from . import token_routes
