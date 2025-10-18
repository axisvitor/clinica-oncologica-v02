#!/usr/bin/env python3
"""
Analisa uso de services no backend.

Este script gera um relatório completo sobre:
- Services definidos e sua localização
- Services importados e frequência de uso
- Services nunca usados (candidatos a remoção)
- Duplicações potenciais de responsabilidade
- Dependências entre services
- Análise de complexidade

Usage:
    python scripts/analyze_services.py
    python scripts/analyze_services.py --output report.md
    python scripts/analyze_services.py --json
"""

import os
import re
import ast
import json
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Set, Tuple
from datetime import datetime


class ServiceAnalyzer:
    """Analisador de services do backend."""

    def __init__(self, services_dir: str = "app/services"):
        self.services_dir = Path(services_dir)
        self.app_dir = Path("app")
        self.services: Dict[str, Path] = {}
        self.imports: Dict[str, List[str]] = defaultdict(list)
        self.classes: Dict[str, List[str]] = defaultdict(list)
        self.functions: Dict[str, int] = {}
        self.lines_of_code: Dict[str, int] = {}

    def find_service_files(self) -> Dict[str, Path]:
        """Encontra todos os arquivos de service."""
        services = {}

        # Services no diretório principal
        for py_file in self.services_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                services[py_file.stem] = py_file

        # Services em subdiretórios
        for subdir in ["flow", "monitoring", "orchestrators", "delivery_callbacks"]:
            subdir_path = self.services_dir / subdir
            if subdir_path.exists():
                for py_file in subdir_path.glob("*.py"):
                    if py_file.name != "__init__.py":
                        key = f"{subdir}/{py_file.stem}"
                        services[key] = py_file

        return services

    def analyze_file_content(self, filepath: Path) -> Tuple[List[str], int, int]:
        """Analisa conteúdo de um arquivo Python."""
        try:
            content = filepath.read_text(encoding="utf-8")
            lines = len(content.splitlines())

            # Parse AST para encontrar classes
            tree = ast.parse(content)
            classes = [
                node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            ]
            functions = len(
                [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            )

            return classes, lines, functions
        except Exception as e:
            print(f"Warning: Could not parse {filepath}: {e}")
            return [], 0, 0

    def find_service_imports(self) -> Dict[str, List[str]]:
        """Encontra todos os imports de services em todo o código."""
        imports = defaultdict(list)

        for py_file in self.app_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")

                # Pattern 1: from app.services.xxx import YyyService
                matches = re.findall(r"from app\.services\.(\S+) import (\w+)", content)
                for module, service_name in matches:
                    key = f"{module}.{service_name}"
                    imports[key].append(str(py_file))

                # Pattern 2: from app.services import xxx
                matches = re.findall(r"from app\.services import (\w+)", content)
                for service_name in matches:
                    imports[service_name].append(str(py_file))

                # Pattern 3: import app.services.xxx
                matches = re.findall(r"import app\.services\.(\w+)", content)
                for service_name in matches:
                    imports[service_name].append(str(py_file))

            except Exception as e:
                pass  # Ignorar erros de leitura

        return imports

    def find_duplications(self) -> List[Tuple[str, str, str]]:
        """Encontra duplicações potenciais baseadas em nomes similares."""
        duplications = []
        service_names = list(self.services.keys())
        checked = set()

        for name1 in service_names:
            for name2 in service_names:
                if name1 != name2 and name1 not in checked:
                    # Remover sufixos comuns para comparação
                    clean1 = (
                        name1.replace("_service", "")
                        .replace("_manager", "")
                        .replace("_handler", "")
                    )
                    clean2 = (
                        name2.replace("_service", "")
                        .replace("_manager", "")
                        .replace("_handler", "")
                    )

                    # Checar similaridade
                    if (
                        clean1 in clean2
                        or clean2 in clean1
                        or clean1.replace("_", "") == clean2.replace("_", "")
                        or name1.startswith(name2.split("_")[0])
                        or name2.startswith(name1.split("_")[0])
                    ):
                        reason = self._detect_duplication_reason(
                            name1, name2, clean1, clean2
                        )
                        duplications.append((name1, name2, reason))
                        checked.add(name2)

        return duplications

    def _detect_duplication_reason(
        self, name1: str, name2: str, clean1: str, clean2: str
    ) -> str:
        """Detecta o motivo da duplicação."""
        if "enhanced" in name1 or "enhanced" in name2:
            return "Enhanced version"
        elif "optimized" in name1 or "optimized" in name2:
            return "Optimized version"
        elif clean1 == clean2:
            return "Same base name with different suffixes"
        elif clean1 in clean2 or clean2 in clean1:
            return "Subset naming (one contains the other)"
        else:
            return "Similar naming pattern"

    def categorize_services(self) -> Dict[str, List[str]]:
        """Categoriza services por domínio."""
        categories = defaultdict(list)

        keywords = {
            "AI": ["ai", "gemini", "openai", "langchain", "llm"],
            "Cache": ["cache", "redis"],
            "Flow": ["flow", "workflow", "engine"],
            "Message": ["message", "whatsapp", "notification"],
            "Quiz": ["quiz", "question", "template"],
            "Auth": ["auth", "jwt", "firebase", "session"],
            "Monitoring": ["monitor", "metrics", "performance", "alert"],
            "Database": ["database", "query", "index", "integrity"],
            "Security": ["security", "encryption", "privacy", "phi"],
            "Patient": ["patient", "user", "admin"],
            "Analytics": ["analytics", "stats", "report"],
            "Error Handling": ["error", "recovery", "dlq", "circuit_breaker"],
            "WebSocket": ["websocket", "ws", "realtime"],
            "AB Testing": ["ab_testing", "experiment"],
            "Other": [],
        }

        for service_name in self.services.keys():
            categorized = False
            for category, words in keywords.items():
                if category != "Other":
                    if any(word in service_name.lower() for word in words):
                        categories[category].append(service_name)
                        categorized = True
                        break

            if not categorized:
                categories["Other"].append(service_name)

        return dict(categories)

    def analyze(self) -> Dict:
        """Executa análise completa."""
        print("🔍 Analyzing backend services...")

        # 1. Encontrar services
        self.services = self.find_service_files()
        print(f"   Found {len(self.services)} service files")

        # 2. Analisar conteúdo
        for name, path in self.services.items():
            classes, lines, functions = self.analyze_file_content(path)
            self.classes[name] = classes
            self.lines_of_code[name] = lines
            self.functions[name] = functions

        # 3. Encontrar imports
        self.imports = self.find_service_imports()
        print(f"   Found {len(self.imports)} unique imports")

        # 4. Encontrar duplicações
        duplications = self.find_duplications()
        print(f"   Found {len(duplications)} potential duplications")

        # 5. Categorizar
        categories = self.categorize_services()

        # 6. Identificar não usados
        unused = self._find_unused_services()

        # 7. Ranking de uso
        most_used = self._get_most_used_services()

        return {
            "total_services": len(self.services),
            "services": self.services,
            "imports": dict(self.imports),
            "duplications": duplications,
            "categories": categories,
            "unused": unused,
            "most_used": most_used,
            "classes": dict(self.classes),
            "lines_of_code": self.lines_of_code,
            "functions": self.functions,
            "timestamp": datetime.now().isoformat(),
        }

    def _find_unused_services(self) -> List[str]:
        """Encontra services nunca importados."""
        unused = []

        for service_name in self.services.keys():
            # Checar se algum import usa este service
            used = any(
                service_name in key or service_name.replace("/", ".") in key
                for key in self.imports.keys()
            )

            if not used:
                unused.append(service_name)

        return sorted(unused)

    def _get_most_used_services(self, top_n: int = 20) -> List[Tuple[str, int]]:
        """Retorna os services mais usados."""
        usage_count = Counter()

        for service_key, files in self.imports.items():
            # Extrair nome base do service
            base_name = service_key.split(".")[0].replace("/", "_")
            usage_count[base_name] += len(files)

        return usage_count.most_common(top_n)

    def generate_report(self, data: Dict, format: str = "markdown") -> str:
        """Gera relatório em formato especificado."""
        if format == "json":
            # Converter Path objects para strings
            serializable_data = {
                **data,
                "services": {k: str(v) for k, v in data["services"].items()},
            }
            return json.dumps(serializable_data, indent=2, ensure_ascii=False)
        else:
            return self._generate_markdown_report(data)

    def _generate_markdown_report(self, data: Dict) -> str:
        """Gera relatório em Markdown."""
        report = []

        # Header
        report.append("# 📊 Backend Services Analysis Report")
        report.append(f"\n**Generated:** {data['timestamp']}")
        report.append(f"\n**Total Services:** {data['total_services']}")
        report.append("\n---\n")

        # Executive Summary
        report.append("## 🎯 Executive Summary\n")
        report.append(f"- **Total Service Files:** {data['total_services']}")
        report.append(f"- **Unique Imports Found:** {len(data['imports'])}")
        report.append(
            f"- **Unused Services:** {len(data['unused'])} ({len(data['unused']) / data['total_services'] * 100:.1f}%)"
        )
        report.append(f"- **Potential Duplications:** {len(data['duplications'])}")

        total_loc = sum(data["lines_of_code"].values())
        avg_loc = (
            total_loc / data["total_services"] if data["total_services"] > 0 else 0
        )
        report.append(f"- **Total Lines of Code:** {total_loc:,}")
        report.append(f"- **Average LOC per Service:** {avg_loc:.0f}")
        report.append("\n---\n")

        # Services by Category
        report.append("## 📁 Services by Category\n")
        for category, services in sorted(
            data["categories"].items(), key=lambda x: len(x[1]), reverse=True
        ):
            report.append(f"### {category} ({len(services)})\n")
            for service in sorted(services):
                loc = data["lines_of_code"].get(service, 0)
                classes = len(data["classes"].get(service, []))
                funcs = data["functions"].get(service, 0)
                report.append(
                    f"- `{service}.py` - {loc} lines, {classes} classes, {funcs} functions"
                )
            report.append("")

        report.append("---\n")

        # Most Used Services
        report.append("## 🔥 Top 20 Most Used Services\n")
        report.append("| Rank | Service | Usage Count | Files Using It |")
        report.append("|------|---------|-------------|----------------|")
        for rank, (service, count) in enumerate(data["most_used"], 1):
            report.append(f"| {rank} | `{service}` | {count} | {count} files |")

        report.append("\n---\n")

        # Unused Services
        report.append(f"## 🚨 Unused Services ({len(data['unused'])})\n")
        report.append(
            "**These services are NEVER imported anywhere in the codebase.**\n"
        )
        report.append("**Action:** Review and consider removing if truly unused.\n")

        if data["unused"]:
            for service in data["unused"]:
                loc = data["lines_of_code"].get(service, 0)
                report.append(f"- `{service}.py` ({loc} lines)")
        else:
            report.append("✅ No unused services found!\n")

        report.append("\n---\n")

        # Potential Duplications
        report.append(f"## ⚠️ Potential Duplications ({len(data['duplications'])})\n")
        report.append(
            "**These services have similar names and may overlap in responsibility.**\n"
        )

        if data["duplications"]:
            for service1, service2, reason in data["duplications"]:
                loc1 = data["lines_of_code"].get(service1, 0)
                loc2 = data["lines_of_code"].get(service2, 0)
                report.append(f"\n### `{service1}.py` ↔️ `{service2}.py`")
                report.append(f"**Reason:** {reason}")
                report.append(f"**Sizes:** {loc1} lines ↔️ {loc2} lines")

                classes1 = data["classes"].get(service1, [])
                classes2 = data["classes"].get(service2, [])
                if classes1:
                    report.append(f"**Classes in {service1}:** {', '.join(classes1)}")
                if classes2:
                    report.append(f"**Classes in {service2}:** {', '.join(classes2)}")
        else:
            report.append("✅ No obvious duplications found!\n")

        report.append("\n---\n")

        # Recommendations
        report.append("## 💡 Recommendations\n")

        if len(data["unused"]) > 10:
            report.append(f"### 1. Remove Unused Services (Priority: HIGH)")
            report.append(
                f"- Found **{len(data['unused'])} unused services** wasting space"
            )
            report.append(
                f"- Estimated cleanup: **{sum(data['lines_of_code'].get(s, 0) for s in data['unused']):,} lines**"
            )
            report.append("")

        if len(data["duplications"]) > 5:
            report.append(f"### 2. Consolidate Duplicated Services (Priority: HIGH)")
            report.append(
                f"- Found **{len(data['duplications'])} potential duplications**"
            )
            report.append(f"- Review each pair and merge similar responsibilities")
            report.append("")

        # Category-specific recommendations
        ai_services = len(data["categories"].get("AI", []))
        if ai_services > 3:
            report.append(f"### 3. Consolidate AI Services (Priority: MEDIUM)")
            report.append(f"- Found **{ai_services} AI-related services**")
            report.append(f"- Consider consolidating into 1-2 main services")
            report.append("")

        cache_services = len(data["categories"].get("Cache", []))
        if cache_services > 3:
            report.append(f"### 4. Consolidate Cache Services (Priority: MEDIUM)")
            report.append(f"- Found **{cache_services} Cache-related services**")
            report.append(f"- Should have only 1 unified cache service")
            report.append("")

        flow_services = len(data["categories"].get("Flow", []))
        if flow_services > 5:
            report.append(f"### 5. Consolidate Flow Services (Priority: HIGH)")
            report.append(f"- Found **{flow_services} Flow-related services**")
            report.append(f"- Consider consolidating into 2-3 core services")
            report.append("")

        report.append("---\n")

        # Complexity Analysis
        report.append("## 📈 Complexity Analysis\n")

        # Services com mais de 500 linhas
        large_services = [
            (name, loc) for name, loc in data["lines_of_code"].items() if loc > 500
        ]
        if large_services:
            report.append(f"### Large Services (>500 lines): {len(large_services)}\n")
            for name, loc in sorted(large_services, key=lambda x: x[1], reverse=True)[
                :10
            ]:
                report.append(f"- `{name}.py`: **{loc} lines** - Consider splitting")
            report.append("")

        report.append("---\n")

        # Next Steps
        report.append("## 🚀 Next Steps\n")
        report.append(
            "1. **Review unused services** - Delete or document why they exist"
        )
        report.append(
            "2. **Consolidate duplications** - Merge services with overlapping responsibilities"
        )
        report.append("3. **Refactor large services** - Split services with >500 lines")
        report.append(
            "4. **Create service map** - Document responsibilities of each service"
        )
        report.append(
            "5. **Establish naming conventions** - Prevent future duplications"
        )
        report.append(
            "6. **Add service registry** - Central documentation of all services"
        )

        return "\n".join(report)


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description="Analyze backend services")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--services-dir", default="app/services", help="Services directory"
    )

    args = parser.parse_args()

    # Mudar para diretório do backend se necessário
    if not Path("app/services").exists():
        backend_dir = Path(__file__).parent.parent
        os.chdir(backend_dir)

    # Criar analyzer
    analyzer = ServiceAnalyzer(args.services_dir)

    # Executar análise
    print("\n" + "=" * 80)
    print("🔍 BACKEND SERVICES ANALYSIS")
    print("=" * 80 + "\n")

    data = analyzer.analyze()

    # Gerar relatório
    format_type = "json" if args.json else "markdown"
    report = analyzer.generate_report(data, format=format_type)

    # Salvar ou exibir
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
        print(f"\n✅ Report saved to: {output_path}")
    else:
        print("\n" + report)

    print("\n" + "=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
