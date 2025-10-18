#!/usr/bin/env python3
"""
Script de Análise de Queries N+1 - Sistema Hormonia
====================================================

Detecta automaticamente queries N+1 no código analisando padrões de uso
de relacionamentos SQLAlchemy.

Execução:
---------
# Análise completa
python scripts/analyze_n_plus_one.py

# Análise de arquivo específico
python scripts/analyze_n_plus_one.py --file app/services/patient.py

# Com sugestões de correção
python scripts/analyze_n_plus_one.py --suggest

# Output JSON
python scripts/analyze_n_plus_one.py --format json > report.json

Detecta:
--------
- Acesso a relacionamentos em loops
- Queries sem eager loading
- Relacionamentos lazy em endpoints de lista
- Agregações que poderiam ser feitas no banco
"""

import ast
import os
import sys
import json
import argparse
from typing import List, Dict, Any, Set
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class NPlusOneIssue:
    """Representa um problema N+1 detectado."""

    file: str
    line: int
    column: int
    severity: str  # 'high', 'medium', 'low'
    type: str
    description: str
    code_snippet: str
    suggestion: str


class NPlusOneAnalyzer(ast.NodeVisitor):
    """Analisa AST para detectar padrões N+1."""

    def __init__(self, filename: str, source_code: str):
        self.filename = filename
        self.source_code = source_code
        self.source_lines = source_code.split("\n")
        self.issues: List[NPlusOneIssue] = []
        self.in_loop = False
        self.loop_depth = 0
        self.query_calls: Set[int] = set()
        self.relationship_accesses: List[Dict] = []

    def visit_For(self, node: ast.For):
        """Detecta loops for."""
        self.in_loop = True
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1
        if self.loop_depth == 0:
            self.in_loop = False

    def visit_While(self, node: ast.While):
        """Detecta loops while."""
        self.in_loop = True
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1
        if self.loop_depth == 0:
            self.in_loop = False

    def visit_Attribute(self, node: ast.Attribute):
        """Detecta acesso a atributos (possíveis relacionamentos)."""
        if self.in_loop:
            # Detectar padrões como: obj.relationship
            attr_name = node.attr

            # Relacionamentos comuns
            relationship_patterns = [
                "patients",
                "messages",
                "doctor",
                "user",
                "flow_states",
                "quiz_sessions",
                "quiz_responses",
                "appointments",
                "medications",
                "treatments",
                "notifications",
                "alerts",
                "consents",
            ]

            if attr_name in relationship_patterns:
                code_snippet = self.get_code_snippet(node.lineno)

                # Verificar se não tem eager loading
                if not self.has_eager_loading_nearby(node.lineno):
                    self.issues.append(
                        NPlusOneIssue(
                            file=self.filename,
                            line=node.lineno,
                            column=node.col_offset,
                            severity="high",
                            type="relationship_in_loop",
                            description=f"Acesso a relacionamento '{attr_name}' dentro de loop sem eager loading",
                            code_snippet=code_snippet,
                            suggestion=f"Usar .options(selectinload(Model.{attr_name})) na query",
                        )
                    )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Detecta chamadas de função (queries)."""
        # Detectar chamadas .all(), .first(), .one()
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ["all", "first", "one", "one_or_none"]:
                self.query_calls.add(node.lineno)

                # Se está em função de lista, verificar se tem eager loading
                if self.is_in_list_function():
                    if not self.has_eager_loading_in_query(node):
                        code_snippet = self.get_code_snippet(node.lineno)
                        self.issues.append(
                            NPlusOneIssue(
                                file=self.filename,
                                line=node.lineno,
                                column=node.col_offset,
                                severity="medium",
                                type="list_without_eager_loading",
                                description="Query em função de listagem sem eager loading",
                                code_snippet=code_snippet,
                                suggestion="Adicionar .options(selectinload/joinedload) para relacionamentos usados",
                            )
                        )

        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp):
        """Detecta list comprehensions."""
        # List comprehensions podem causar N+1
        for generator in node.generators:
            if isinstance(generator.iter, ast.Attribute):
                attr_name = generator.iter.attr

                relationship_patterns = [
                    "patients",
                    "messages",
                    "doctor",
                    "user",
                    "flow_states",
                ]

                if attr_name in relationship_patterns:
                    code_snippet = self.get_code_snippet(node.lineno)
                    self.issues.append(
                        NPlusOneIssue(
                            file=self.filename,
                            line=node.lineno,
                            column=node.col_offset,
                            severity="medium",
                            type="comprehension_relationship",
                            description=f"List comprehension acessando relacionamento '{attr_name}'",
                            code_snippet=code_snippet,
                            suggestion="Considerar usar query com aggregation ou eager loading",
                        )
                    )

        self.generic_visit(node)

    def has_eager_loading_nearby(self, line: int, window: int = 20) -> bool:
        """Verifica se há eager loading próximo à linha."""
        start = max(0, line - window)
        end = min(len(self.source_lines), line + window)

        nearby_code = "\n".join(self.source_lines[start:end])

        eager_loading_keywords = [
            "joinedload",
            "selectinload",
            "subqueryload",
            "lazyload",
            "immediateload",
            ".options(",
        ]

        return any(keyword in nearby_code for keyword in eager_loading_keywords)

    def has_eager_loading_in_query(self, node: ast.Call) -> bool:
        """Verifica se a query tem eager loading."""
        # Simples verificação: procurar .options() na mesma expressão
        # Pode ser melhorado com análise mais profunda
        return False  # Conservador: assume que não tem

    def is_in_list_function(self) -> bool:
        """Verifica se está em função de listagem."""
        # Heurística simples: procurar "list" no nome da função
        for line in self.source_lines:
            if "def list_" in line or "def get_all" in line:
                return True
        return False

    def get_code_snippet(self, line: int, context: int = 2) -> str:
        """Obtém snippet de código ao redor da linha."""
        start = max(0, line - context - 1)
        end = min(len(self.source_lines), line + context)

        lines = []
        for i in range(start, end):
            marker = ">>> " if i == line - 1 else "    "
            lines.append(f"{i + 1:4d} {marker}{self.source_lines[i]}")

        return "\n".join(lines)


def analyze_file(filepath: str) -> List[NPlusOneIssue]:
    """Analisa um arquivo Python."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = ast.parse(source_code, filename=filepath)
        analyzer = NPlusOneAnalyzer(filepath, source_code)
        analyzer.visit(tree)

        return analyzer.issues

    except SyntaxError as e:
        print(f"⚠️  Erro de sintaxe em {filepath}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"⚠️  Erro ao analisar {filepath}: {e}", file=sys.stderr)
        return []


def analyze_directory(
    directory: str, patterns: List[str] = None
) -> List[NPlusOneIssue]:
    """Analisa todos os arquivos Python em um diretório."""
    if patterns is None:
        patterns = ["**/*.py"]

    all_issues = []

    for pattern in patterns:
        for filepath in Path(directory).glob(pattern):
            if "__pycache__" in str(filepath):
                continue

            issues = analyze_file(str(filepath))
            all_issues.extend(issues)

    return all_issues


def print_report(issues: List[NPlusOneIssue], suggest: bool = False):
    """Imprime relatório de issues."""
    if not issues:
        print("✅ Nenhum problema N+1 detectado!")
        return

    # Agrupar por severidade
    by_severity = {
        "high": [i for i in issues if i.severity == "high"],
        "medium": [i for i in issues if i.severity == "medium"],
        "low": [i for i in issues if i.severity == "low"],
    }

    print("=" * 80)
    print("🔍 ANÁLISE DE QUERIES N+1 - SISTEMA HORMONIA")
    print("=" * 80)
    print()

    print(f"Total de Issues: {len(issues)}")
    print(f"  🔴 Alta:   {len(by_severity['high'])}")
    print(f"  🟡 Média:  {len(by_severity['medium'])}")
    print(f"  🟢 Baixa:  {len(by_severity['low'])}")
    print()

    for severity in ["high", "medium", "low"]:
        severity_issues = by_severity[severity]
        if not severity_issues:
            continue

        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[severity]
        print(f"\n{icon} Severidade: {severity.upper()}")
        print("-" * 80)

        for idx, issue in enumerate(severity_issues, 1):
            print(f"\n[{idx}] {issue.type}")
            print(f"    Arquivo: {issue.file}:{issue.line}:{issue.column}")
            print(f"    Descrição: {issue.description}")
            print()
            print("    Código:")
            for line in issue.code_snippet.split("\n"):
                print(f"    {line}")

            if suggest:
                print()
                print(f"    💡 Sugestão: {issue.suggestion}")

    print("\n" + "=" * 80)
    print("📊 RESUMO")
    print("=" * 80)

    # Arquivos com mais issues
    files_count: Dict[str, int] = {}
    for issue in issues:
        files_count[issue.file] = files_count.get(issue.file, 0) + 1

    print("\nArquivos com mais problemas:")
    for file, count in sorted(files_count.items(), key=lambda x: x[1], reverse=True)[
        :5
    ]:
        print(f"  {count:2d} issues - {file}")

    # Tipos mais comuns
    types_count: Dict[str, int] = {}
    for issue in issues:
        types_count[issue.type] = types_count.get(issue.type, 0) + 1

    print("\nTipos mais comuns:")
    for issue_type, count in sorted(
        types_count.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  {count:2d} issues - {issue_type}")

    print("\n" + "=" * 80)


def print_json_report(issues: List[NPlusOneIssue]):
    """Imprime relatório em JSON."""
    report = {
        "total_issues": len(issues),
        "by_severity": {
            "high": len([i for i in issues if i.severity == "high"]),
            "medium": len([i for i in issues if i.severity == "medium"]),
            "low": len([i for i in issues if i.severity == "low"]),
        },
        "issues": [asdict(issue) for issue in issues],
    }

    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Analisa código para detectar queries N+1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Análise completa do projeto
  python scripts/analyze_n_plus_one.py

  # Analisar arquivo específico
  python scripts/analyze_n_plus_one.py --file app/services/patient.py

  # Com sugestões de correção
  python scripts/analyze_n_plus_one.py --suggest

  # Output JSON para CI/CD
  python scripts/analyze_n_plus_one.py --format json > n_plus_one_report.json
        """,
    )

    parser.add_argument("--file", help="Analisar arquivo específico")

    parser.add_argument(
        "--dir", default="app", help="Diretório para análise (padrão: app)"
    )

    parser.add_argument(
        "--suggest", action="store_true", help="Mostrar sugestões de correção"
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Formato de output (padrão: text)",
    )

    parser.add_argument(
        "--severity",
        choices=["high", "medium", "low", "all"],
        default="all",
        help="Filtrar por severidade (padrão: all)",
    )

    args = parser.parse_args()

    # Análise
    if args.file:
        issues = analyze_file(args.file)
    else:
        issues = analyze_directory(args.dir)

    # Filtrar por severidade
    if args.severity != "all":
        issues = [i for i in issues if i.severity == args.severity]

    # Output
    if args.format == "json":
        print_json_report(issues)
    else:
        print_report(issues, suggest=args.suggest)

    # Exit code
    high_severity_count = len([i for i in issues if i.severity == "high"])
    if high_severity_count > 0:
        sys.exit(1)  # Falhar CI se tiver issues críticas
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
