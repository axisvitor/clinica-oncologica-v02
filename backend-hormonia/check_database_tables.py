#!/usr/bin/env python3
"""
Auditoria rápida do banco: tabelas, enums e metadados críticos.

Executa consultas de verificação usando a sessão do backend (get_scoped_session).
Este script fornece uma visão geral rápida do estado do banco de dados,
incluindo estrutura de tabelas, enums e contagens de registros.
"""

from __future__ import annotations

import json
from typing import Iterable

from sqlalchemy import text

from app.database import get_scoped_session


def _print_header(title: str) -> None:
    """Imprime um cabeçalho formatado com linha separadora."""
    bar = "-" * len(title)
    print(f"\n{title}\n{bar}")


def list_tables() -> list[str]:
    """Lista todas as tabelas no schema público do banco de dados.
    
    Returns:
        Lista com nomes das tabelas ordenadas alfabeticamente.
    """
    _print_header("Tabelas existentes")

    with get_scoped_session() as db:
        result = db.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
        )

        tables = [row[0] for row in result.fetchall()]

        print(f"Total: {len(tables)}\n")
        for name in tables:
            print(f"  • {name}")

    return tables


def list_columns(table: str) -> list[tuple[str, str, str]]:
    """Retorna informações sobre as colunas de uma tabela.
    
    Args:
        table: Nome da tabela para analisar.
        
    Returns:
        Lista de tuplas com (nome_coluna, tipo_dados, nullable).
    """
    with get_scoped_session() as db:
        result = db.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                ORDER BY ordinal_position
                """
            ),
            {"table": table},
        )
        return result.fetchall()


def check_patients_columns() -> None:
    """Verifica e exibe as colunas da tabela patients.
    
    Destaca especialmente as colunas de metadados JSONB que são
    importantes para o funcionamento do sistema.
    """
    _print_header("Colunas em patients")
    columns = list_columns("patients")
    wanted = {"patient_metadata", "metadata"}

    for name, data_type, nullable in columns:
        flag = "[OK]" if name in wanted else "    "
        nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
        print(f"{flag} {name:<20} {data_type:<20} {nullable_str}")

    missing = wanted - {col[0] for col in columns}
    if missing:
        print("\n[WARN] Colunas ausentes:", ", ".join(sorted(missing)))


def check_enum(enum_name: str) -> None:
    """Lista os valores de um enum PostgreSQL.
    
    Args:
        enum_name: Nome do tipo enum a ser consultado.
    """
    _print_header(f"Enum {enum_name}")

    with get_scoped_session() as db:
        result = db.execute(text(f"SELECT unnest(enum_range(NULL::{enum_name}))"))
        values = [row[0] for row in result.fetchall()]

    for value in values:
        print(f"  • {value}")


def check_quiz_delivery_attempts(limit: int = 10) -> None:
    """Mostra metadados relevantes das últimas sessões de quiz.
    
    Analisa os dados de tentativas de entrega armazenados no campo
    session_metadata da tabela quiz_sessions.
    
    Args:
        limit: Número máximo de registros a exibir.
    """
    _print_header("quiz_sessions.delivery_attempts (últimos registros)")

    query = text(
        """
        SELECT id,
               started_at,
               session_metadata ->> 'last_delivery_status' AS last_status,
               session_metadata ->> 'last_delivery_method' AS last_method,
               session_metadata -> 'delivery_attempts' AS attempts
        FROM quiz_sessions
        ORDER BY updated_at DESC
        LIMIT :limit
        """
    )

    with get_scoped_session() as db:
        rows = db.execute(query, {"limit": limit}).fetchall()

    if not rows:
        print("Nenhum registro encontrado.")
        return

    for row in rows:
        attempts: Iterable | None = row.attempts if isinstance(row.attempts, list) else None
        print(f"\nSessão: {row.id}")
        print(f"  started_at: {row.started_at}")
        print(f"  last_status: {row.last_status}")
        print(f"  last_method: {row.last_method}")
        if attempts:
            pretty = json.dumps(attempts, indent=2, ensure_ascii=False)
            print("  attempts:")
            print(pretty)
        else:
            print("  attempts: []")


def check_counts(tables: Iterable[str]) -> None:
    """Mostra quantidade de registros das tabelas principais.
    
    Args:
        tables: Lista de nomes de tabelas para contar registros.
    """
    _print_header("Contagem de registros")

    with get_scoped_session() as db:
        for table in tables:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar_one()
                print(f"  • {table:<25} {count}")
            except Exception as exc:  # pylint: disable=broad-except
                print(f"  • {table:<25} ERRO ({exc})")


def main() -> None:
    """Função principal que executa a auditoria completa do banco de dados."""
    try:
        tables = list_tables()

        # Verifica estrutura da tabela patients
        check_patients_columns()
        
        # Verifica enums críticos do sistema
        check_enum("flow_state")
        check_enum("message_type")
        check_enum("message_status")
        
        # Conta registros das tabelas principais
        important_tables = [
            "patients",
            "patient_flow_states",
            "messages",
            "quiz_templates",
            "quiz_sessions",
            "quiz_responses",
            "flow_template_versions",
            "users",
        ]
        check_counts(important_tables)

        print("\n[SUCCESS] Auditoria concluída com sucesso.")
        print(f"Total de tabelas analisadas: {len(tables)}")
        
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n[ERROR] Erro durante a auditoria: {exc}")
        raise


if __name__ == "__main__":
    main()