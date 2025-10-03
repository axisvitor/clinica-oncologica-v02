"""
Metrics Dashboard API

Flask blueprint for resilience metrics visualization.
"""

import time
from flask import Blueprint, jsonify, request
from .collector import metrics_collector


def create_metrics_blueprint() -> Blueprint:
    """Create metrics dashboard blueprint"""
    bp = Blueprint('metrics', __name__, url_prefix='/metrics')

    @bp.route('/', methods=['GET'])
    def get_current_metrics():
        """Get current resilience metrics"""
        try:
            current_metrics = metrics_collector.get_current_metrics()
            return jsonify({
                'status': 'success',
                'data': current_metrics.to_dict()
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @bp.route('/history', methods=['GET'])
    def get_metrics_history():
        """Get historical metrics"""
        try:
            # Get query parameters
            minutes = request.args.get('minutes', type=int)

            history = metrics_collector.get_metrics_history(last_n_minutes=minutes)

            return jsonify({
                'status': 'success',
                'data': {
                    'history': [m.to_dict() for m in history],
                    'count': len(history),
                    'time_range_minutes': minutes
                }
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @bp.route('/aggregated', methods=['GET'])
    def get_aggregated_metrics():
        """Get aggregated metrics over time period"""
        try:
            # Get query parameters
            minutes = request.args.get('minutes', type=int, default=60)

            aggregated = metrics_collector.get_aggregated_metrics(last_n_minutes=minutes)

            return jsonify({
                'status': 'success',
                'data': aggregated
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @bp.route('/export', methods=['GET'])
    def export_metrics():
        """Export metrics in various formats"""
        try:
            format_type = request.args.get('format', 'json')

            if format_type not in ['json', 'prometheus']:
                return jsonify({
                    'status': 'error',
                    'error': 'Unsupported format. Use: json, prometheus'
                }), 400

            exported_data = metrics_collector.export_metrics(format_type)

            if format_type == 'prometheus':
                # Return plain text for Prometheus
                from flask import Response
                return Response(exported_data, mimetype='text/plain')
            else:
                return jsonify({
                    'status': 'success',
                    'format': format_type,
                    'data': exported_data
                }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @bp.route('/components', methods=['GET'])
    def get_component_metrics():
        """Get metrics for individual components"""
        try:
            component_metrics = {}

            # Circuit breakers
            component_metrics['circuit_breakers'] = {}
            for name, cb in metrics_collector._circuit_breakers.items():
                try:
                    component_metrics['circuit_breakers'][name] = cb.get_metrics()
                except Exception as e:
                    component_metrics['circuit_breakers'][name] = {'error': str(e)}

            # Retry managers
            component_metrics['retry_managers'] = {}
            for name, rm in metrics_collector._retry_managers.items():
                try:
                    component_metrics['retry_managers'][name] = rm.get_metrics()
                except Exception as e:
                    component_metrics['retry_managers'][name] = {'error': str(e)}

            # Rate limiters
            component_metrics['rate_limiters'] = {}
            for name, rl in metrics_collector._rate_limiters.items():
                try:
                    component_metrics['rate_limiters'][name] = rl.get_metrics()
                except Exception as e:
                    component_metrics['rate_limiters'][name] = {'error': str(e)}

            # Health checkers
            component_metrics['health_checkers'] = {}
            for name, hc in metrics_collector._health_checkers.items():
                try:
                    component_metrics['health_checkers'][name] = hc.get_metrics()
                except Exception as e:
                    component_metrics['health_checkers'][name] = {'error': str(e)}

            return jsonify({
                'status': 'success',
                'data': component_metrics
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @bp.route('/dashboard', methods=['GET'])
    def get_dashboard_data():
        """Get comprehensive dashboard data"""
        try:
            # Get current metrics
            current = metrics_collector.get_current_metrics()

            # Get aggregated data for last hour
            aggregated_1h = metrics_collector.get_aggregated_metrics(60)

            # Get aggregated data for last 24 hours
            aggregated_24h = metrics_collector.get_aggregated_metrics(1440)

            # Calculate health scores
            circuit_breaker_health = _calculate_circuit_breaker_health(current)
            retry_health = _calculate_retry_health(current)
            rate_limit_health = _calculate_rate_limit_health(current)

            overall_health = (circuit_breaker_health + retry_health + rate_limit_health) / 3

            dashboard_data = {
                'overview': {
                    'overall_health_score': overall_health,
                    'circuit_breaker_health': circuit_breaker_health,
                    'retry_health': retry_health,
                    'rate_limit_health': rate_limit_health,
                    'uptime_hours': current.uptime_seconds / 3600,
                    'error_rate': current.error_rate,
                    'average_response_time': current.average_response_time
                },
                'current_metrics': current.to_dict(),
                'trends_1h': aggregated_1h,
                'trends_24h': aggregated_24h,
                'timestamp': time.time()
            }

            return jsonify({
                'status': 'success',
                'data': dashboard_data
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @bp.route('/alerts', methods=['GET'])
    def get_alerts():
        """Get current alerts based on thresholds"""
        try:
            current = metrics_collector.get_current_metrics()
            alerts = _generate_alerts(current)

            return jsonify({
                'status': 'success',
                'data': {
                    'alerts': alerts,
                    'alert_count': len(alerts),
                    'severity_counts': _count_alerts_by_severity(alerts)
                }
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    @bp.route('/status', methods=['GET'])
    def get_metrics_status():
        """Get metrics collection status"""
        try:
            status_info = {
                'collection_active': metrics_collector._collection_thread and metrics_collector._collection_thread.is_alive(),
                'registered_components': {
                    'circuit_breakers': len(metrics_collector._circuit_breakers),
                    'retry_managers': len(metrics_collector._retry_managers),
                    'rate_limiters': len(metrics_collector._rate_limiters),
                    'health_checkers': len(metrics_collector._health_checkers)
                },
                'history_length': len(metrics_collector._metrics_history),
                'retention_period': metrics_collector.retention_period,
                'collection_interval': metrics_collector.collection_interval,
                'uptime': time.time() - metrics_collector.start_time
            }

            return jsonify({
                'status': 'success',
                'data': status_info
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500

    return bp


def _calculate_circuit_breaker_health(metrics) -> float:
    """Calculate circuit breaker health score (0-100)"""
    total_requests = metrics.circuit_breaker_successes + metrics.circuit_breaker_failures

    if total_requests == 0:
        return 100.0

    success_rate = metrics.circuit_breaker_successes / total_requests

    # Penalize for trips
    trip_penalty = min(metrics.circuit_breaker_trips * 10, 50)

    health_score = (success_rate * 100) - trip_penalty
    return max(0.0, min(100.0, health_score))


def _calculate_retry_health(metrics) -> float:
    """Calculate retry health score (0-100)"""
    total_executions = metrics.retry_successes + metrics.retry_failures

    if total_executions == 0:
        return 100.0

    success_rate = metrics.retry_successes / total_executions

    # Penalize for dead letters
    dead_letter_penalty = min(metrics.retry_dead_letters * 5, 30)

    health_score = (success_rate * 100) - dead_letter_penalty
    return max(0.0, min(100.0, health_score))


def _calculate_rate_limit_health(metrics) -> float:
    """Calculate rate limiting health score (0-100)"""
    total_requests = metrics.rate_limit_allowed + metrics.rate_limit_denied

    if total_requests == 0:
        return 100.0

    # Lower denial rate is better
    denial_rate = metrics.rate_limit_denied / total_requests
    health_score = (1 - denial_rate) * 100

    return max(0.0, min(100.0, health_score))


def _generate_alerts(metrics) -> list:
    """Generate alerts based on metric thresholds"""
    alerts = []

    # High error rate alert
    if metrics.error_rate > 0.1:  # 10%
        alerts.append({
            'type': 'high_error_rate',
            'severity': 'critical' if metrics.error_rate > 0.2 else 'warning',
            'message': f'High error rate: {metrics.error_rate:.1%}',
            'value': metrics.error_rate,
            'threshold': 0.1
        })

    # High response time alert
    if metrics.average_response_time > 2.0:  # 2 seconds
        alerts.append({
            'type': 'high_response_time',
            'severity': 'critical' if metrics.average_response_time > 5.0 else 'warning',
            'message': f'High response time: {metrics.average_response_time:.2f}s',
            'value': metrics.average_response_time,
            'threshold': 2.0
        })

    # Circuit breaker trips alert
    if metrics.circuit_breaker_trips > 0:
        alerts.append({
            'type': 'circuit_breaker_trips',
            'severity': 'warning',
            'message': f'Circuit breaker trips detected: {metrics.circuit_breaker_trips}',
            'value': metrics.circuit_breaker_trips,
            'threshold': 0
        })

    # Dead letter queue alert
    if metrics.retry_dead_letters > 0:
        alerts.append({
            'type': 'dead_letter_queue',
            'severity': 'warning',
            'message': f'Items in dead letter queue: {metrics.retry_dead_letters}',
            'value': metrics.retry_dead_letters,
            'threshold': 0
        })

    # High memory usage alert
    if metrics.memory_usage_mb > 1000:  # 1GB
        alerts.append({
            'type': 'high_memory_usage',
            'severity': 'critical' if metrics.memory_usage_mb > 2000 else 'warning',
            'message': f'High memory usage: {metrics.memory_usage_mb:.0f}MB',
            'value': metrics.memory_usage_mb,
            'threshold': 1000
        })

    # High CPU usage alert
    if metrics.cpu_usage_percent > 80:
        alerts.append({
            'type': 'high_cpu_usage',
            'severity': 'critical' if metrics.cpu_usage_percent > 95 else 'warning',
            'message': f'High CPU usage: {metrics.cpu_usage_percent:.1f}%',
            'value': metrics.cpu_usage_percent,
            'threshold': 80
        })

    return alerts


def _count_alerts_by_severity(alerts) -> dict:
    """Count alerts by severity level"""
    counts = {'critical': 0, 'warning': 0, 'info': 0}

    for alert in alerts:
        severity = alert.get('severity', 'info')
        counts[severity] = counts.get(severity, 0) + 1

    return counts