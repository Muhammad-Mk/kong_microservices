"""
Trade management routes for Trade Service

Routes are at root level since Kong strips /v1/trades prefix.
Example: /v1/trades/create -> /create
"""
import datetime
import uuid
import logging
from flask import request, jsonify
from . import trade_bp

logger = logging.getLogger(__name__)

# In-memory trade store (use database in production)
trades_db = {
    'trade-001': {
        'id': 'trade-001',
        'user_id': 'user-001',
        'symbol': 'AAPL',
        'type': 'buy',
        'quantity': 100,
        'price': 175.50,
        'total_value': 17550.00,
        'status': 'executed',
        'created_at': '2024-01-15T10:30:00Z',
        'executed_at': '2024-01-15T10:30:05Z'
    },
    'trade-002': {
        'id': 'trade-002',
        'user_id': 'user-001',
        'symbol': 'GOOGL',
        'type': 'buy',
        'quantity': 50,
        'price': 142.25,
        'total_value': 7112.50,
        'status': 'executed',
        'created_at': '2024-01-14T09:15:00Z',
        'executed_at': '2024-01-14T09:15:03Z'
    },
    'trade-003': {
        'id': 'trade-003',
        'user_id': 'user-002',
        'symbol': 'MSFT',
        'type': 'sell',
        'quantity': 25,
        'price': 380.00,
        'total_value': 9500.00,
        'status': 'pending',
        'created_at': '2024-01-16T14:20:00Z',
        'executed_at': None
    }
}


def get_user_from_header():
    """Extract user ID from Kong-forwarded header"""
    user_id = request.headers.get('X-Consumer-Custom-ID')
    username = request.headers.get('X-Consumer-Username')
    return user_id or username or 'user-001'


