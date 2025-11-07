#!/usr/bin/env python3
"""
Script para limpar arquivos de cache legados e atualizar imports.

Remove arquivos de cache duplicados/legados:
- app/services/cache.py (vazio)
- app/services/cache_service.py
- app/services/cache_invalidation.py
- app/services/unified_cache.py
- app/services/jwt_cache_service.py
- app/services/template_cache.py
- app/services/analytics_cache.py

Atualiza imports para usar o módulo consolidado:
- app/services/cache/*

Author: AI Architect
Date: 22 Jan 2025
"""

import os
import re
from pathlib import Path
from typing import List, Tuple
from app.services.unified_cache import UnifiedCacheService

# Mapeamento de imports antigos → novos
IMPORT_MAPPINGS = [
    # analytics_cache
    (
        r"from app\.services\.analytics_cache import get_analytics_cache",
        "from app.services.cache.specialized import get_analytics_cache",
    ),
    (
        r"from app\.services\.analytics_cache import cache_analytics_data",
        "from app.services.cache.specialized import AnalyticsCache",
    ),
    (
        r"from app\.services\.analytics_cache import AnalyticsCache",
        "from app.services.cache.specialized import AnalyticsCache",
    ),
    # jwt_cache_service
    (
        r"from app\.services\.jwt_cache_service import JWTCacheService",
        "from app.services.cache.specialized import JWTCache",
    ),
    (
        r"from app\.services\.jwt_cache_service import get_jwt_cache",
        "from app.services.cache.specialized import get_jwt_cache",
    ),
    # template_cache
    (
        r"from app\.services\.template_cache import get_template_cache",
        "from app.services.cache.specialized import get_template_cache",
    ),
    (
        r"from app\.services\.template_cache import TemplateRedisCache",
        "from app.services.cache.specialized import TemplateCache",
    ),
    (
        r"from app\.services\.template_cache import TemplateCache",
        "from app.services.cache.specialized import TemplateCache",
    ),
    # cache_service
    (
        r"from app\.services\.cache_service import get_cache_service",
        "
    ),
    (
        r"from app\.services\.cache_service import CacheService",
        "
    ),
    # unified_cache
    (
        r"from app\.services\.unified_cache import UnifiedCacheService",
        "
    ),
    (
        r"from app\.services\.unified_cache import get_cache_manager",
        "
    ),
    # cache_invalidation
    (
        r"from app\.services\.cache_invalidation import get_cache_invalidation_service",
        "from app.services.cache.invalidation import get_invalidator",
    ),
    (
        r"from app\.services\.cache_invalidation import CacheInvalidationService",
        "from app.services.cache.invalidation import CacheInvalidator",
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
                    f"  ✓ {file_path.name}: {count}x '{old_pattern[:60]}...' → '{new_pattern[:60]}...'"
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
    print("CLEANUP DE ARQUIVOS DE CACHE LEGADOS")
    print("=" * 80)
    print()

    # Determinar diretório raiz
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent

    print(f"📁 Backend directory: {backend_dir}")
    print()

    # Listar arquivos legados a remover
    legacy_files = [
        "app/services/cache.py",
        "app/services/cache_service.py",
        "app/services/cache_invalidation.py",
        "app/services/unified_cache.py",
        "app/services/jwt_cache_service.py",
        "app/services/template_cache.py",
        "app/services/analytics_cache.py",
    ]

    print("🗑️  Arquivos legados a remover:")
    for file in legacy_files:
        file_path = backend_dir / file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   - {file} ({size} bytes)")
        else:
            print(f"   - {file} (não encontrado)")
    print()

    # Encontrar arquivos Python para atualizar
    print("🔍 Procurando arquivos Python para atualizar imports...")
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
    print(f"✅ Arquivos com imports atualizados: {len(modified_files)}")
    print(f"✅ Total de substituições: {total_replacements}")
    print()

    if modified_files:
        print("📝 Arquivos atualizados:")
        for file_path in modified_files:
            rel_path = file_path.relative_to(backend_dir)
            print(f"   - {rel_path}")
        print()

    # Verificar se há arquivos legados para remover
    legacy_to_remove = []
    total_legacy_size = 0
    for file in legacy_files:
        file_path = backend_dir / file
        if file_path.exists():
            size = file_path.stat().st_size
            legacy_to_remove.append((file, size))
            total_legacy_size += size

    if legacy_to_remove:
        print("=" * 80)
        print("ARQUIVOS LEGADOS ENCONTRADOS")
        print("=" * 80)
        print(f"Total: {len(legacy_to_remove)} arquivos ({total_legacy_size:,} bytes)")
        print()
        for file, size in legacy_to_remove:
            print(f"   - {file} ({size:,} bytes)")
        print()

    print("=" * 80)
    print("✅ ATUALIZAÇÃO DE IMPORTS COMPLETA!")
    print("=" * 80)
    print()
    print("📌 PRÓXIMOS PASSOS:")
    print("   1. Revisar mudanças: git diff")
    print("   2. Testar aplicação: pytest tests/")
    print("   3. Remover arquivos legados manualmente:")
    print()
    for file in legacy_files:
        print(f"      git rm {file}")
    print()
    print("   4. Commit:")
    print("      git add -A")
    print("      git commit -m 'refactor(cache): migrate to consolidated cache module'")
    print()


if __name__ == "__main__":
    main()
