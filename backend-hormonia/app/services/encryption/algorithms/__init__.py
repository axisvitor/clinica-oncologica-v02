"""
Encryption algorithms module.

Provides Strategy Pattern implementations for:
- AES-256-GCM (recommended, authenticated encryption)
- AES-256-CBC (legacy, backward compatibility)
- Fernet (symmetric encryption for quiz tokens)
"""

from .base import BaseAlgorithm
from .aes_gcm import AESGCMAlgorithm
from .aes_cbc import AESCBCAlgorithm
from .fernet import FernetAlgorithm

__all__ = [
    "BaseAlgorithm",
    "AESGCMAlgorithm",
    "AESCBCAlgorithm",
    "FernetAlgorithm",
]
