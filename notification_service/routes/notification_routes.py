"""
Notification management routes for Notification Service
"""
import datetime
import uuid
import logging
from flask import request, jsonify
from . import notification_bp

logger = logging.getLogger(__name__)

# In-memory notifications store (use database in production)
notifications_db = {
    'notif-001': {
        'id': 'notif-001',
        'user_id': 'user-001',
        'type': 'trade_executed',
        'channel': 'email',
        'title': 'Trade Executed Successfully',
        'message': 'Your buy order for 100 shares of AAPL has been executed at $175.50',
        'status': 'delivered',
        'read': True,
        'created_at': '2024-01-15T10:30:10Z',
        'delivered_at': '2024-01-15T10:30:15Z'
    },
    'notif-002': {
        'id': 'notif-002',
        'user_id': 'user-001',
        'type': 'price_alert',
        'channel': 'push',
        'title': 'Price Alert: GOOGL',
        'message': 'GOOGL has reached your target price of $145.00',
        'status': 'delivered',
        'read': False,
        'created_at': '2024-01-16T09:00:00Z',
        'delivered_at': '2024-01-16T09:00:05Z'
    },
    'notif-003': {
        'id': 'notif-003',
        'user_id': 'user-002',
        'type': 'system',
        'channel': 'in_app',
        'title': 'System Maintenance Scheduled',
        'message': 'Scheduled maintenance on January 20, 2024 from 2:00 AM to 4:00 AM UTC',
        'status': 'pending',
        'read': False,
        'created_at': '2024-01-16T12:00:00Z',
        'delivered_at': None
    }
}


def get_user_from_header():
    """Extract user ID from Kong-forwarded header"""
    user_id = request.headers.get('X-Consumer-Custom-ID')
    username = request.headers.get('X-Consumer-Username')
    return user_id or username or 'user-001'


@notification_bp.route('/send', methods=['POST'])
def send_notification():
    """
    Send a new notification
    ---
    Request Body:
        - user_id: string (required)
        - type: string (required) - trade_executed, price_alert, system, account
        - channel: string (required) - email, sms, push, in_app
        - title: string (required)
        - message: string (required)
    
    Note: This endpoint requires API key authentication
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
        required_fields = ['user_id', 'type', 'channel', 'title', 'message']
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'code': 'MISSING_FIELDS'
            }), 400
        
        # Validate type
        valid_types = ['trade_executed', 'price_alert', 'system', 'account', 'security']
        if data['type'] not in valid_types:
            return jsonify({
                'success': False,
                'error': f'Invalid notification type. Valid types: {", ".join(valid_types)}',
                'code': 'INVALID_TYPE'
            }), 400
        
        # Validate channel
        valid_channels = ['email', 'sms', 'push', 'in_app']
        if data['channel'] not in valid_channels:
            return jsonify({
                'success': False,
                'error': f'Invalid channel. Valid channels: {", ".join(valid_channels)}',
                'code': 'INVALID_CHANNEL'
            }), 400
        
        notif_id = f"notif-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.utcnow().isoformat()
        
        new_notification = {
            'id': notif_id,
            'user_id': data['user_id'],
            'type': data['type'],
            'channel': data['channel'],
            'title': data['title'],
            'message': data['message'],
            'status': 'pending',
            'read': False,
            'created_at': now,
            'delivered_at': None,
            'metadata': data.get('metadata', {})
        }
        
        # Simulate delivery (in production, use actual notification service)
        new_notification['status'] = 'delivered'
        new_notification['delivered_at'] = datetime.datetime.utcnow().isoformat()
        
        notifications_db[notif_id] = new_notification
        
        logger.info(f"Notification sent: {notif_id} to user {data['user_id']} via {data['channel']}")
        
        return jsonify({
            'success': True,
            'message': 'Notification sent successfully',
            'data': new_notification
        }), 201
        
    except Exception as e:
        logger.error(f"Send notification error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@notification_bp.route('/list', methods=['GET'])
def list_notifications():
    """
    List notifications with pagination and filters
    Query params: page, limit, type, channel, read, status
    """
    try:
        user_id = get_user_from_header()
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        notif_type = request.args.get('type', '', type=str)
        channel = request.args.get('channel', '', type=str)
        read = request.args.get('read', None, type=str)
        status = request.args.get('status', '', type=str)
        
        # Validate pagination
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 10
        
        # Filter notifications
        filtered_notifications = []
        for notif in notifications_db.values():
            match = True
            
            if notif_type and notif.get('type') != notif_type:
                match = False
            
            if channel and notif.get('channel') != channel:
                match = False
            
            if read is not None:
                read_bool = read.lower() == 'true'
                if notif.get('read') != read_bool:
                    match = False
            
            if status and notif.get('status') != status:
                match = False
            
            if match:
                filtered_notifications.append(notif)
        
        # Sort by created_at descending
        filtered_notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Calculate pagination
        total = len(filtered_notifications)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        paginated_notifications = filtered_notifications[start_idx:end_idx]
        
        # Count unread
        unread_count = sum(1 for n in notifications_db.values() if not n.get('read', True))
        
        logger.info(f"Notifications list retrieved: page={page}, limit={limit}, total={total}")
        
        return jsonify({
            'success': True,
            'data': {
                'notifications': paginated_notifications,
                'unread_count': unread_count,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'total_pages': (total + limit - 1) // limit
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"List notifications error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@notification_bp.route('/<notification_id>', methods=['GET'])
def get_notification(notification_id):
    """
    Get a specific notification by ID
    """
    try:
        notification = notifications_db.get(notification_id)
        
        if not notification:
            return jsonify({
                'success': False,
                'error': 'Notification not found',
                'code': 'NOTIFICATION_NOT_FOUND'
            }), 404
        
        logger.info(f"Notification retrieved: {notification_id}")
        
        return jsonify({
            'success': True,
            'data': notification
        }), 200
        
    except Exception as e:
        logger.error(f"Get notification error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@notification_bp.route('/delete/<notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    """
    Delete a notification
    """
    try:
        if notification_id not in notifications_db:
            return jsonify({
                'success': False,
                'error': 'Notification not found',
                'code': 'NOTIFICATION_NOT_FOUND'
            }), 404
        
        del notifications_db[notification_id]
        
        logger.info(f"Notification deleted: {notification_id}")
        
        return jsonify({
            'success': True,
            'message': 'Notification deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Delete notification error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@notification_bp.route('/<notification_id>/read', methods=['POST'])
def mark_as_read(notification_id):
    """
    Mark a notification as read
    """
    try:
        notification = notifications_db.get(notification_id)
        
        if not notification:
            return jsonify({
                'success': False,
                'error': 'Notification not found',
                'code': 'NOTIFICATION_NOT_FOUND'
            }), 404
        
        notification['read'] = True
        notification['read_at'] = datetime.datetime.utcnow().isoformat()
        
        logger.info(f"Notification marked as read: {notification_id}")
        
        return jsonify({
            'success': True,
            'message': 'Notification marked as read',
            'data': notification
        }), 200
        
    except Exception as e:
        logger.error(f"Mark as read error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
