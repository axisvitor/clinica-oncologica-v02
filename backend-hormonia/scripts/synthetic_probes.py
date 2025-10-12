#!/usr/bin/env python3
"""
Synthetic Monitoring Probes
Tests critical endpoints to ensure production health.
"""
import requests
import time
import json
import sys
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

class SyntheticProbe:
    def __init__(self, base_url: str, auth_token: str = None):
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.session = requests.Session()
        if auth_token:
            self.session.headers.update({'Authorization': f'Bearer {auth_token}'})
    
    def probe_endpoint(self, endpoint: str, method: str = 'GET', 
                      expected_status: int = 200, timeout: int = 10) -> Dict:
        """Probe a single endpoint and return metrics."""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method == 'GET':
                response = self.session.get(url, timeout=timeout)
            elif method == 'POST':
                response = self.session.post(url, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            return {
                'endpoint': endpoint,
                'status_code': response.status_code,
                'latency_ms': round(latency_ms, 2),
                'success': response.status_code == expected_status,
                'response_size': len(response.content),
                'timestamp': datetime.now().isoformat(),
                'error': None
            }
            
        except requests.exceptions.Timeout:
            return {
                'endpoint': endpoint,
                'status_code': 0,
                'latency_ms': timeout * 1000,
                'success': False,
                'response_size': 0,
                'timestamp': datetime.now().isoformat(),
                'error': 'Timeout'
            }
        except Exception as e:
            return {
                'endpoint': endpoint,
                'status_code': 0,
                'latency_ms': 0,
                'success': False,
                'response_size': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

def run_critical_probes(base_url: str, auth_token: str = None) -> List[Dict]:
    """Run probes on critical endpoints."""
    probe = SyntheticProbe(base_url, auth_token)
    
    # Critical endpoints to monitor
    endpoints = [
        # Health and monitoring
        ('/api/v1/monitoring/health', 'GET', 200),
        ('/api/v1/monitoring/database-health', 'GET', 200),
        ('/api/v1/monitoring/error-summary', 'GET', 200),
        
        # Analytics endpoints (date parameter handling)
        ('/api/v1/analytics/engagement-range?start_date=2025-01-01&end_date=2025-01-12', 'GET', 200),
        
        # Monthly quiz endpoints (role-based access)
        ('/api/v1/monthly-quiz/active-quiz-links', 'GET', 200),
        
        # Quiz alerts endpoints (schema compatibility)
        ('/api/v1/quiz-alerts/critical', 'GET', 200),
        
        # Authentication health
        ('/api/v1/auth/health', 'GET', 200),
    ]
    
    results = []
    print("🔍 Running Synthetic Probes...")
    print("=" * 50)
    
    for endpoint, method, expected_status in endpoints:
        result = probe.probe_endpoint(endpoint, method, expected_status)
        results.append(result)
        
        # Display result
        status_icon = "✅" if result['success'] else "❌"
        latency_color = "🟢" if result['latency_ms'] < 500 else "🟡" if result['latency_ms'] < 2000 else "🔴"
        
        print(f"{status_icon} {endpoint}")
        print(f"   Status: {result['status_code']} | Latency: {latency_color} {result['latency_ms']}ms")
        if result['error']:
            print(f"   Error: {result['error']}")
        print()
    
    return results

def analyze_results(results: List[Dict]) -> Dict:
    """Analyze probe results and generate summary."""
    total_probes = len(results)
    successful_probes = sum(1 for r in results if r['success'])
    failed_probes = total_probes - successful_probes
    
    latencies = [r['latency_ms'] for r in results if r['success']]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    
    # SLA calculations
    availability = (successful_probes / total_probes) * 100 if total_probes > 0 else 0
    performance_sla = sum(1 for l in latencies if l < 2000) / len(latencies) * 100 if latencies else 0
    
    return {
        'total_probes': total_probes,
        'successful_probes': successful_probes,
        'failed_probes': failed_probes,
        'availability_percent': round(availability, 2),
        'avg_latency_ms': round(avg_latency, 2),
        'max_latency_ms': round(max_latency, 2),
        'performance_sla_percent': round(performance_sla, 2),
        'timestamp': datetime.now().isoformat()
    }

def main():
    """Main synthetic monitoring function."""
    print("🎯 SYNTHETIC MONITORING PROBES")
    print("=" * 50)
    
    # Configuration
    base_url = "https://clinica-oncologica-v02-production.up.railway.app"
    auth_token = None  # Add if authentication required
    
    # Run probes
    results = run_critical_probes(base_url, auth_token)
    
    # Analyze results
    summary = analyze_results(results)
    
    print("📊 PROBE SUMMARY")
    print("=" * 50)
    print(f"Total Probes: {summary['total_probes']}")
    print(f"Successful: {summary['successful_probes']} ✅")
    print(f"Failed: {summary['failed_probes']} ❌")
    print(f"Availability: {summary['availability_percent']}%")
    print(f"Average Latency: {summary['avg_latency_ms']}ms")
    print(f"Max Latency: {summary['max_latency_ms']}ms")
    print(f"Performance SLA: {summary['performance_sla_percent']}% (< 2s)")
    
    # SLA Thresholds
    print("\n🎯 SLA STATUS")
    print("=" * 50)
    
    sla_checks = [
        ("Availability > 99%", summary['availability_percent'] > 99),
        ("Average Latency < 500ms", summary['avg_latency_ms'] < 500),
        ("Performance SLA > 95%", summary['performance_sla_percent'] > 95),
        ("No Critical Failures", summary['failed_probes'] == 0)
    ]
    
    all_sla_met = True
    for check_name, passed in sla_checks:
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}")
        if not passed:
            all_sla_met = False
    
    print("\n" + "=" * 50)
    if all_sla_met:
        print("🎉 ALL SLA TARGETS MET!")
        print("   System performing within acceptable parameters")
        return 0
    else:
        print("⚠️  SLA TARGETS NOT MET!")
        print("   Review failed probes and performance issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())