@trade_bp.route('/create', methods=['POST'])
def create_trade():
    """
    Create a new trade order
    ---
    Request Body:
        - symbol: string (required)
        - type: string (buy/sell) (required)
        - quantity: integer (required)
        - price: float (optional - market order if not specified)
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
        required_fields = ['symbol', 'type', 'quantity']
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'code': 'MISSING_FIELDS'
            }), 400
        
        # Validate trade type
        if data['type'] not in ['buy', 'sell']:
            return jsonify({
                'success': False,
                'error': 'Trade type must be "buy" or "sell"',
                'code': 'INVALID_TRADE_TYPE'
            }), 400
        
        # Validate quantity
        if not isinstance(data['quantity'], int) or data['quantity'] <= 0:
            return jsonify({
                'success': False,
                'error': 'Quantity must be a positive integer',
                'code': 'INVALID_QUANTITY'
            }), 400
        
        user_id = get_user_from_header()
        trade_id = f"trade-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.utcnow().isoformat()
        
        # Default price for demo (in production, fetch from market data)
        price = data.get('price', 100.00)
        total_value = price * data['quantity']
        
        new_trade = {
            'id': trade_id,
            'user_id': user_id,
            'symbol': data['symbol'].upper(),
            'type': data['type'],
            'quantity': data['quantity'],
            'price': price,
            'total_value': total_value,
            'status': 'pending',
            'created_at': now,
            'executed_at': None
        }
        
        trades_db[trade_id] = new_trade
        
        logger.info(f"Trade created: {trade_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Trade order created successfully',
            'data': new_trade
        }), 201
        
    except Exception as e:
        logger.error(f"Create trade error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@trade_bp.route('/modify', methods=['PUT'])
def modify_trade():
    """
    Modify an existing pending trade
    ---
    Request Body:
        - trade_id: string (required)
        - quantity: integer (optional)
        - price: float (optional)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required',
                'code': 'INVALID_REQUEST'
            }), 400
        
        trade_id = data.get('trade_id')
        
        if not trade_id:
            return jsonify({
                'success': False,
                'error': 'Trade ID is required',
                'code': 'MISSING_TRADE_ID'
            }), 400
        
        trade = trades_db.get(trade_id)
        
        if not trade:
            return jsonify({
                'success': False,
                'error': 'Trade not found',
                'code': 'TRADE_NOT_FOUND'
            }), 404
        
        # Can only modify pending trades
        if trade['status'] != 'pending':
            return jsonify({
                'success': False,
                'error': 'Only pending trades can be modified',
                'code': 'TRADE_NOT_MODIFIABLE'
            }), 400
        
        # Update allowed fields
        if 'quantity' in data:
            if not isinstance(data['quantity'], int) or data['quantity'] <= 0:
                return jsonify({
                    'success': False,
                    'error': 'Quantity must be a positive integer',
                    'code': 'INVALID_QUANTITY'
                }), 400
            trade['quantity'] = data['quantity']
        
        if 'price' in data:
            if not isinstance(data['price'], (int, float)) or data['price'] <= 0:
                return jsonify({
                    'success': False,
                    'error': 'Price must be a positive number',
                    'code': 'INVALID_PRICE'
                }), 400
            trade['price'] = data['price']
        
        # Recalculate total value
        trade['total_value'] = trade['price'] * trade['quantity']
        trade['updated_at'] = datetime.datetime.utcnow().isoformat()
        
        logger.info(f"Trade modified: {trade_id}")
        
        return jsonify({
            'success': True,
            'message': 'Trade order modified successfully',
            'data': trade
        }), 200
        
    except Exception as e:
        logger.error(f"Modify trade error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@trade_bp.route('/list', methods=['GET'])
def list_trades():
    """
    List trades with pagination and filters
    Query params: page, limit, status, symbol
    """
    try:
        user_id = get_user_from_header()
        
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        status = request.args.get('status', '', type=str)
        symbol = request.args.get('symbol', '', type=str)
        
        # Validate pagination
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 10
        
        # Filter trades
        filtered_trades = []
        for trade in trades_db.values():
            # For demo, show all trades (in production, filter by user_id)
            match = True
            
            if status and trade.get('status') != status:
                match = False
            
            if symbol and trade.get('symbol').upper() != symbol.upper():
                match = False
            
            if match:
                filtered_trades.append(trade)
        
        # Sort by created_at descending
        filtered_trades.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Calculate pagination
        total = len(filtered_trades)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        paginated_trades = filtered_trades[start_idx:end_idx]
        
        logger.info(f"Trades list retrieved: page={page}, limit={limit}, total={total}")
        
        return jsonify({
            'success': True,
            'data': {
                'trades': paginated_trades,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'total_pages': (total + limit - 1) // limit
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"List trades error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@trade_bp.route('/<trade_id>', methods=['GET'])
def get_trade(trade_id):
    """
    Get a specific trade by ID
    """
    try:
        trade = trades_db.get(trade_id)
        
        if not trade:
            return jsonify({
                'success': False,
                'error': 'Trade not found',
                'code': 'TRADE_NOT_FOUND'
            }), 404
        
        logger.info(f"Trade retrieved: {trade_id}")
        
        return jsonify({
            'success': True,
            'data': trade
        }), 200
        
    except Exception as e:
        logger.error(f"Get trade error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@trade_bp.route('/close/<trade_id>', methods=['POST'])
def close_trade(trade_id):
    """
    Close/cancel a pending trade
    """
    try:
        trade = trades_db.get(trade_id)
        
        if not trade:
            return jsonify({
                'success': False,
                'error': 'Trade not found',
                'code': 'TRADE_NOT_FOUND'
            }), 404
        
        if trade['status'] != 'pending':
            return jsonify({
                'success': False,
                'error': 'Only pending trades can be closed',
                'code': 'TRADE_NOT_CLOSABLE'
            }), 400
        
        trade['status'] = 'cancelled'
        trade['closed_at'] = datetime.datetime.utcnow().isoformat()
        
        logger.info(f"Trade closed: {trade_id}")
        
        return jsonify({
            'success': True,
            'message': 'Trade closed successfully',
            'data': trade
        }), 200
        
    except Exception as e:
        logger.error(f"Close trade error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
