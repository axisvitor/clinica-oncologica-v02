"""
FIX #13 - PROTEÇÃO DE DADOS SENSÍVEIS
Advanced Data Protection and Sanitization Service
"""

import re
import hashlib
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from uuid import UUID
from enum import Enum
import json

logger = logging.getLogger(__name__)


class SensitiveDataType(Enum):
    """Types of sensitive data that need protection."""
    CPF = "cpf"
    CNPJ = "cnpj"
    EMAIL = "email"
    PHONE = "phone"
    NAME = "name"
    ADDRESS = "address"
    MEDICAL_INFO = "medical_info"


class AccessReason(Enum):
    """Reasons for accessing sensitive data."""
    MEDICAL_TREATMENT = "medical_treatment"
    ADMINISTRATIVE = "administrative"
    AUDIT = "audit"
    SUPPORT = "support"
    EMERGENCY = "emergency"


class DataProtectionService:
    """Comprehensive data protection service for healthcare sensitive data."""
    
    def __init__(self):
        """Initialize data protection service."""
        # Patterns for sensitive data detection
        self.patterns = {
            SensitiveDataType.CPF: re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b'),
            SensitiveDataType.EMAIL: re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            SensitiveDataType.PHONE: re.compile(r'\b(?:\+55\s?)?(?:\(\d{2}\)\s?)?(?:9\s?)?\d{4}[-.]?\d{4}\b'),
        }
        logger.info("Data Protection Service initialized")
    
    def mask_cpf(self, cpf: str) -> str:
        """Mask CPF maintaining format for identification."""
        if not cpf:
            return cpf
        
        clean_cpf = re.sub(r'[^\d]', '', cpf)
        if len(clean_cpf) != 11:
            return cpf
        
        masked = clean_cpf[:6] + '*' * 5
        return f"{masked[:3]}.{masked[3:6]}.***-**"
    
    def mask_email(self, email: str) -> str:
        """Mask email preserving domain for identification."""
        if not email or '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) <= 1:
            return email
        elif len(local) <= 3:
            masked_local = local[0] + '*' * (len(local) - 1)
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    def mask_phone(self, phone: str) -> str:
        """Mask phone number preserving area code."""
        if not phone:
            return phone
        
        digits = re.sub(r'[^\d]', '', phone)
        if len(digits) == 11:
            return f"({digits[:2]}) 9****-****"
        elif len(digits) == 10:
            return f"({digits[:2]}) ****-****"
        else:
            if len(digits) > 4:
                return digits[:2] + '*' * (len(digits) - 4) + digits[-2:]
            else:
                return '*' * len(digits)
    
    def sanitize_for_logging(self, data: Union[str, Dict, List], 
                           preserve_types: List[SensitiveDataType] = None) -> Union[str, Dict, List]:
        """Sanitize data for safe logging by masking sensitive information."""
        if preserve_types is None:
            preserve_types = []
        
        if isinstance(data, str):
            return self._sanitize_string(data, preserve_types)
        elif isinstance(data, dict):
            return self._sanitize_dict(data, preserve_types)
        elif isinstance(data, list):
            return [self.sanitize_for_logging(item, preserve_types) for item in data]
        else:
            return data
    
    def _sanitize_string(self, text: str, preserve_types: List[SensitiveDataType]) -> str:
        """Sanitize string by masking sensitive patterns."""
        if not text:
            return text
        
        sanitized = text
        
        if SensitiveDataType.CPF not in preserve_types:
            sanitized = self.patterns[SensitiveDataType.CPF].sub(
                lambda m: self.mask_cpf(m.group()), sanitized
            )
        
        if SensitiveDataType.EMAIL not in preserve_types:
            sanitized = self.patterns[SensitiveDataType.EMAIL].sub(
                lambda m: self.mask_email(m.group()), sanitized
            )
        
        if SensitiveDataType.PHONE not in preserve_types:
            sanitized = self.patterns[SensitiveDataType.PHONE].sub(
                lambda m: self.mask_phone(m.group()), sanitized
            )
        
        return sanitized
    
    def _sanitize_dict(self, data: Dict, preserve_types: List[SensitiveDataType]) -> Dict:
        """Sanitize dictionary by masking sensitive fields."""
        sanitized = {}
        
        sensitive_fields = {
            'cpf': SensitiveDataType.CPF,
            'email': SensitiveDataType.EMAIL,
            'phone': SensitiveDataType.PHONE,
            'telefone': SensitiveDataType.PHONE,
        }
        
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                sanitized[key] = self.sanitize_for_logging(value, preserve_types)
            elif isinstance(value, str) and key.lower() in sensitive_fields:
                data_type = sensitive_fields[key.lower()]
                
                if data_type not in preserve_types:
                    if data_type == SensitiveDataType.CPF:
                        sanitized[key] = self.mask_cpf(value)
                    elif data_type == SensitiveDataType.EMAIL:
                        sanitized[key] = self.mask_email(value)
                    elif data_type == SensitiveDataType.PHONE:
                        sanitized[key] = self.mask_phone(value)
                    else:
                        sanitized[key] = value
                else:
                    sanitized[key] = value
            else:
                if isinstance(value, str):
                    sanitized[key] = self._sanitize_string(value, preserve_types)
                else:
                    sanitized[key] = value
        
        return sanitized
    
    def log_sensitive_access(self, 
                           user_id: UUID,
                           data_type: SensitiveDataType,
                           entity_id: UUID,
                           access_reason: AccessReason,
                           additional_context: Dict[str, Any] = None) -> None:
        """Log access to sensitive data for audit trail."""
        try:
            audit_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': str(user_id),
                'data_type': data_type.value,
                'entity_id': str(entity_id),
                'access_reason': access_reason.value,
                'ip_address': additional_context.get('ip_address') if additional_context else None,
                'user_agent': additional_context.get('user_agent') if additional_context else None,
                'session_id': additional_context.get('session_id') if additional_context else None,
            }
            
            sensitive_logger = logging.getLogger('sensitive_data_access')
            sensitive_logger.info(f"SENSITIVE_ACCESS: {json.dumps(audit_entry)}")
            
        except Exception as e:
            logger.error(f"Failed to log sensitive data access: {e}")


# Global service instance
_data_protection_service = None

def get_data_protection_service() -> DataProtectionService:
    """Get global data protection service instance."""
    global _data_protection_service
    if _data_protection_service is None:
        _data_protection_service = DataProtectionService()
    return _data_protection_service
