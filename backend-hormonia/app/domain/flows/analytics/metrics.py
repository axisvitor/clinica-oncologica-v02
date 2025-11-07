"""
Analytics Metrics Module - Flow Metrics Computation

Computes metrics and statistics for flow execution.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List


logger = logging.getLogger(__name__)


class FlowMetricsCalculator:
    """
    Calculates flow execution metrics.

    Responsibilities:
    - Compute flow performance metrics
    - Calculate success rates
    - Track timing statistics
    - Generate summary reports
    """

    def __init__(self):
        """Initialize FlowMetricsCalculator."""
        logger.info("FlowMetricsCalculator initialized")

    def calculate_batch_metrics(
        self,
        processed_count: int,
        successful_count: int,
        failed_count: int,
        skipped_count: int,
        processing_time: float
    ) -> Dict[str, Any]:
        """
        Calculate metrics for batch processing.

        Args:
            processed_count: Number of processed items
            successful_count: Number of successful operations
            failed_count: Number of failed operations
            skipped_count: Number of skipped operations
            processing_time: Total processing time in seconds

        Returns:
            Metrics dictionary
        """
        total_operations = successful_count + failed_count + skipped_count

        metrics = {
            'processed_patients': processed_count,
            'successful_operations': successful_count,
            'failed_operations': failed_count,
            'skipped_operations': skipped_count,
            'total_operations': total_operations,
            'processing_time_seconds': processing_time,
            'success_rate': (successful_count / total_operations * 100) if total_operations > 0 else 0,
            'failure_rate': (failed_count / total_operations * 100) if total_operations > 0 else 0,
            'avg_time_per_operation': (processing_time / total_operations) if total_operations > 0 else 0
        }

        logger.debug(f"Batch metrics calculated: {metrics}")
        return metrics

    def calculate_health_percentage(
        self,
        healthy_components: int,
        total_components: int
    ) -> float:
        """
        Calculate health percentage.

        Args:
            healthy_components: Number of healthy components
            total_components: Total number of components

        Returns:
            Health percentage
        """
        if total_components == 0:
            return 0.0

        percentage = (healthy_components / total_components) * 100
        logger.debug(f"Health percentage: {percentage:.1f}%")
        return percentage

    def aggregate_processing_results(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate multiple processing results.

        Args:
            results: List of processing result dictionaries

        Returns:
            Aggregated results
        """
        aggregated = {
            'total_operations': len(results),
            'successful': sum(1 for r in results if r.get('status') == 'success'),
            'failed': sum(1 for r in results if r.get('status') == 'error'),
            'skipped': sum(1 for r in results if r.get('status') == 'skipped'),
            'quiz_triggers': sum(1 for r in results if r.get('quiz_triggered', False)),
            'messages_scheduled': sum(r.get('messages_scheduled', 0) for r in results)
        }

        aggregated['success_rate'] = (
            aggregated['successful'] / aggregated['total_operations'] * 100
            if aggregated['total_operations'] > 0 else 0
        )

        logger.debug(f"Aggregated results: {aggregated}")
        return aggregated
