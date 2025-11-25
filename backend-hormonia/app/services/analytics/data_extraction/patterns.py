"""
Medical pattern definitions for data extraction.
Contains regex patterns for pain, medication, symptoms, and emotions.
"""
from typing import Dict, List


class MedicalPatterns:
    """Medical terminology patterns for extraction."""

    def __init__(self):
        """Initialize medical patterns."""
        self.pain_patterns = {
            'pain_descriptors': [
                r'\b(dor|pain|ache|aching|hurt|hurting|sore|tender)\b',
                r'\b(doloroso|dolorosa|doendo|machucando)\b'
            ],
            'pain_intensity': [
                r'\b(leve|mild|light|fraca|fraco)\b',
                r'\b(moderada|moderate|média|medio)\b',
                r'\b(forte|strong|intensa|intenso|severe)\b',
                r'\b(insuportável|unbearable|terrível|terrible|extrema|extreme)\b'
            ],
            'pain_scale': r'\b([1-9]|10)\s*(?:de\s*10|/10|out\s*of\s*10)\b'
        }

        self.medication_patterns = {
            'medication_names': [
                r'\b(comprimido|tablet|cápsula|capsule|medicamento|medication|remédio|medicine)\b',
                r'\b(mg|ml|mcg|g|grama|gram|miligramas?|milligrams?)\b'
            ],
            'dosage': r'\b(\d+(?:\.\d+)?)\s*(mg|ml|mcg|g|comprimidos?|tablets?|cápsulas?|capsules?)\b',
            'frequency': [
                r'\b(uma vez|once|twice|duas vezes|três vezes|three times)\b',
                r'\b(diário|daily|diariamente|por dia|per day)\b',
                r'\b(manhã|morning|tarde|afternoon|noite|night|evening)\b'
            ]
        }

        self.symptom_patterns = {
            'common_symptoms': [
                r'\b(náusea|nausea|vômito|vomiting|tontura|dizziness|dizzy)\b',
                r'\b(cansaço|fatigue|tired|weakness|fraqueza)\b',
                r'\b(febre|fever|calafrio|chills|suor|sweating)\b',
                r'\b(dor de cabeça|headache|enxaqueca|migraine)\b'
            ],
            'severity_indicators': [
                r'\b(pior|worse|piorando|worsening|melhor|better|melhorando|improving)\b',
                r'\b(começou|started|parou|stopped|continua|continues|persistent)\b'
            ]
        }

        self.emotional_patterns = {
            'positive_emotions': [
                r'\b(feliz|happy|bem|good|ótimo|great|animada|excited|confiante|confident)\b',
                r'\b(melhor|better|aliviada|relieved|grata|grateful|esperançosa|hopeful)\b'
            ],
            'negative_emotions': [
                r'\b(triste|sad|deprimida|depressed|ansiosa|anxious|preocupada|worried)\b',
                r'\b(medo|fear|scared|assustada|nervosa|nervous|estressada|stressed)\b'
            ],
            'emotional_intensity': [
                r'\b(muito|very|extremely|bastante|quite|um pouco|a little|slightly)\b'
            ]
        }
