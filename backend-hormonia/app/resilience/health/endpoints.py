"""
Health Check API Endpoints

Flask blueprint for health monitoring endpoints.
"""

import asyncio
from flask import Blueprint, jsonify
from ..health.checker import health_checker


def create_health_blueprint() -> Blueprint:
    """Create health check blueprint"""
    bp = Blueprint("health", __name__, url_prefix="/health")

    @bp.route("/", methods=["GET"])
    def health_status():
        """
        Main health endpoint

        Returns overall health status and summary of all checks
        """
        try:
            # Run async health check in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(health_checker.check_health())
            finally:
                loop.close()

            # Determine HTTP status code
            summary = result.get("summary", {})
            status_value = summary.get("status", "unknown")

            if status_value == "healthy":
                status_code = 200
            elif status_value == "degraded":
                status_code = 200  # Still operational
            else:
                status_code = 503  # Service unavailable

            return jsonify(result), status_code

        except Exception as e:
            return jsonify(
                {
                    "error": f"Health check failed: {str(e)}",
                    "summary": {"status": "unhealthy", "health_percentage": 0.0},
                }
            ), 503

    @bp.route("/live", methods=["GET"])
    def liveness_probe():
        """
        Kubernetes liveness probe endpoint

        Simple endpoint that returns 200 if service is running
        """
        return jsonify({"status": "alive", "timestamp": time.time()}), 200

    @bp.route("/ready", methods=["GET"])
    def readiness_probe():
        """
        Kubernetes readiness probe endpoint

        Returns 200 only if service is ready to handle requests
        """
        try:
            # Run health checks
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(health_checker.check_health())
            finally:
                loop.close()

            summary = result.get("summary", {})
            status_value = summary.get("status", "unknown")

            # Only ready if healthy or degraded
            if status_value in ["healthy", "degraded"]:
                return jsonify(
                    {
                        "status": "ready",
                        "health_status": status_value,
                        "health_percentage": summary.get("health_percentage", 0.0),
                    }
                ), 200
            else:
                return jsonify(
                    {
                        "status": "not_ready",
                        "health_status": status_value,
                        "health_percentage": summary.get("health_percentage", 0.0),
                    }
                ), 503

        except Exception as e:
            return jsonify({"status": "not_ready", "error": str(e)}), 503

    @bp.route("/check/<check_name>", methods=["GET"])
    def specific_health_check(check_name: str):
        """
        Specific health check endpoint

        Returns result for a specific health check
        """
        try:
            # Run specific health check
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    health_checker.check_health(check_name)
                )
            finally:
                loop.close()

            if "error" in result:
                return jsonify(result), 404

            # Determine status code from check result
            check_result = result.get("checks", {}).get(check_name, {})
            status_value = check_result.get("status", "unknown")

            if status_value == "healthy":
                status_code = 200
            elif status_value == "degraded":
                status_code = 200
            else:
                status_code = 503

            return jsonify(result), status_code

        except Exception as e:
            return jsonify(
                {"error": f"Health check failed: {str(e)}", "check_name": check_name}
            ), 503

    @bp.route("/checks", methods=["GET"])
    def list_health_checks():
        """
        List all available health checks
        """
        try:
            checks = health_checker.get_check_names()
            metrics = health_checker.get_metrics()

            return jsonify(
                {
                    "available_checks": checks,
                    "total_checks": len(checks),
                    "metrics": metrics,
                }
            ), 200

        except Exception as e:
            return jsonify({"error": f"Failed to list health checks: {str(e)}"}), 500

    @bp.route("/metrics", methods=["GET"])
    def health_metrics():
        """
        Health check metrics endpoint
        """
        try:
            metrics = health_checker.get_metrics()

            return jsonify({"metrics": metrics, "timestamp": time.time()}), 200

        except Exception as e:
            return jsonify({"error": f"Failed to get metrics: {str(e)}"}), 500

    @bp.route("/cache", methods=["DELETE"])
    def clear_health_cache():
        """
        Clear health check cache
        """
        try:
            health_checker.clear_cache()

            return jsonify(
                {"message": "Health check cache cleared", "timestamp": time.time()}
            ), 200

        except Exception as e:
            return jsonify({"error": f"Failed to clear cache: {str(e)}"}), 500

    return bp


import time
