"""
Admin routes for User Service
"""
import datetime
import uuid
import logging
from flask import request, jsonify
from . import admin_bp
from .user_routes import users_db

logger = logging.getLogger(__name__)


@admin_bp.route('/users/create', methods=['POST'])
def admin_create_user():
    """
    Admin endpoint to create a new user
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required',
                'code': 'INVALID_REQUEST'
            }), 400
        
        # Required fields
        required_fields = ['username', 'email', 'first_name', 'last_name']
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'code': 'MISSING_FIELDS'
            }), 400
        
        # Check for duplicate email
        for user in users_db.values():
            if user['email'] == data['email']:
                return jsonify({
                    'success': False,
                    'error': 'User with this email already exists',
                    'code': 'DUPLICATE_EMAIL'
                }), 409
        
        # Create user
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.utcnow().isoformat()
        
        new_user = {
            'id': user_id,
            'username': data['username'],
            'email': data['email'],
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'phone': data.get('phone', ''),
            'role': data.get('role', 'user'),
            'is_active': True,
            'created_at': now,
            'updated_at': now
        }
        
        users_db[user_id] = new_user
        
        logger.info(f"Admin created new user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'data': new_user
        }), 201
        
    except Exception as e:
        logger.error(f"Admin create user error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@admin_bp.route('/users/<user_id>/role', methods=['PUT'])
def admin_update_role(user_id):
    """
    Admin endpoint to update user role
    """
    try:
        user = users_db.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404
        
        data = request.get_json()
        
        if not data or 'role' not in data:
            return jsonify({
                'success': False,
                'error': 'Role is required',
                'code': 'MISSING_ROLE'
            }), 400
        
        valid_roles = ['user', 'admin', 'moderator', 'viewer']
        
        if data['role'] not in valid_roles:
            return jsonify({
                'success': False,
                'error': f'Invalid role. Valid roles: {", ".join(valid_roles)}',
                'code': 'INVALID_ROLE'
            }), 400
        
        user['role'] = data['role']
        user['updated_at'] = datetime.datetime.utcnow().isoformat()
        
        logger.info(f"Admin updated role for user {user_id}: {data['role']}")
        
        return jsonify({
            'success': True,
            'message': 'User role updated successfully',
            'data': {
                'user_id': user_id,
                'role': data['role']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Admin update role error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@admin_bp.route('/users/<user_id>/activate', methods=['POST'])
def admin_activate_user(user_id):
    """
    Admin endpoint to activate a user
    """
    try:
        user = users_db.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404
        
        user['is_active'] = True
        user['updated_at'] = datetime.datetime.utcnow().isoformat()
        
        logger.info(f"Admin activated user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'User activated successfully',
            'data': {
                'user_id': user_id,
                'is_active': True
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Admin activate user error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@admin_bp.route('/stats', methods=['GET'])
def admin_stats():
    """
    Admin endpoint to get user statistics
    """
    try:
        total_users = len(users_db)
        active_users = sum(1 for u in users_db.values() if u.get('is_active', False))
        inactive_users = total_users - active_users
        
        # Role distribution
        roles = {}
        for user in users_db.values():
            role = user.get('role', 'user')
            roles[role] = roles.get(role, 0) + 1
        
        logger.info("Admin retrieved user statistics")
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': inactive_users,
                'roles_distribution': roles,
                'timestamp': datetime.datetime.utcnow().isoformat()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Admin stats error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
