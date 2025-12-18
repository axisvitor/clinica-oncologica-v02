"""
Field-specific encryption module.

Provides specialized encryptors for:
- CPF (Brazilian National ID)
- Email addresses
- Phone numbers
"""

from .base import BaseFieldEncryptor
from .cpf import CPFEncryptor
from .email import EmailEncryptor
from .phone import PhoneEncryptor

__all__ = [
    "BaseFieldEncryptor",
    "CPFEncryptor",
    "EmailEncryptor",
    "PhoneEncryptor",
]
