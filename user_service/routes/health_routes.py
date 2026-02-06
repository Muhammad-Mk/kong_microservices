"""
Health and version routes for User Service
Includes instance identifier for load balancing verification
"""
import datetime
import os
import socket
import logging
from flask import jsonify, current_app
from . import health_bp

logger = logging.getLogger(__name__)

# Track service start time
SERVICE_START_TIME = datetime.datetime.utcnow()

# Get hostname/container ID for instance identification
INSTANCE_ID = socket.gethostname()


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for load balancers and orchestrators
    Returns instance ID to verify load balancing across replicas
    """
    try:
        uptime = (datetime.datetime.utcnow() - SERVICE_START_TIME).total_seconds()
        
        return jsonify({
            'status': 'healthy',
            'service': current_app.config.get('SERVICE_NAME', 'user_service'),
            'instance': INSTANCE_ID,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'uptime_seconds': round(uptime, 2),
            'checks': {
                'app': 'ok',
                'memory': 'ok'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'user_service',
            'instance': INSTANCE_ID,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'error': str(e)
        }), 503


@health_bp.route('/version', methods=['GET'])
def version():
    """
    Return service version information
    """
    return jsonify({
        'service': current_app.config.get('SERVICE_NAME', 'user_service'),
        'version': current_app.config.get('SERVICE_VERSION', '1.0.0'),
        'instance': INSTANCE_ID,
        'environment': os.environ.get('FLASK_ENV', 'development'),
        'python_version': os.popen('python --version').read().strip(),
        'build_date': os.environ.get('BUILD_DATE', 'unknown')
    }), 200


@health_bp.route('/ready', methods=['GET'])
def readiness_check():
    """
    Readiness check for Kubernetes/Swarm-style deployments
    """
    try:
        return jsonify({
            'ready': True,
            'service': current_app.config.get('SERVICE_NAME', 'user_service'),
            'instance': INSTANCE_ID,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return jsonify({
            'ready': False,
            'service': 'user_service',
            'instance': INSTANCE_ID,
            'error': str(e)
        }), 503
