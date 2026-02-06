"""
Channel management routes for Notification Service
"""
import datetime
import uuid
import logging
from flask import request, jsonify
from . import channel_bp

logger = logging.getLogger(__name__)

# In-memory channel preferences store (use database in production)
channel_preferences_db = {
    'user-001': {
        'user_id': 'user-001',
        'preferences': {
            'email': {
                'enabled': True,
                'address': 'john@example.com',
                'verified': True
            },
            'sms': {
                'enabled': False,
                'phone': '+1234567890',
                'verified': False
            },
            'push': {
                'enabled': True,
                'device_tokens': ['token-abc-123']
            },
            'in_app': {
                'enabled': True
            }
        },
        'notification_types': {
            'trade_executed': ['email', 'push', 'in_app'],
            'price_alert': ['push', 'in_app'],
            'system': ['email', 'in_app'],
            'account': ['email', 'sms'],
            'security': ['email', 'sms', 'push']
        },
        'quiet_hours': {
            'enabled': False,
            'start': '22:00',
            'end': '08:00',
            'timezone': 'UTC'
        },
        'updated_at': '2024-01-15T10:30:00Z'
    }
}


def get_user_from_header():
    """Extract user ID from Kong-forwarded header"""
    user_id = request.headers.get('X-Consumer-Custom-ID')
    username = request.headers.get('X-Consumer-Username')
    return user_id or username or 'user-001'


@channel_bp.route('/preferences', methods=['GET'])
def get_preferences():
    """
    Get notification channel preferences for the current user
    """
    try:
        user_id = get_user_from_header()
        
        preferences = channel_preferences_db.get(user_id)
        
        if not preferences:
            # Return default preferences
            preferences = {
                'user_id': user_id,
                'preferences': {
                    'email': {'enabled': True, 'address': '', 'verified': False},
                    'sms': {'enabled': False, 'phone': '', 'verified': False},
                    'push': {'enabled': True, 'device_tokens': []},
                    'in_app': {'enabled': True}
                },
                'notification_types': {
                    'trade_executed': ['in_app'],
                    'price_alert': ['in_app'],
                    'system': ['in_app'],
                    'account': ['in_app'],
                    'security': ['in_app']
                },
                'quiet_hours': {
                    'enabled': False,
                    'start': '22:00',
                    'end': '08:00',
                    'timezone': 'UTC'
                }
            }
        
        logger.info(f"Preferences retrieved for user: {user_id}")
        
        return jsonify({
            'success': True,
            'data': preferences
        }), 200
        
    except Exception as e:
        logger.error(f"Get preferences error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@channel_bp.route('/preferences', methods=['PUT'])
def update_preferences():
    """
    Update notification channel preferences
    """
    try:
        user_id = get_user_from_header()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required',
                'code': 'INVALID_REQUEST'
            }), 400
        
        existing = channel_preferences_db.get(user_id, {
            'user_id': user_id,
            'preferences': {},
            'notification_types': {},
            'quiet_hours': {}
        })
        
        # Update preferences
        if 'preferences' in data:
            existing['preferences'].update(data['preferences'])
        
        if 'notification_types' in data:
            existing['notification_types'].update(data['notification_types'])
        
        if 'quiet_hours' in data:
            existing['quiet_hours'].update(data['quiet_hours'])
        
        existing['updated_at'] = datetime.datetime.utcnow().isoformat()
        
        channel_preferences_db[user_id] = existing
        
        logger.info(f"Preferences updated for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Preferences updated successfully',
            'data': existing
        }), 200
        
    except Exception as e:
        logger.error(f"Update preferences error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@channel_bp.route('/verify', methods=['POST'])
def verify_channel():
    """
    Send verification code for a channel (email/sms)
    """
    try:
        user_id = get_user_from_header()
        data = request.get_json()
        
        if not data or 'channel' not in data:
            return jsonify({
                'success': False,
                'error': 'Channel is required',
                'code': 'MISSING_CHANNEL'
            }), 400
        
        channel = data['channel']
        
        if channel not in ['email', 'sms']:
            return jsonify({
                'success': False,
                'error': 'Only email and sms channels can be verified',
                'code': 'INVALID_CHANNEL'
            }), 400
        
        # Generate verification code (in production, send actual verification)
        verification_code = str(uuid.uuid4().int)[:6]
        
        logger.info(f"Verification code sent for user {user_id} channel {channel}")
        
        return jsonify({
            'success': True,
            'message': f'Verification code sent to your {channel}',
            'data': {
                'channel': channel,
                'expires_in': 600  # 10 minutes
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Verify channel error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@channel_bp.route('/register-device', methods=['POST'])
def register_device():
    """
    Register a device for push notifications
    """
    try:
        user_id = get_user_from_header()
        data = request.get_json()
        
        if not data or 'device_token' not in data:
            return jsonify({
                'success': False,
                'error': 'Device token is required',
                'code': 'MISSING_TOKEN'
            }), 400
        
        device_token = data['device_token']
        platform = data.get('platform', 'unknown')
        
        # Get or create preferences
        if user_id not in channel_preferences_db:
            channel_preferences_db[user_id] = {
                'user_id': user_id,
                'preferences': {
                    'push': {'enabled': True, 'device_tokens': []}
                }
            }
        
        prefs = channel_preferences_db[user_id]
        
        if 'push' not in prefs.get('preferences', {}):
            prefs['preferences']['push'] = {'enabled': True, 'device_tokens': []}
        
        # Add device token if not exists
        tokens = prefs['preferences']['push'].get('device_tokens', [])
        if device_token not in tokens:
            tokens.append(device_token)
            prefs['preferences']['push']['device_tokens'] = tokens
        
        prefs['updated_at'] = datetime.datetime.utcnow().isoformat()
        
        logger.info(f"Device registered for user {user_id}: {platform}")
        
        return jsonify({
            'success': True,
            'message': 'Device registered successfully',
            'data': {
                'device_token': device_token,
                'platform': platform,
                'total_devices': len(tokens)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Register device error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
