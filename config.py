
# Configuration file for API Performance Monitor

import os

class Config:
    # Database configuration
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'api_monitor.db')
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Monitoring configuration
    DEFAULT_CHECK_INTERVAL = int(os.environ.get('DEFAULT_CHECK_INTERVAL', '60'))
    MAX_CONCURRENT_MONITORS = int(os.environ.get('MAX_CONCURRENT_MONITORS', '10'))
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', '30'))
    
    # Grafana configuration
    GRAFANA_ENABLED = os.environ.get('GRAFANA_ENABLED', 'True').lower() == 'true'
    GRAFANA_PORT = int(os.environ.get('GRAFANA_PORT', '3000'))
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'api_monitor.log')
