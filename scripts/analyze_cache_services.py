#!/usr/bin/env python3
"""
Script to analyze cache service usage and plan consolidation.
Maps all imports and usage patterns to facilitate migration to unified_cache.py
"""
import os
import re
from pathlib import Path
from collections import defaultdict

# Cache files to analyze
CACHE_FILES = [
    "app/services/ai/cache_layer.py",
    "app/services/analytics_cache.py",
    "app/services/cache.py",
    "app/services/cache/specialized/analytics_cache.py",
    "app/services/cache/specialized/jwt_cache.py",
    "app/services/cache/specialized/query_cache.py",
    "app/services/cache/specialized/template_cache.py",
    "app/services/cache_invalidation.py",
    "app/services/cache_service.py",
    "app/services/jwt_cache_service.py",
    "app/services/template_cache.py",
]

KEEP_FILE = "app/services/unified_cache.py"

def find_imports(root_dir):
    """Find all imports of cache services."""
    usage_map = defaultdict(list)

    for root, dirs, files in os.walk(root_dir):
        # Skip some directories
        if any(skip in root for skip in ['node_modules', '.git', '__pycache__', 'venv', '.venv']):
            continue

        for file in files:
            if not file.endswith('.py'):
                continue

            file_path = Path(root) / file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Look for imports of cache services
                for cache_file in CACHE_FILES:
                    # Convert path to module name
                    module_name = cache_file.replace('/', '.').replace('.py', '')

                    # Check various import patterns
                    patterns = [
                        rf'from {re.escape(module_name)} import',
                        rf'import {re.escape(module_name)}',
                        # Also check for relative imports
                        rf'from \..*{re.escape(Path(cache_file).stem)} import',
                    ]

                    for pattern in patterns:
                        if re.search(pattern, content):
                            relative_path = file_path.relative_to(Path(root_dir))
                            usage_map[cache_file].append(str(relative_path))
                            break

            except Exception as e:
                pass

    return usage_map

def analyze_cache_file(file_path):
    """Analyze a cache file to understand its API."""
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find class definitions
        classes = re.findall(r'class\s+(\w+)', content)

        # Find function definitions (public methods/functions)
        functions = re.findall(r'def\s+(\w+)\s*\(', content)
        public_functions = [f for f in functions if not f.startswith('_')]

        # Count lines
        lines = len(content.split('\n'))

        return {
            'classes': classes,
            'public_functions': public_functions,
            'lines': lines,
        }
    except Exception as e:
        return None

def main():
    root_dir = Path(__file__).parent.parent / "backend-hormonia"

    print("="*80)
    print("CACHE SERVICES CONSOLIDATION ANALYSIS")
    print("="*80)
    print()

    # Analyze unified_cache.py (the keeper)
    print("📦 UNIFIED CACHE (Master Implementation)")
    print("-" * 80)
    unified_path = root_dir / KEEP_FILE
    unified_info = analyze_cache_file(unified_path)
    if unified_info:
        print(f"Location: {KEEP_FILE}")
        print(f"Classes: {', '.join(unified_info['classes'])}")
        print(f"Public Methods: {len(unified_info['public_functions'])}")
        print(f"Lines of Code: {unified_info['lines']}")
        print()

    # Analyze each cache file
    print("🗑️  CACHE FILES TO REMOVE")
    print("-" * 80)

    total_lines = 0
    for cache_file in CACHE_FILES:
        file_path = root_dir / cache_file
        info = analyze_cache_file(file_path)

        if info:
            print(f"\n📄 {cache_file}")
            print(f"   Classes: {', '.join(info['classes']) if info['classes'] else 'None'}")
            print(f"   Functions: {len(info['public_functions'])} public")
            print(f"   Lines: {info['lines']}")
            total_lines += info['lines']

    print()
    print(f"💾 Total lines to remove: {total_lines}")
    print()

    # Find usage
    print("🔍 USAGE ANALYSIS")
    print("-" * 80)
    usage_map = find_imports(root_dir)

    total_files_affected = 0
    for cache_file in CACHE_FILES:
        usages = usage_map.get(cache_file, [])
        if usages:
            print(f"\n📌 {cache_file}")
            print(f"   Used in {len(usages)} files:")
            for usage in usages[:5]:  # Show first 5
                print(f"      - {usage}")
            if len(usages) > 5:
                print(f"      ... and {len(usages) - 5} more")
            total_files_affected += len(usages)

    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✅ Keep: 1 file (unified_cache.py)")
    print(f"🗑️  Remove: {len(CACHE_FILES)} files ({total_lines} lines)")
    print(f"📝 Update imports in: {total_files_affected} files")
    print()
    print("Next Steps:")
    print("1. Review unified_cache.py capabilities")
    print("2. Map missing features from deprecated caches")
    print("3. Update all imports to use unified_cache")
    print("4. Remove deprecated cache files")
    print("5. Run full test suite")
    print()

if __name__ == "__main__":
    main()
