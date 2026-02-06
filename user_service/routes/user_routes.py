"""
User management routes for User Service

Routes are at root level since Kong strips /v1/users prefix.
Example: /v1/users/profile -> /profile
"""
import datetime
import uuid
import logging
from flask import request, jsonify
from . import user_bp

logger = logging.getLogger(__name__)

# In-memory user store (use database in production)
users_db = {
    'user-001': {
        'id': 'user-001',
        'username': 'john_doe',
        'email': 'john@example.com',
        'first_name': 'John',
        'last_name': 'Doe',
        'phone': '+1234567890',
        'role': 'user',
        'is_active': True,
        'created_at': '2024-01-15T10:30:00Z',
        'updated_at': '2024-01-15T10:30:00Z'
    },
    'user-002': {
        'id': 'user-002',
        'username': 'jane_smith',
        'email': 'jane@example.com',
        'first_name': 'Jane',
        'last_name': 'Smith',
        'phone': '+0987654321',
        'role': 'admin',
        'is_active': True,
        'created_at': '2024-01-10T08:15:00Z',
        'updated_at': '2024-01-12T14:20:00Z'
    }
}


def get_user_from_header():
    """Extract user ID from Kong-forwarded header"""
    # Kong JWT plugin adds X-Consumer-Username or X-Consumer-Custom-ID
    user_id = request.headers.get('X-Consumer-Custom-ID')
    username = request.headers.get('X-Consumer-Username')
    return user_id or username


@user_bp.route('/profile', methods=['GET'])
def get_profile():
    """
    Get current user's profile
    User ID is extracted from JWT token (forwarded by Kong)
    """
    try:
        # In production, get user ID from Kong's JWT validation
        user_id = get_user_from_header()
        
        # For demo, if no header, return first user
        if not user_id:
            user_id = 'user-001'
        
        user = users_db.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404
        
        # Remove sensitive fields
        profile = {k: v for k, v in user.items() if k not in ['password']}
        
        logger.info(f"Profile retrieved for user: {user_id}")
        
        return jsonify({
            'success': True,
            'data': profile
        }), 200
        
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@user_bp.route('/profile', methods=['PUT'])
def update_profile():
    """
    Update current user's profile
    """
    try:
        user_id = get_user_from_header() or 'user-001'
        
        user = users_db.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required',
                'code': 'INVALID_REQUEST'
            }), 400
        
        # Allowed fields to update
        allowed_fields = ['first_name', 'last_name', 'phone', 'username']
        
        for field in allowed_fields:
            if field in data:
                user[field] = data[field]
        
        user['updated_at'] = datetime.datetime.utcnow().isoformat()
        
        logger.info(f"Profile updated for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'data': {k: v for k, v in user.items() if k not in ['password']}
        }), 200
        
    except Exception as e:
        logger.error(f"Update profile error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@user_bp.route('/list', methods=['GET'])
def list_users():
    """
    List all users with pagination
    Query params: page, limit, search
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        search = request.args.get('search', '', type=str)
        
        # Validate pagination
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 10
        
        # Filter users
        filtered_users = []
        for user in users_db.values():
            if search:
                if (search.lower() in user.get('username', '').lower() or
                    search.lower() in user.get('email', '').lower() or
                    search.lower() in user.get('first_name', '').lower() or
                    search.lower() in user.get('last_name', '').lower()):
                    filtered_users.append(user)
            else:
                filtered_users.append(user)
        
        # Calculate pagination
        total = len(filtered_users)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        paginated_users = filtered_users[start_idx:end_idx]
        
        # Remove sensitive fields
        clean_users = [
            {k: v for k, v in u.items() if k not in ['password']}
            for u in paginated_users
        ]
        
        logger.info(f"Users list retrieved: page={page}, limit={limit}, total={total}")
        
        return jsonify({
            'success': True,
            'data': {
                'users': clean_users,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'total_pages': (total + limit - 1) // limit
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"List users error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@user_bp.route('/<user_id>', methods=['GET'])
def get_user(user_id):
    """
    Get a specific user by ID
    """
    try:
        user = users_db.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404
        
        # Remove sensitive fields
        profile = {k: v for k, v in user.items() if k not in ['password']}
        
        logger.info(f"User retrieved: {user_id}")
        
        return jsonify({
            'success': True,
            'data': profile
        }), 200
        
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@user_bp.route('/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """
    Delete a user (soft delete - deactivate)
    """
    try:
        user = users_db.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404
        
        # Soft delete - just deactivate
        user['is_active'] = False
        user['updated_at'] = datetime.datetime.utcnow().isoformat()
        
        logger.info(f"User deactivated: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Delete user error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
