
# Grafana Integration Setup for API Performance Monitor
# Run this script to set up Grafana dashboards and data source

import json
import requests
import time
from datetime import datetime

class GrafanaSetup:
    def __init__(self, grafana_url='http://localhost:3000', admin_user='admin', admin_password='admin'):
        self.grafana_url = grafana_url
        self.session = requests.Session()
        self.session.auth = (admin_user, admin_password)
        
    def setup_data_source(self, flask_app_url='http://localhost:5000'):
        \"\"\"Set up the Flask app as a JSON data source in Grafana\"\"\"
        
        datasource_config = {
            "name": "API Monitor",
            "type": "simpod-json-datasource",
            "url": f"{flask_app_url}/grafana",
            "access": "proxy",
            "isDefault": True,
            "jsonData": {},
            "secureJsonFields": {}
        }
        
        try:
            response = self.session.post(
                f"{self.grafana_url}/api/datasources",
                json=datasource_config,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print("✅ Data source created successfully")
                return response.json()
            else:
                print(f"❌ Failed to create data source: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error setting up data source: {str(e)}")
            return None
    
    def create_dashboard(self):
        \"\"\"Create a comprehensive API monitoring dashboard\"\"\"
        
        dashboard_config = {
            "dashboard": {
                "id": None,
                "title": "API Performance Monitor",
                "tags": ["api", "monitoring", "performance"],
                "timezone": "browser",
                "panels": [
                    {
                        "id": 1,
                        "title": "Response Time Trends",
                        "type": "graph",
                        "targets": [
                            {
                                "target": "*.response_time",
                                "refId": "A"
                            }
                        ],
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                        "xAxis": {"show": True},
                        "yAxes": [
                            {
                                "label": "Response Time (ms)",
                                "show": True
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "title": "Success Rate",
                        "type": "stat",
                        "targets": [
                            {
                                "target": "*.success_rate",
                                "refId": "B"
                            }
                        ],
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                        "options": {
                            "colorMode": "background",
                            "graphMode": "area",
                            "justifyMode": "auto",
                            "orientation": "horizontal"
                        }
                    },
                    {
                        "id": 3,
                        "title": "Request Volume",
                        "type": "graph",
                        "targets": [
                            {
                                "target": "*.request_count",
                                "refId": "C"
                            }
                        ],
                        "gridPos": {"h": 8, "w": 24, "x": 0, "y": 8}
                    }
                ],
                "time": {
                    "from": "now-6h",
                    "to": "now"
                },
                "refresh": "30s"
            },
            "overwrite": True
        }
        
        try:
            response = self.session.post(
                f"{self.grafana_url}/api/dashboards/db",
                json=dashboard_config,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                print("✅ Dashboard created successfully")
                dashboard_data = response.json()
                print(f"📊 Dashboard URL: {self.grafana_url}/d/{dashboard_data['slug']}")
                return dashboard_data
            else:
                print(f"❌ Failed to create dashboard: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating dashboard: {str(e)}")
            return None
    
    def setup_alerts(self):
        \"\"\"Set up alerting rules for API monitoring\"\"\"
        
        alert_rules = [
            {
                "alert": {
                    "name": "High Response Time",
                    "message": "API response time is above threshold",
                    "frequency": "30s",
                    "conditions": [
                        {
                            "query": {"queryType": "A", "refId": "A"},
                            "reducer": {"type": "avg", "params": []},
                            "evaluator": {"params": [1000], "type": "gt"}
                        }
                    ],
                    "executionErrorState": "alerting",
                    "noDataState": "no_data",
                    "for": "2m"
                }
            },
            {
                "alert": {
                    "name": "Low Success Rate",
                    "message": "API success rate is below threshold",
                    "frequency": "30s",
                    "conditions": [
                        {
                            "query": {"queryType": "B", "refId": "B"},
                            "reducer": {"type": "avg", "params": []},
                            "evaluator": {"params": [95], "type": "lt"}
                        }
                    ],
                    "executionErrorState": "alerting",
                    "noDataState": "no_data",
                    "for": "2m"
                }
            }
        ]
        
        print("⚠️  Alert setup would be implemented here")
        print("💡 Configure alerts through Grafana UI for full functionality")

def main():
    print("🚀 Setting up Grafana integration for API Performance Monitor...")
    
    # Wait for Grafana to be ready
    print("⏳ Waiting for Grafana to be ready...")
    time.sleep(5)
    
    setup = GrafanaSetup()
    
    # Setup data source
    print("📊 Setting up data source...")
    setup.setup_data_source()
    
    # Create dashboard
    print("📈 Creating dashboard...")
    setup.create_dashboard()
    
    # Setup alerts
    print("🚨 Setting up alerts...")
    setup.setup_alerts()
    
    print("✅ Grafana setup complete!")
    print("🌐 Access Grafana at: http://localhost:3000")
    print("👤 Default credentials: admin/admin")

if __name__ == "__main__":
    main()
