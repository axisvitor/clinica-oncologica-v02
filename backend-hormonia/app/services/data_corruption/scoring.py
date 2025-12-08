"""
Scoring and Recommendations
Calculates corruption scores and generates recommendations.
"""
from typing import List, Dict, Any
from .types import CorruptionPattern, CorruptionType


class CorruptionScoring:
    """Handles corruption scoring and recommendation generation"""

    @staticmethod
    def calculate_corruption_score(patterns: List[CorruptionPattern]) -> float:
        """Calculate overall corruption score (0-100)"""
        if not patterns:
            return 0.0

        severity_weights = {
            'low': 1,
            'medium': 3,
            'high': 7,
            'critical': 15
        }

        total_score = sum(
            severity_weights.get(pattern.severity, 1) * pattern.confidence
            for pattern in patterns
        )

        # Normalize to 0-100 scale
        normalized_score = min(100.0, total_score / len(patterns) * 10)
        return round(normalized_score, 2)

    @staticmethod
    def generate_recommendations(patterns: List[CorruptionPattern]) -> List[str]:
        """Generate recommendations based on detected corruption patterns"""
        recommendations = []

        # Count patterns by type
        type_counts = {}
        for pattern in patterns:
            pattern_type = pattern.type.value
            type_counts[pattern_type] = type_counts.get(pattern_type, 0) + 1

        # Generate specific recommendations
        if type_counts.get('encoding_corruption', 0) > 0:
            recommendations.append("Review data import/export processes for encoding consistency")

        if type_counts.get('format_corruption', 0) > 0:
            recommendations.append("Implement stricter input validation for formatted fields")

        if type_counts.get('temporal_corruption', 0) > 0:
            recommendations.append("Add temporal validation constraints to prevent impossible dates")

        if type_counts.get('content_corruption', 0) > 0:
            recommendations.append("Implement content sanitization and validation")

        if type_counts.get('metadata_corruption', 0) > 0:
            recommendations.append("Add JSON schema validation for metadata fields")

        # General recommendations
        if len(patterns) > 5:
            recommendations.append("Schedule regular corruption detection scans")

        critical_patterns = [p for p in patterns if p.severity == 'critical']
        if critical_patterns:
            recommendations.append("Address critical corruption issues immediately")

        return recommendations[:5]  # Limit to top 5 recommendations

    @staticmethod
    def get_summary(patterns: List[CorruptionPattern]) -> Dict[str, Any]:
        """Get summary of detected corruption patterns"""
        return {
            'total_patterns': len(patterns),
            'by_type': {
                corruption_type.value: len([p for p in patterns if p.type == corruption_type])
                for corruption_type in CorruptionType
            },
            'by_severity': {
                severity: len([p for p in patterns if p.severity == severity])
                for severity in ['low', 'medium', 'high', 'critical']
            },
            'corruption_score': CorruptionScoring.calculate_corruption_score(patterns),
            'top_patterns': [
                {
                    'type': p.type.value,
                    'field': p.field,
                    'description': p.description,
                    'confidence': p.confidence
                }
                for p in sorted(patterns, key=lambda x: x.confidence, reverse=True)[:10]
            ]
        }
