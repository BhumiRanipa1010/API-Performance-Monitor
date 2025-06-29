from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
import requests
import json
import time
import threading
from datetime import datetime, timedelta
import statistics
from contextlib import contextmanager
import os
import logging

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE = 'api_monitor.db'

# Global monitoring state
monitoring_active = False
monitoring_threads = {}

# Database helper functions
@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """Initialize the database with required tables"""
    with get_db_connection() as conn:
        # API Endpoints table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS api_endpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                headers TEXT,
                body TEXT,
                expected_status INTEGER DEFAULT 200,
                check_interval INTEGER DEFAULT 60,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # API Metrics table (for detailed monitoring data)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS api_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id INTEGER,
                response_time REAL,
                status_code INTEGER,
                success BOOLEAN,
                error_message TEXT,
                response_size INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (endpoint_id) REFERENCES api_endpoints (id)
            )
        ''')
        
        # Performance summary table (for Grafana)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS performance_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id INTEGER,
                endpoint_name TEXT,
                avg_response_time REAL,
                min_response_time REAL,
                max_response_time REAL,
                success_rate REAL,
                total_requests INTEGER,
                successful_requests INTEGER,
                failed_requests INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (endpoint_id) REFERENCES api_endpoints (id)
            )
        ''')
        
        conn.commit()

class APIMonitor:
    """API monitoring class to handle individual endpoint monitoring"""
    
    def __init__(self, endpoint_id, name, url, method='GET', headers=None, body=None, 
                 expected_status=200, check_interval=60):
        self.endpoint_id = endpoint_id
        self.name = name
        self.url = url
        self.method = method.upper()
        self.headers = json.loads(headers) if headers else {}
        self.body = body
        self.expected_status = expected_status
        self.check_interval = check_interval
        self.running = False
        
    def start_monitoring(self):
        """Start monitoring this endpoint"""
        self.running = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        logger.info(f"Started monitoring {self.name}")
        
    def stop_monitoring(self):
        """Stop monitoring this endpoint"""
        self.running = False
        logger.info(f"Stopped monitoring {self.name}")
        
    def _monitor_loop(self):
        """Main monitoring loop for this endpoint"""
        while self.running:
            try:
                self._perform_check()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop for {self.name}: {str(e)}")
                time.sleep(self.check_interval)
                
    def _perform_check(self):
        """Perform a single API check"""
        start_time = time.time()
        success = False
        status_code = None
        error_message = None
        response_size = 0
        
        try:
            # Prepare request
            request_kwargs = {
                'timeout': 30,
                'headers': self.headers
            }
            
            if self.body and self.method in ['POST', 'PUT', 'PATCH']:
                request_kwargs['data'] = self.body
                
            # Make the request
            response = requests.request(self.method, self.url, **request_kwargs)
            
            # Calculate metrics
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            status_code = response.status_code
            response_size = len(response.content)
            
            # Determine success
            success = status_code == self.expected_status
            
            if not success:
                error_message = f"Expected status {self.expected_status}, got {status_code}"
                
        except requests.exceptions.Timeout:
            response_time = (time.time() - start_time) * 1000
            error_message = "Request timeout"
        except requests.exceptions.ConnectionError:
            response_time = (time.time() - start_time) * 1000
            error_message = "Connection error"
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            error_message = str(e)
            
        # Store the result
        self._store_result(response_time, status_code, success, error_message, response_size)
        
    def _store_result(self, response_time, status_code, success, error_message, response_size):
        """Store monitoring result in database"""
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO api_metrics 
                (endpoint_id, response_time, status_code, success, error_message, response_size)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (self.endpoint_id, response_time, status_code, success, error_message, response_size))
            conn.commit()
            
        # Update performance summary
        self._update_performance_summary()
        
    def _update_performance_summary(self):
        """Update performance summary for this endpoint"""
        with get_db_connection() as conn:
            # Get metrics from last 24 hours
            yesterday = datetime.now() - timedelta(days=1)
            
            result = conn.execute('''
                SELECT 
                    AVG(response_time) as avg_response_time,
                    MIN(response_time) as min_response_time,
                    MAX(response_time) as max_response_time,
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests
                FROM api_metrics 
                WHERE endpoint_id = ? AND timestamp > ?
            ''', (self.endpoint_id, yesterday)).fetchone()
            
            if result and result['total_requests'] > 0:
                success_rate = (result['successful_requests'] / result['total_requests']) * 100
                
                # Update or insert summary
                conn.execute('''
                    INSERT OR REPLACE INTO performance_summary 
                    (endpoint_id, endpoint_name, avg_response_time, min_response_time, 
                     max_response_time, success_rate, total_requests, successful_requests, 
                     failed_requests, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (self.endpoint_id, self.name, result['avg_response_time'],
                      result['min_response_time'], result['max_response_time'],
                      success_rate, result['total_requests'], 
                      result['successful_requests'], result['failed_requests']))
                conn.commit()

# Flask Routes
@app.route('/')
def dashboard():
    """Main dashboard page"""
    with get_db_connection() as conn:
        endpoints = conn.execute('SELECT * FROM api_endpoints ORDER BY name').fetchall()
        
        # Get recent metrics for each endpoint
        endpoint_data = []
        for endpoint in endpoints:
            recent_metrics = conn.execute('''
                SELECT * FROM api_metrics 
                WHERE endpoint_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (endpoint['id'],)).fetchone()
            
            performance = conn.execute('''
                SELECT * FROM performance_summary 
                WHERE endpoint_id = ?
            ''', (endpoint['id'],)).fetchone()
            
            endpoint_data.append({
                'endpoint': dict(endpoint),
                'recent_metric': dict(recent_metrics) if recent_metrics else None,
                'performance': dict(performance) if performance else None
            })
    
    return render_template('dashboard.html', endpoint_data=endpoint_data, 
                         monitoring_active=monitoring_active)

