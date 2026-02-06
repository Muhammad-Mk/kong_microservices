"""
Authentication routes for Auth Service

Routes are at root level since Kong strips /v1/auth prefix.
Example: /v1/auth/login -> /login
"""
import jwt
import datetime
import uuid
import logging
from flask import request, jsonify, current_app
from . import auth_bp

logger = logging.getLogger(__name__)

# In-memory user store (use database in production)
users_db = {}
# Token blacklist for logout
token_blacklist = set()


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user
    ---
    Request Body:
        - username: string (required)
        - email: string (required)
        - password: string (required)
    """
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("Registration attempt with empty payload")
            return jsonify({
                'success': False,
                'error': 'Request body is required',
                'code': 'INVALID_REQUEST'
            }), 400
        
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Validation
        if not all([username, email, password]):
            return jsonify({
                'success': False,
                'error': 'Username, email, and password are required',
                'code': 'MISSING_FIELDS'
            }), 400
        
        # Check if user exists
        if email in users_db:
            logger.info(f"Registration failed: email {email} already exists")
            return jsonify({
                'success': False,
                'error': 'User with this email already exists',
                'code': 'USER_EXISTS'
            }), 409
        
        # Create user
        user_id = str(uuid.uuid4())
        users_db[email] = {
            'id': user_id,
            'username': username,
            'email': email,
            'password': password,  # In production, hash this!
            'created_at': datetime.datetime.utcnow().isoformat(),
            'is_active': True
        }
        
        logger.info(f"User registered successfully: {email}")
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'data': {
                'user_id': user_id,
                'username': username,
                'email': email
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and return JWT tokens
    ---
    Request Body:
        - email: string (required)
        - password: string (required)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required',
                'code': 'INVALID_REQUEST'
            }), 400
        
        email = data.get('email')
        password = data.get('password')
        
        if not all([email, password]):
            return jsonify({
                'success': False,
                'error': 'Email and password are required',
                'code': 'MISSING_FIELDS'
            }), 400
        
        # Find user
        user = users_db.get(email)
        
        if not user or user['password'] != password:
            logger.warning(f"Failed login attempt for: {email}")
            return jsonify({
                'success': False,
                'error': 'Invalid credentials',
                'code': 'INVALID_CREDENTIALS'
            }), 401
        
        if not user.get('is_active', True):
            return jsonify({
                'success': False,
                'error': 'Account is deactivated',
                'code': 'ACCOUNT_INACTIVE'
            }), 403
        
        # Generate tokens
        now = datetime.datetime.utcnow()
        
        # Access token payload
        # IMPORTANT: 'iss' claim must match Kong consumer's jwt_secrets key
        access_payload = {
            'sub': user['id'],
            'email': user['email'],
            'username': user['username'],
            'type': 'access',
            'iat': now,
            'exp': now + datetime.timedelta(seconds=current_app.config['JWT_ACCESS_TOKEN_EXPIRES']),
            'jti': str(uuid.uuid4()),
            'iss': 'kong-demo-auth'  # Must match Kong consumer key
        }
        
        # Refresh token payload
        refresh_payload = {
            'sub': user['id'],
            'type': 'refresh',
            'iat': now,
            'exp': now + datetime.timedelta(seconds=current_app.config['JWT_REFRESH_TOKEN_EXPIRES']),
            'jti': str(uuid.uuid4()),
            'iss': 'kong-demo-auth'
        }
        
        access_token = jwt.encode(
            access_payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm=current_app.config['JWT_ALGORITHM']
        )
        
        refresh_token = jwt.encode(
            refresh_payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm=current_app.config['JWT_ALGORITHM']
        )
        
        logger.info(f"User logged in successfully: {email}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'data': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email']
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@auth_bp.route('/verify', methods=['GET'])
def verify():
    """
    Verify JWT token validity
    ---
    Headers:
        - Authorization: Bearer <token>
    """
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'success': False,
                'error': 'Authorization header is required',
                'code': 'MISSING_AUTH'
            }), 401
        
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({
                'success': False,
                'error': 'Invalid authorization header format',
                'code': 'INVALID_AUTH_FORMAT'
            }), 401
        
        token = parts[1]
        
        # Check if token is blacklisted
        if token in token_blacklist:
            return jsonify({
                'success': False,
                'error': 'Token has been revoked',
                'code': 'TOKEN_REVOKED'
            }), 401
        
        # Decode and verify token
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']]
        )
        
        return jsonify({
            'success': True,
            'message': 'Token is valid',
            'data': {
                'user_id': payload.get('sub'),
                'email': payload.get('email'),
                'username': payload.get('username'),
                'issued_at': payload.get('iat'),
                'expires_at': payload.get('exp')
            }
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({
            'success': False,
            'error': 'Token has expired',
            'code': 'TOKEN_EXPIRED'
        }), 401
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token verification attempt: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Invalid token',
            'code': 'INVALID_TOKEN'
        }), 401
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Logout user by blacklisting their token
    ---
    Headers:
        - Authorization: Bearer <token>
    """
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'success': False,
                'error': 'Authorization header is required',
                'code': 'MISSING_AUTH'
            }), 401
        
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({
                'success': False,
                'error': 'Invalid authorization header format',
                'code': 'INVALID_AUTH_FORMAT'
            }), 401
        
        token = parts[1]
        
        # Add token to blacklist
        token_blacklist.add(token)
        
        logger.info("User logged out successfully")
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
