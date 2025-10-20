#!/usr/bin/env python3
"""
Script para atualizar imports do módulo AI consolidado.

Atualiza imports de:
- app.services.ai (antigo) → app.services.ai (novo módulo)
- app.services.ai_cache → app.services.ai.cache_layer
- app.services.ai_batch_processor → app.services.ai.batch_processor
- app.services.ai_redis_cache → app.services.ai.cache_layer

Author: AI Architect
Date: 22 Jan 2025
"""

import os
import re
from pathlib import Path
from typing import List, Tuple


# Mapeamento de imports antigos → novos
IMPORT_MAPPINGS = [
    # AIHumanizer → AIService
    (
        r"from app\.services\.ai import AIHumanizer",
        "from app.services.ai import AIService",
    ),
    (r"get_ai_humanizer\(\)", "get_ai_service()"),
    (r"ai_humanizer = get_ai_humanizer\(\)", "ai_service = get_ai_service()"),
    (r"self\.ai_humanizer", "self.ai_service"),
    # SentimentAnalyzer → AIService (sentiment analysis é método do AIService)
    (
        r"from app\.services\.ai import.*SentimentAnalyzer",
        "from app.services.ai import AIService",
    ),
    (r"get_sentiment_analyzer\(\)", "get_ai_service()"),
    # ContextBuilder → AIService (context building é método do AIService)
    (
        r"from app\.services\.ai import.*ContextBuilder",
        "from app.services.ai import AIService",
    ),
    (r"get_context_builder\(\)", "get_ai_service()"),
    # NLPUtilities → métodos do AIService
    (
        r"from app\.services\.ai import NLPUtilities",
        "from app.services.ai import AIService",
    ),
    (
        r"NLPUtilities\.calculate_readability_score\(",
        "await ai_service.calculate_readability_score(",
    ),
    (
        r"NLPUtilities\.detect_urgency_indicators\(",
        "await ai_service.detect_urgency_indicators(",
    ),
    # AICache → CacheLayer
    (
        r"from app\.services\.ai_cache import AICache",
        "from app.services.ai import CacheLayer",
    ),
    (
        r"from app\.services\.ai_cache import get_ai_cache",
        "from app.services.ai import get_cache_layer",
    ),
    (r"get_ai_cache\(\)", "get_cache_layer()"),
    (r"cache_layer = get_cache_layer", "cache_layer = get_cache_layer"),
    # ai_redis_cache → cache_layer
    (
        r"from app\.services\.ai_redis_cache import get_ai_cache_service",
        "from app.services.ai import get_cache_layer",
    ),
    (r"get_ai_cache_service\(\)", "get_cache_layer()"),
    # ai_batch_processor → batch_processor
    (r"from app\.services\.ai_batch_processor import", "from app.services.ai import"),
    # CacheOperation mantém o mesmo
    (
        r"from app\.services\.ai_cache import.*CacheOperation",
        "from app.services.ai import CacheOperation",
    ),
]


def update_file_imports(file_path: Path) -> Tuple[bool, int]:
    """
    Atualiza imports em um arquivo.

    Args:
        file_path: Path do arquivo

    Returns:
        Tuple[bool, int]: (modificado, número de substituições)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        total_replacements = 0

        # Aplicar cada mapeamento
        for old_pattern, new_pattern in IMPORT_MAPPINGS:
            content, count = re.subn(old_pattern, new_pattern, content)
            total_replacements += count

            if count > 0:
                print(
                    f"  ✓ {file_path.name}: {count}x '{old_pattern[:50]}...' → '{new_pattern[:50]}...'"
                )

        # Se houve mudanças, salvar
        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, total_replacements

        return False, 0

    except Exception as e:
        print(f"  ✗ Erro em {file_path}: {e}")
        return False, 0


def find_python_files(directory: Path, exclude_dirs: List[str] = None) -> List[Path]:
    """
    Encontra todos os arquivos Python em um diretório.

    Args:
        directory: Diretório raiz
        exclude_dirs: Diretórios a excluir

    Returns:
        Lista de paths de arquivos Python
    """
    if exclude_dirs is None:
        exclude_dirs = ["venv", "__pycache__", ".git", "node_modules", ".pytest_cache"]

    python_files = []

    for root, dirs, files in os.walk(directory):
        # Remover diretórios excluídos
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        # Adicionar arquivos .py
        for file in files:
            if file.endswith(".py"):
                python_files.append(Path(root) / file)

    return python_files


def main():
    """Função principal."""
    print("=" * 80)
    print("ATUALIZADOR DE IMPORTS - AI SERVICES CONSOLIDATION")
    print("=" * 80)
    print()

    # Determinar diretório raiz
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent

    print(f"📁 Backend directory: {backend_dir}")
    print()

    # Encontrar arquivos Python
    print("🔍 Procurando arquivos Python...")
    python_files = find_python_files(backend_dir)
    print(f"   Encontrados: {len(python_files)} arquivos")
    print()

    # Processar arquivos
    print("🔄 Atualizando imports...")
    print()

    modified_files = []
    total_replacements = 0

    for file_path in python_files:
        modified, count = update_file_imports(file_path)
        if modified:
            modified_files.append(file_path)
            total_replacements += count

    # Resumo
    print()
    print("=" * 80)
    print("RESUMO")
    print("=" * 80)
    print(f"✅ Arquivos modificados: {len(modified_files)}")
    print(f"✅ Total de substituições: {total_replacements}")
    print()

    if modified_files:
        print("📝 Arquivos atualizados:")
        for file_path in modified_files:
            rel_path = file_path.relative_to(backend_dir)
            print(f"   - {rel_path}")
        print()

    print("=" * 80)
    print("✅ ATUALIZAÇÃO COMPLETA!")
    print("=" * 80)
    print()
    print("📌 PRÓXIMOS PASSOS:")
    print("   1. Revisar mudanças: git diff")
    print("   2. Testar aplicação: pytest tests/")
    print("   3. Remover arquivos antigos:")
    print("      - app/services/ai.py")
    print("      - app/services/ai_cache.py")
    print("      - app/services/ai_redis_cache.py")
    print("      - app/services/ai_batch_processor.py")
    print("      - app/services/ai_cache_service.py")
    print("   4. Commit: git commit -m 'refactor: migrate to consolidated AI services'")
    print()


if __name__ == "__main__":
    main()
