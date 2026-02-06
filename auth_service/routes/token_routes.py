"""
Token management routes for Auth Service

Routes are at root level since Kong strips /v1/auth prefix.
"""
import jwt
import datetime
import uuid
import logging
from flask import request, jsonify, current_app
from . import token_bp
from .auth_routes import users_db, token_blacklist

logger = logging.getLogger(__name__)


@token_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    Refresh access token using refresh token
    ---
    Request Body:
        - refresh_token: string (required)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required',
                'code': 'INVALID_REQUEST'
            }), 400
        
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            return jsonify({
                'success': False,
                'error': 'Refresh token is required',
                'code': 'MISSING_TOKEN'
            }), 400
        
        # Check if token is blacklisted
        if refresh_token in token_blacklist:
            return jsonify({
                'success': False,
                'error': 'Refresh token has been revoked',
                'code': 'TOKEN_REVOKED'
            }), 401
        
        # Decode and verify refresh token
        payload = jwt.decode(
            refresh_token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']]
        )
        
        # Verify token type
        if payload.get('type') != 'refresh':
            return jsonify({
                'success': False,
                'error': 'Invalid token type',
                'code': 'INVALID_TOKEN_TYPE'
            }), 401
        
        user_id = payload.get('sub')
        
        # Find user by ID
        user = None
        for email, user_data in users_db.items():
            if user_data['id'] == user_id:
                user = user_data
                break
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404
        
        # Generate new access token
        now = datetime.datetime.utcnow()
        
        access_payload = {
            'sub': user['id'],
            'email': user['email'],
            'username': user['username'],
            'type': 'access',
            'iat': now,
            'exp': now + datetime.timedelta(seconds=current_app.config['JWT_ACCESS_TOKEN_EXPIRES']),
            'jti': str(uuid.uuid4()),
            'iss': 'kong-demo-auth'
        }
        
        new_access_token = jwt.encode(
            access_payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm=current_app.config['JWT_ALGORITHM']
        )
        
        logger.info(f"Token refreshed for user: {user['email']}")
        
        return jsonify({
            'success': True,
            'message': 'Token refreshed successfully',
            'data': {
                'access_token': new_access_token,
                'token_type': 'Bearer',
                'expires_in': current_app.config['JWT_ACCESS_TOKEN_EXPIRES']
            }
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({
            'success': False,
            'error': 'Refresh token has expired',
            'code': 'TOKEN_EXPIRED'
        }), 401
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid refresh token: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Invalid refresh token',
            'code': 'INVALID_TOKEN'
        }), 401
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@token_bp.route('/introspect', methods=['POST'])
def introspect_token():
    """
    Introspect token to get detailed information (OAuth 2.0 style)
    ---
    Request Body:
        - token: string (required)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'active': False,
                'error': 'Request body is required'
            }), 400
        
        token = data.get('token')
        
        if not token:
            return jsonify({
                'active': False,
                'error': 'Token is required'
            }), 400
        
        # Check if token is blacklisted
        if token in token_blacklist:
            return jsonify({
                'active': False
            }), 200
        
        # Decode and verify token
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=[current_app.config['JWT_ALGORITHM']]
        )
        
        return jsonify({
            'active': True,
            'sub': payload.get('sub'),
            'email': payload.get('email'),
            'username': payload.get('username'),
            'token_type': payload.get('type'),
            'iat': payload.get('iat'),
            'exp': payload.get('exp'),
            'jti': payload.get('jti'),
            'iss': payload.get('iss')
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({
            'active': False,
            'error': 'Token has expired'
        }), 200
    except jwt.InvalidTokenError:
        return jsonify({
            'active': False,
            'error': 'Invalid token'
        }), 200
    except Exception as e:
        logger.error(f"Token introspection error: {str(e)}")
        return jsonify({
            'active': False,
            'error': 'Internal server error'
        }), 500


@token_bp.route('/revoke', methods=['POST'])
def revoke_token():
    """
    Revoke a token (add to blacklist)
    ---
    Request Body:
        - token: string (required)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required',
                'code': 'INVALID_REQUEST'
            }), 400
        
        token = data.get('token')
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token is required',
                'code': 'MISSING_TOKEN'
            }), 400
        
        # Add token to blacklist
        token_blacklist.add(token)
        
        logger.info("Token revoked successfully")
        
        return jsonify({
            'success': True,
            'message': 'Token revoked successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Token revocation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