@app.route('/add_endpoint', methods=['POST'])
def add_endpoint():
    """Add a new API endpoint to monitor"""
    data = request.get_json()
    
    required_fields = ['name', 'url']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO api_endpoints 
                (name, url, method, headers, body, expected_status, check_interval)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['name'],
                data['url'],
                data.get('method', 'GET'),
                json.dumps(data.get('headers', {})),
                data.get('body'),
                data.get('expected_status', 200),
                data.get('check_interval', 60)
            ))
            conn.commit()
            
        return jsonify({'message': 'Endpoint added successfully'}), 201
        
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Endpoint name already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/start_monitoring', methods=['POST'])
def start_monitoring():
    """Start monitoring all active endpoints"""
    global monitoring_active, monitoring_threads
    
    if monitoring_active:
        return jsonify({'message': 'Monitoring already active'}), 200
    
    try:
        with get_db_connection() as conn:
            endpoints = conn.execute('''
                SELECT * FROM api_endpoints WHERE active = 1
            ''').fetchall()
        
        monitoring_active = True
        monitoring_threads = {}
        
        for endpoint in endpoints:
            monitor = APIMonitor(
                endpoint['id'],
                endpoint['name'],
                endpoint['url'],
                endpoint['method'],
                endpoint['headers'],
                endpoint['body'],
                endpoint['expected_status'],
                endpoint['check_interval']
            )
            monitor.start_monitoring()
            monitoring_threads[endpoint['id']] = monitor
            
        return jsonify({'message': f'Started monitoring {len(endpoints)} endpoints'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stop_monitoring', methods=['POST'])
def stop_monitoring():
    """Stop all monitoring"""
    global monitoring_active, monitoring_threads
    
    monitoring_active = False
    
    for monitor in monitoring_threads.values():
        monitor.stop_monitoring()
    
    monitoring_threads = {}
    
    return jsonify({'message': 'Monitoring stopped'}), 200

@app.route('/api/metrics/<int:endpoint_id>')
def get_metrics(endpoint_id):
    """Get metrics for specific endpoint (for AJAX/API calls)"""
    hours = request.args.get('hours', 24, type=int)
    since = datetime.now() - timedelta(hours=hours)
    
    with get_db_connection() as conn:
        metrics = conn.execute('''
            SELECT * FROM api_metrics 
            WHERE endpoint_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
        ''', (endpoint_id, since)).fetchall()
        
    return jsonify([dict(metric) for metric in metrics])

@app.route('/api/performance_summary')
def performance_summary():
    """Get performance summary for all endpoints (Grafana-ready)"""
    with get_db_connection() as conn:
        summary = conn.execute('''
            SELECT * FROM performance_summary 
            ORDER BY endpoint_name
        ''').fetchall()
        
    return jsonify([dict(row) for row in summary])

@app.route('/delete_endpoint/<int:endpoint_id>', methods=['POST'])
def delete_endpoint(endpoint_id):
    """Delete an endpoint and its metrics"""
    try:
        with get_db_connection() as conn:
            # Stop monitoring if active
            if endpoint_id in monitoring_threads:
                monitoring_threads[endpoint_id].stop_monitoring()
                del monitoring_threads[endpoint_id]
            
            # Delete from database
            conn.execute('DELETE FROM api_metrics WHERE endpoint_id = ?', (endpoint_id,))
            conn.execute('DELETE FROM performance_summary WHERE endpoint_id = ?', (endpoint_id,))
            conn.execute('DELETE FROM api_endpoints WHERE id = ?', (endpoint_id,))
            conn.commit()
            
        return jsonify({'message': 'Endpoint deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Grafana Integration Endpoints
@app.route('/grafana/search', methods=['POST', 'GET'])
def grafana_search():
    """Grafana data source search endpoint"""
    with get_db_connection() as conn:
        endpoints = conn.execute('SELECT name FROM api_endpoints').fetchall()
    
    metrics = ['response_time', 'success_rate', 'request_count']
    targets = []
    
    for endpoint in endpoints:
        for metric in metrics:
            targets.append(f"{endpoint['name']}.{metric}")
    
    return jsonify(targets)

@app.route('/grafana/query', methods=['POST'])
def grafana_query():
    """Grafana data source query endpoint"""
    data = request.get_json()
    
    # This is a simplified version - in production, you'd implement
    # proper Grafana JSON datasource protocol
    results = []
    
    for target in data.get('targets', []):
        if target.get('hide'):
            continue
            
        # Parse target (endpoint.metric format)
        parts = target['target'].split('.')
        if len(parts) != 2:
            continue
            
        endpoint_name, metric = parts
        
        with get_db_connection() as conn:
            if metric == 'response_time':
                query_data = conn.execute('''
                    SELECT timestamp, response_time 
                    FROM api_metrics m
                    JOIN api_endpoints e ON m.endpoint_id = e.id
                    WHERE e.name = ? AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp
                ''', (endpoint_name, data['range']['from'], data['range']['to'])).fetchall()
                
                datapoints = [[row['response_time'], 
                             int(datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')).timestamp() * 1000)]
                            for row in query_data]
                
            results.append({
                'target': target['target'],
                'datapoints': datapoints
            })
    
    return jsonify(results)

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Add sample data for testing
    with get_db_connection() as conn:
        # Check if we have any endpoints
        count = conn.execute('SELECT COUNT(*) as count FROM api_endpoints').fetchone()['count']
        
        if count == 0:
            # Add sample endpoints
            sample_endpoints = [
                ('JSONPlaceholder Posts', 'https://jsonplaceholder.typicode.com/posts', 'GET', '{}', None, 200, 30),
                ('GitHub API', 'https://api.github.com/users/octocat', 'GET', '{}', None, 200, 60),
                ('HTTPBin Status', 'https://httpbin.org/status/200', 'GET', '{}', None, 200, 45)
            ]
            
            for endpoint in sample_endpoints:
                conn.execute('''
                    INSERT INTO api_endpoints 
                    (name, url, method, headers, body, expected_status, check_interval)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', endpoint)
            conn.commit()
            print("Added sample endpoints for testing")
    
    print("🚀 API Performance Monitor starting...")
    print("📊 Dashboard: http://localhost:5000")
    print("📈 Grafana API: http://localhost:5000/grafana/")
    print("🔍 Performance API: http://localhost:5000/api/performance_summary")
    
    app.run(debug=True, host='0.0.0.0', port=5000)