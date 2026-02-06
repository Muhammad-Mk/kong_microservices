"""
Position management routes for Trade Service
"""
import datetime
import logging
from flask import request, jsonify
from . import position_bp

logger = logging.getLogger(__name__)

# In-memory positions store (use database in production)
positions_db = {
    'pos-001': {
        'id': 'pos-001',
        'user_id': 'user-001',
        'symbol': 'AAPL',
        'quantity': 100,
        'avg_price': 175.50,
        'current_price': 178.25,
        'total_value': 17825.00,
        'profit_loss': 275.00,
        'profit_loss_percent': 1.57,
        'updated_at': '2024-01-16T12:00:00Z'
    },
    'pos-002': {
        'id': 'pos-002',
        'user_id': 'user-001',
        'symbol': 'GOOGL',
        'quantity': 50,
        'avg_price': 142.25,
        'current_price': 145.00,
        'total_value': 7250.00,
        'profit_loss': 137.50,
        'profit_loss_percent': 1.93,
        'updated_at': '2024-01-16T12:00:00Z'
    }
}


def get_user_from_header():
    """Extract user ID from Kong-forwarded header"""
    user_id = request.headers.get('X-Consumer-Custom-ID')
    username = request.headers.get('X-Consumer-Username')
    return user_id or username or 'user-001'


@position_bp.route('/list', methods=['GET'])
def list_positions():
    """
    List all positions for the current user
    """
    try:
        user_id = get_user_from_header()
        
        # Filter positions by user (for demo, return all)
        user_positions = list(positions_db.values())
        
        # Calculate totals
        total_value = sum(p['total_value'] for p in user_positions)
        total_profit_loss = sum(p['profit_loss'] for p in user_positions)
        
        logger.info(f"Positions list retrieved for user: {user_id}")
        
        return jsonify({
            'success': True,
            'data': {
                'positions': user_positions,
                'summary': {
                    'total_positions': len(user_positions),
                    'total_value': round(total_value, 2),
                    'total_profit_loss': round(total_profit_loss, 2)
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"List positions error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@position_bp.route('/<symbol>', methods=['GET'])
def get_position(symbol):
    """
    Get position for a specific symbol
    """
    try:
        symbol = symbol.upper()
        
        # Find position by symbol
        position = None
        for pos in positions_db.values():
            if pos['symbol'] == symbol:
                position = pos
                break
        
        if not position:
            return jsonify({
                'success': False,
                'error': f'No position found for symbol {symbol}',
                'code': 'POSITION_NOT_FOUND'
            }), 404
        
        logger.info(f"Position retrieved for symbol: {symbol}")
        
        return jsonify({
            'success': True,
            'data': position
        }), 200
        
    except Exception as e:
        logger.error(f"Get position error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@position_bp.route('/summary', methods=['GET'])
def positions_summary():
    """
    Get portfolio summary
    """
    try:
        user_id = get_user_from_header()
        
        # Get all positions
        user_positions = list(positions_db.values())
        
        if not user_positions:
            return jsonify({
                'success': True,
                'data': {
                    'total_positions': 0,
                    'total_invested': 0,
                    'total_value': 0,
                    'total_profit_loss': 0,
                    'total_profit_loss_percent': 0,
                    'best_performer': None,
                    'worst_performer': None
                }
            }), 200
        
        # Calculate metrics
        total_invested = sum(p['avg_price'] * p['quantity'] for p in user_positions)
        total_value = sum(p['total_value'] for p in user_positions)
        total_profit_loss = sum(p['profit_loss'] for p in user_positions)
        total_profit_loss_percent = (total_profit_loss / total_invested * 100) if total_invested > 0 else 0
        
        # Find best and worst performers
        best = max(user_positions, key=lambda x: x['profit_loss_percent'])
        worst = min(user_positions, key=lambda x: x['profit_loss_percent'])
        
        logger.info(f"Portfolio summary retrieved for user: {user_id}")
        
        return jsonify({
            'success': True,
            'data': {
                'total_positions': len(user_positions),
                'total_invested': round(total_invested, 2),
                'total_value': round(total_value, 2),
                'total_profit_loss': round(total_profit_loss, 2),
                'total_profit_loss_percent': round(total_profit_loss_percent, 2),
                'best_performer': {
                    'symbol': best['symbol'],
                    'profit_loss_percent': best['profit_loss_percent']
                },
                'worst_performer': {
                    'symbol': worst['symbol'],
                    'profit_loss_percent': worst['profit_loss_percent']
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Portfolio summary error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500


@position_bp.route('/history', methods=['GET'])
def position_history():
    """
    Get historical position data
    Query params: symbol, days
    """
    try:
        symbol = request.args.get('symbol', '', type=str).upper()
        days = request.args.get('days', 30, type=int)
        
        # Generate mock historical data
        history = []
        base_date = datetime.datetime.utcnow()
        base_value = 17000.00
        
        for i in range(days):
            date = base_date - datetime.timedelta(days=days - i - 1)
            # Simulate some variation
            variation = (i % 7 - 3) * 50
            value = base_value + variation + (i * 10)
            
            history.append({
                'date': date.strftime('%Y-%m-%d'),
                'value': round(value, 2),
                'change': round(variation, 2)
            })
        
        logger.info(f"Position history retrieved: symbol={symbol}, days={days}")
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol or 'PORTFOLIO',
                'period_days': days,
                'history': history
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Position history error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }), 500
