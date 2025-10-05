"""
Script para executar os testes Redis com o ambiente correto.
"""
import sys
import os
from pathlib import Path

# Adiciona o diretório backend ao PYTHONPATH
backend_dir = Path(__file__).parent.parent.parent.parent / "backend-hormonia"
sys.path.insert(0, str(backend_dir))

# Agora executa os testes
import pytest

if __name__ == "__main__":
    test_dir = Path(__file__).parent
    exit_code = pytest.main([
        str(test_dir),
        "-v",
        "--tb=short",
        "-p", "no:warnings"
    ])
    sys.exit(exit_code)
