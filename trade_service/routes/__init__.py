"""
Routes package for Trade Service
Kong strips /v1 prefix, so services receive clean paths: /trades/*, /positions/*
"""
from flask import Blueprint

# Create blueprints with clean prefixes (Kong strips /v1)
# External: /v1/trades/create → Internal: /trades/create
# External: /v1/positions/list → Internal: /positions/list
trade_bp = Blueprint('trades', __name__, url_prefix='/trades')
position_bp = Blueprint('positions', __name__, url_prefix='/positions')
health_bp = Blueprint('health', __name__, url_prefix='/trades')

# Import routes to register them
from . import trade_routes
from . import position_routes
from . import health_routes
