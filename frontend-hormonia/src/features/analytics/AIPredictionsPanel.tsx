/**
 * AI Predictions Panel Component
 * Displays AI-powered patient predictions with interpretability
 */

import React, { useState } from 'react';
import { Prediction, PredictionFactor } from '../../types/enhanced-analytics';

export interface AIPredictionsPanelProps {
  predictions: Prediction[];
  onRefresh?: (patientId: string) => void;
  loading?: boolean;
}

const predictionTypeLabels: Record<string, string> = {
  risk: 'Risk Assessment',
  adherence: 'Treatment Adherence',
  success: 'Treatment Success',
  outcome: 'Patient Outcome',
};

const predictionTypeColors: Record<string, string> = {
  risk: 'red',
  adherence: 'blue',
  success: 'green',
  outcome: 'purple',
};

export const AIPredictionsPanel: React.FC<AIPredictionsPanelProps> = ({
  predictions,
  onRefresh,
  loading = false,
}) => {
  const [expandedPrediction, setExpandedPrediction] = useState<string | null>(null);

  const toggleExpanded = (patientId: string) => {
    setExpandedPrediction(expandedPrediction === patientId ? null : patientId);
  };

  const getValueColor = (value: number, predictionType: string) => {
    if (predictionType === 'risk') {
      if (value >= 0.7) return 'text-red-600';
      if (value >= 0.4) return 'text-orange-600';
      return 'text-green-600';
    }
    if (predictionType === 'success' || predictionType === 'adherence') {
      if (value >= 0.7) return 'text-green-600';
      if (value >= 0.4) return 'text-orange-600';
      return 'text-red-600';
    }
    return 'text-gray-600';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return 'High';
    if (confidence >= 0.6) return 'Medium';
    return 'Low';
  };

  const renderFactorImpact = (factor: PredictionFactor) => {
    const impactPercentage = Math.abs(factor.impact) * 100;
    const isPositive = factor.impact > 0;

    return (
      <div className="mb-3 last:mb-0">
        <div className="flex justify-between items-start mb-1">
          <span className="text-sm font-medium text-gray-700">{factor.name}</span>
          <span className={`text-sm font-semibold ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
            {isPositive ? '+' : '-'}
            {impactPercentage.toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2 mb-1">
          <div
            className={`h-2 rounded-full ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
            style={{ width: `${impactPercentage}%` }}
          />
        </div>
        <p className="text-xs text-gray-600">{factor.description}</p>
        <p className="text-xs text-gray-500 mt-1">Value: {factor.value}</p>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (predictions.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <p>No predictions available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {predictions.map((prediction) => {
        const isExpanded = expandedPrediction === prediction.patient_id;
        const typeColor = predictionTypeColors[prediction.prediction_type] || 'gray';
        const valueColor = getValueColor(prediction.value, prediction.prediction_type);

        return (
          <div
            key={`${prediction.patient_id}-${prediction.prediction_type}`}
            className="border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm hover:shadow-md transition-shadow"
          >
            {/* Header */}
            <div
              className="p-4 cursor-pointer"
              onClick={() => toggleExpanded(prediction.patient_id)}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`px-2 py-1 rounded text-xs font-semibold text-white bg-${typeColor}-500`}
                    >
                      {predictionTypeLabels[prediction.prediction_type]}
                    </span>
                    <span className="text-sm text-gray-600">
                      Patient: {prediction.patient_id}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 mb-2">{prediction.explanation}</p>
                </div>

                <div className="text-right ml-4">
                  <div className={`text-3xl font-bold ${valueColor}`}>
                    {(prediction.value * 100).toFixed(0)}%
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    Confidence: {getConfidenceLabel(prediction.confidence)} (
                    {(prediction.confidence * 100).toFixed(0)}%)
                  </div>
                </div>
              </div>

              {/* Expand indicator */}
              <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-100">
                <div className="text-xs text-gray-500">
                  Valid until: {new Date(prediction.valid_until).toLocaleDateString()}
                </div>
                <button className="text-blue-600 text-sm hover:text-blue-800">
                  {isExpanded ? 'Hide Details' : 'View Details'}
                </button>
              </div>
            </div>

            {/* Expanded Details */}
            {isExpanded && (
              <div className="border-t border-gray-200 bg-gray-50 p-4">
                <h4 className="font-semibold text-gray-800 mb-3">
                  Contributing Factors
                </h4>
                <div className="space-y-3">
                  {prediction.factors.map((factor, index) => (
                    <div key={index}>{renderFactorImpact(factor)}</div>
                  ))}
                </div>

                {/* Actions */}
                <div className="mt-4 pt-4 border-t border-gray-200 flex gap-2">
                  {onRefresh && (
                    <button
                      onClick={() => onRefresh(prediction.patient_id)}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                    >
                      Refresh Prediction
                    </button>
                  )}
                  <button className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-100 text-sm">
                    View Patient Details
                  </button>
                </div>

                {/* Metadata */}
                <div className="mt-3 text-xs text-gray-500">
                  Generated: {new Date(prediction.created_at).toLocaleString()}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default AIPredictionsPanel;
