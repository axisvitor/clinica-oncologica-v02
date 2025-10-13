#!/usr/bin/env python3
"""
Full Database Review
- Lists all tables across ALL non-system schemas (not only public)
- Row counts per table
- Top 3 rows (safe selection)
- Indexes per table
- Foreign keys per table
- Heuristics: flags empty critical tables, missing indexes on FKs
"""
import os
import sys
from typing import List, Tuple, Dict
import psycopg

# Heuristics: critical tables to track emptiness
CRITICAL_TABLES = [
	"patients",
	"patient_flow_states",
	"flow_kinds",
	"flow_template_versions",
	"quiz_templates",
	"quiz_sessions",
	"quiz_responses",
	"messages",
	"whatsapp_messages",
	"whatsapp_instances",
]

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
	print("❌ DATABASE_URL not set")
	sys.exit(1)
if DATABASE_URL.startswith("postgresql+psycopg://"):
	DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

def fetchall(cur, q: str, params: tuple = ()):
	cur.execute(q, params)
	return cur.fetchall()

def main():
	with psycopg.connect(DATABASE_URL) as conn:
		with conn.cursor() as cur:
			print("🔍 FULL DATABASE REVIEW (all non-system schemas)")
			print("=" * 70)

			# All non-system tables (regular + partitioned) across schemas
			tables = fetchall(cur, """
				SELECT n.nspname AS schema_name, c.relname AS table_name
				FROM pg_class c
				JOIN pg_namespace n ON n.oid = c.relnamespace
				WHERE c.relkind IN ('r','p')
				AND n.nspname NOT IN ('pg_catalog','information_schema')
				ORDER BY 1,2
			""")
			all_tables: List[Tuple[str,str]] = [(s, t) for s, t in tables]
			print(f"📋 Tabelas encontradas: {len(all_tables)} (todas as schemas)")
			for s, t in all_tables:
				print(f" - {s}.{t}")

			# Views (informativo)
			views = fetchall(cur, """
				SELECT n.nspname AS schema_name, c.relname AS view_name, c.relkind
				FROM pg_class c
				JOIN pg_namespace n ON n.oid = c.relnamespace
				WHERE c.relkind IN ('v','m')
				AND n.nspname NOT IN ('pg_catalog','information_schema')
				ORDER BY 1,2
			""")
			if views:
				print(f"\n👁️  Views/materialized views: {len(views)}")
				for s, v, k in views:
					kind = "view" if k == 'v' else "matview"
					print(f" - {s}.{v} ({kind})")

			print("\n📊 Contagem por tabela")
			print("-" * 40)
			counts: Dict[Tuple[str,str], int] = {}
			for s, t in all_tables:
				try:
					cur.execute(f"SELECT COUNT(*) FROM {s}.{t}")
					counts[(s,t)] = cur.fetchone()[0]
					print(f"{s}.{t}: {counts[(s,t)]}")
				except Exception as e:
					print(f"{s}.{t}: erro -> {e}")

			print("\n🔎 Amostras (até 3 linhas)")
			print("-" * 40)
			for s, t in all_tables:
				try:
					cur.execute(f"SELECT * FROM {s}.{t} LIMIT 3")
					rows = cur.fetchall()
					cols = [d[0] for d in cur.description]
					if not rows:
						print(f"{s}.{t}: (vazia)")
						continue
					print(f"{s}.{t}:")
					for r in rows:
						print("  ", dict(zip(cols, r)))
				except Exception as e:
					print(f"{s}.{t}: erro -> {e}")

			print("\n🧭 Índices por tabela")
			print("-" * 40)
			for s, t in all_tables:
				idx = fetchall(cur, """
					SELECT indexname, indexdef
					FROM pg_indexes
					WHERE schemaname=%s AND tablename=%s
					ORDER BY indexname
				""", (s, t))
				print(f"{s}.{t}:")
				if not idx:
					print("  (sem índices)")
				else:
					for name, definition in idx:
						print(f"  {name}: {definition}")

			print("\n🔗 Chaves estrangeiras por tabela")
			print("-" * 40)
			for s, t in all_tables:
				fks = fetchall(cur, """
					SELECT
						kcu.column_name,
						ccu.table_name AS foreign_table,
						ccu.column_name AS foreign_column
					FROM information_schema.table_constraints AS tc
					JOIN information_schema.key_column_usage AS kcu
						ON tc.constraint_name = kcu.constraint_name
						AND tc.table_schema = kcu.table_schema
					JOIN information_schema.constraint_column_usage AS ccu
						ON ccu.constraint_name = tc.constraint_name
						AND ccu.table_schema = tc.table_schema
					WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name=%s AND tc.table_schema=%s
				""", (t, s))
				print(f"{s}.{t}:")
				if not fks:
					print("  (sem FKs)")
				else:
					for col, ft, fc in fks:
						print(f"  {col} -> {ft}.{fc}")

			print("\n⚠️ Heurísticas e alertas")
			print("-" * 40)
			# Tabelas críticas vazias
			for ct in CRITICAL_TABLES:
				# procure por ct em qualquer schema
				empties = [(s,t) for (s,t), c in counts.items() if t == ct and c == 0]
				for s, t in empties:
					print(f"❌ Tabela crítica vazia: {s}.{t}")

			# Índices ausentes em colunas que parecem FKs (sufixo _id)
			for s, t in all_tables:
				cols = fetchall(cur, """
					SELECT column_name
					FROM information_schema.columns
					WHERE table_schema=%s AND table_name=%s
				""", (s, t))
				col_names = [c[0] for c in cols]
				fk_like = [c for c in col_names if c.endswith('_id')]
				if not fk_like:
					continue
				idx_cols = fetchall(cur, """
					SELECT indexdef FROM pg_indexes WHERE schemaname=%s AND tablename=%s
				""", (s, t))
				defs = "\n".join([d[0] for d in idx_cols]).replace(" ", "")
				for col in fk_like:
					if f"({col})" not in defs:
						print(f"⚠️ {s}.{t}.{col} parece FK sem índice explícito")

			print("\n✅ Review concluída")

if __name__ == "__main__":
	main()
