#!/usr/bin/env python3
"""
Script completo para extrair informações detalhadas do banco de dados
e gerar documentação atualizada.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, List, Any
import json
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Carregar variáveis de ambiente do arquivo .env
def load_env_file():
    """Carrega variáveis de ambiente do arquivo .env"""
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        print(f"✅ Variáveis de ambiente carregadas de: {env_file}")
    else:
        print(f"⚠️ Arquivo .env não encontrado em: {env_file}")

# Carregar variáveis de ambiente
load_env_file()

async def extract_database_info():
    """Extrai informações completas do banco de dados"""
    
    # Carregar URL do banco de dados do ambiente
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERRO: DATABASE_URL não encontrada nas variáveis de ambiente")
        return None
    
    print(f"Conectando ao banco de dados...")
    print(f"URL: {database_url.split('@')[1] if '@' in database_url else 'URL oculta'}")
    
    # Criar engine assíncrono
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=10,
        max_overflow=20
    )
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    db_info = {
        'extraction_date': datetime.now().isoformat(),
        'database_info': {},
        'tables': {},
        'indexes': {},
        'constraints': {},
        'sequences': {},
        'extensions': {},
        'rls_policies': {},
        'functions': {},
        'triggers': {},
        'views': {},
        'materialized_views': {},
        'enums': {},
        'statistics': {}
    }
    
    try:
        async with async_session() as session:
            print("✅ Conectado com sucesso!")
            
            # 1. Informações básicas do banco
            print("\n📊 Extraindo informações básicas do banco...")
            await extract_basic_database_info(session, db_info)
            
            # 2. Extensões instaladas
            print("\n🔌 Extraindo extensões...")
            await extract_extensions(session, db_info)
            
            # 3. Todas as tabelas
            print("\n📋 Extraindo tabelas...")
            await extract_tables(session, db_info)
            
            # 4. Colunas de todas as tabelas
            print("\n📝 Extraindo colunas...")
            await extract_columns(session, db_info)
            
            # 5. Índices
            print("\n🔍 Extraindo índices...")
            await extract_indexes(session, db_info)
            
            # 6. Constraints
            print("\n🔒 Extraindo constraints...")
            await extract_constraints(session, db_info)
            
            # 7. Sequences
            print("\n🔢 Extraindo sequences...")
            await extract_sequences(session, db_info)
            
            # 8. Políticas RLS
            print("\n🛡️ Extraindo políticas RLS...")
            await extract_rls_policies(session, db_info)
            
            # 9. Funções
            print("\n⚙️ Extraindo funções...")
            await extract_functions(session, db_info)
            
            # 10. Triggers
            print("\n⚡ Extraindo triggers...")
            await extract_triggers(session, db_info)
            
            # 11. Views
            print("\n👁️ Extraindo views...")
            await extract_views(session, db_info)
            
            # 12. Materialized Views
            print("\n📊 Extraindo materialized views...")
            await extract_materialized_views(session, db_info)
            
            # 13. Enums
            print("\n🏷️ Extraindo enums...")
            await extract_enums(session, db_info)
            
            # 14. Estatísticas
            print("\n📈 Extraindo estatísticas...")
            await extract_statistics(session, db_info)
            
            # 15. Contagem de registros por tabela
            print("\n🔢 Contando registros...")
            await extract_record_counts(session, db_info)
            
            print("\n✅ Extração concluída com sucesso!")
            
    except Exception as e:
        print(f"❌ Erro durante extração: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        await engine.dispose()
    
    return db_info

async def extract_basic_database_info(session, db_info):
    """Extrai informações básicas do banco"""
    result = await session.execute(text("""
        SELECT 
            current_database() as database_name,
            version() as version,
            current_user as current_user,
            current_schema() as current_schema,
            inet_server_addr() as server_ip,
            inet_server_port() as server_port
    """))
    
    row = result.fetchone()
    if row:
        db_info['database_info'] = {
            'name': row.database_name,
            'version': row.version,
            'current_user': row.current_user,
            'current_schema': row.current_schema,
            'server_ip': str(row.server_ip) if row.server_ip else None,
            'server_port': row.server_port
        }

async def extract_extensions(session, db_info):
    """Extrai informações sobre extensões"""
    result = await session.execute(text("""
        SELECT 
            extname as name,
            extversion as version,
            extrelocatable as relocatable,
            extnamespace::regnamespace as schema,
            extconfig as config
        FROM pg_extension
        ORDER BY extname
    """))
    
    extensions = []
    for row in result:
        extensions.append({
            'name': row.name,
            'version': row.version,
            'relocatable': row.relocatable,
            'schema': row.schema,
            'config': row.config
        })
    
    db_info['extensions'] = extensions

async def extract_tables(session, db_info):
    """Extrai informações sobre todas as tabelas"""
    result = await session.execute(text("""
        SELECT 
            t.table_schema,
            t.table_name,
            t.table_type,
            obj_description(c.oid) as comment,
            pg_size_pretty(pg_total_relation_size(c.oid)) as size,
            pg_total_relation_size(c.oid) as size_bytes
        FROM information_schema.tables t
        LEFT JOIN pg_class c ON c.relname = t.table_name
        LEFT JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.table_schema
        WHERE t.table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY t.table_schema, t.table_name
    """))
    
    tables = {}
    for row in result:
        schema = row.table_schema
        table_name = row.table_name
        
        tables[f"{schema}.{table_name}"] = {
            'schema': schema,
            'name': table_name,
            'type': row.table_type,
            'comment': row.comment,
            'size': row.size,
            'size_bytes': row.size_bytes,
            'columns': [],
            'indexes': [],
            'constraints': [],
            'row_count': 0
        }
    
    db_info['tables'] = tables

async def extract_columns(session, db_info):
    """Extrai informações sobre colunas de todas as tabelas"""
    result = await session.execute(text("""
        SELECT 
            c.table_schema,
            c.table_name,
            c.column_name,
            c.ordinal_position,
            c.column_default,
            c.is_nullable,
            c.data_type,
            c.character_maximum_length,
            c.numeric_precision,
            c.numeric_scale,
            c.udt_schema,
            c.udt_name,
            col_description(pgc.oid, c.ordinal_position) as comment
        FROM information_schema.columns c
        LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
        LEFT JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = c.table_schema
        WHERE c.table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY c.table_schema, c.table_name, c.ordinal_position
    """))
    
    for row in result:
        table_key = f"{row.table_schema}.{row.table_name}"
        if table_key in db_info['tables']:
            column = {
                'name': row.column_name,
                'position': row.ordinal_position,
                'default': row.column_default,
                'nullable': row.is_nullable == 'YES',
                'data_type': row.data_type,
                'max_length': row.character_maximum_length,
                'precision': row.numeric_precision,
                'scale': row.numeric_scale,
                'udt_schema': row.udt_schema,
                'udt_name': row.udt_name,
                'comment': row.comment
            }
            db_info['tables'][table_key]['columns'].append(column)

async def extract_indexes(session, db_info):
    """Extrai informações sobre índices"""
    result = await session.execute(text("""
        SELECT 
            schemaname as schema_name,
            tablename as table_name,
            indexname as index_name,
            indexdef as index_definition,
            'index' as index_type
        FROM pg_indexes
        WHERE schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schemaname, tablename, indexname
    """))
    
    indexes = {}
    for row in result:
        table_key = f"{row.schema_name}.{row.table_name}"
        
        index_info = {
            'schema': row.schema_name,
            'table': row.table_name,
            'name': row.index_name,
            'definition': row.index_definition,
            'type': row.index_type
        }
        
        indexes[row.index_name] = index_info
        
        if table_key in db_info['tables']:
            db_info['tables'][table_key]['indexes'].append(index_info)
    
    db_info['indexes'] = indexes

async def extract_constraints(session, db_info):
    """Extrai informações sobre constraints"""
    result = await session.execute(text("""
        SELECT 
            tc.constraint_schema,
            tc.constraint_name,
            tc.table_name,
            tc.constraint_type,
            tc.is_deferrable,
            tc.initially_deferred,
            rc.match_option,
            rc.update_rule,
            rc.delete_rule,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            kcu.column_name,
            kcu.ordinal_position
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage ccu 
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        LEFT JOIN information_schema.referential_constraints rc 
            ON tc.constraint_name = rc.constraint_name
            AND tc.constraint_schema = rc.constraint_schema
        WHERE tc.table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY tc.table_schema, tc.table_name, tc.constraint_name, kcu.ordinal_position
    """))
    
    constraints = {}
    for row in result:
        constraint_key = f"{row.constraint_schema}.{row.constraint_name}"
        
        if constraint_key not in constraints:
            constraints[constraint_key] = {
                'schema': row.constraint_schema,
                'name': row.constraint_name,
                'table': row.table_name,
                'type': row.constraint_type,
                'deferrable': row.is_deferrable == 'YES',
                'initially_deferred': row.initially_deferred == 'YES',
                'columns': [],
                'foreign_table': row.foreign_table_name,
                'foreign_column': row.foreign_column_name,
                'match_option': row.match_option,
                'update_rule': row.update_rule,
                'delete_rule': row.delete_rule
            }
        
        constraints[constraint_key]['columns'].append(row.column_name)
        
        # Adicionar à tabela
        table_key = f"{row.constraint_schema}.{row.table_name}"
        if table_key in db_info['tables']:
            if constraint_key not in [c['name'] for c in db_info['tables'][table_key]['constraints']]:
                db_info['tables'][table_key]['constraints'].append(constraints[constraint_key])
    
    db_info['constraints'] = constraints

async def extract_sequences(session, db_info):
    """Extrai informações sobre sequences"""
    result = await session.execute(text("""
        SELECT 
            sequence_schema,
            sequence_name,
            data_type,
            start_value,
            minimum_value,
            maximum_value,
            increment,
            cycle_option
        FROM information_schema.sequences
        WHERE sequence_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY sequence_schema, sequence_name
    """))
    
    sequences = {}
    for row in result:
        key = f"{row.sequence_schema}.{row.sequence_name}"
        sequences[key] = {
            'schema': row.sequence_schema,
            'name': row.sequence_name,
            'data_type': row.data_type,
            'start_value': row.start_value,
            'minimum_value': row.minimum_value,
            'maximum_value': row.maximum_value,
            'increment': row.increment,
            'cycle_option': row.cycle_option
        }
    
    db_info['sequences'] = sequences

async def extract_rls_policies(session, db_info):
    """Extrai informações sobre políticas RLS"""
    result = await session.execute(text("""
        SELECT 
            schemaname as schema_name,
            tablename as table_name,
            policyname as policy_name,
            permissive as is_permissive,
            roles as applicable_roles,
            cmd as command_type,
            qual as using_expression,
            with_check as with_check_expression
        FROM pg_policies
        WHERE schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schemaname, tablename, policyname
    """))
    
    policies = {}
    for row in result:
        table_key = f"{row.schema_name}.{row.table_name}"
        policy_key = f"{table_key}.{row.policy_name}"
        
        policy = {
            'schema': row.schema_name,
            'table': row.table_name,
            'name': row.policy_name,
            'permissive': row.is_permissive,
            'roles': row.applicable_roles,
            'command': row.command_type,
            'using': row.using_expression,
            'with_check': row.with_check_expression
        }
        
        policies[policy_key] = policy
        
        if table_key in db_info['tables']:
            if 'rls_policies' not in db_info['tables'][table_key]:
                db_info['tables'][table_key]['rls_policies'] = []
            db_info['tables'][table_key]['rls_policies'].append(policy)
    
    db_info['rls_policies'] = policies

async def extract_functions(session, db_info):
    """Extrai informações sobre funções"""
    result = await session.execute(text("""
        SELECT 
            n.nspname as schema_name,
            p.proname as function_name,
            pg_get_function_arguments(p.oid) as arguments,
            pg_get_function_result(p.oid) as return_type,
            p.prokind as function_type,
            p.provolatile as volatility,
            p.prosrc as source_code,
            obj_description(p.oid) as description
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY n.nspname, p.proname
    """))
    
    functions = {}
    for row in result:
        key = f"{row.schema_name}.{row.function_name}"
        functions[key] = {
            'schema': row.schema_name,
            'name': row.function_name,
            'arguments': row.arguments,
            'return_type': row.return_type,
            'type': row.function_type,
            'volatility': row.volatility,
            'source_code': row.source_code,
            'description': row.description
        }
    
    db_info['functions'] = functions

async def extract_triggers(session, db_info):
    """Extrai informações sobre triggers"""
    result = await session.execute(text("""
        SELECT 
            event_object_schema as table_schema,
            event_object_table as table_name,
            trigger_name,
            action_condition,
            action_statement,
            action_timing,
            action_orientation,
            event_manipulation
        FROM information_schema.triggers
        WHERE trigger_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY table_schema, table_name, trigger_name
    """))
    
    triggers = {}
    for row in result:
        table_key = f"{row.table_schema}.{row.table_name}"
        trigger_key = f"{table_key}.{row.trigger_name}"
        
        trigger = {
            'schema': row.table_schema,
            'table': row.table_name,
            'name': row.trigger_name,
            'condition': row.action_condition,
            'statement': row.action_statement,
            'timing': row.action_timing,
            'orientation': row.action_orientation,
            'event': row.event_manipulation
        }
        
        triggers[trigger_key] = trigger
        
        if table_key in db_info['tables']:
            if 'triggers' not in db_info['tables'][table_key]:
                db_info['tables'][table_key]['triggers'] = []
            db_info['tables'][table_key]['triggers'].append(trigger)
    
    db_info['triggers'] = triggers

async def extract_views(session, db_info):
    """Extrai informações sobre views"""
    result = await session.execute(text("""
        SELECT 
            table_schema,
            table_name,
            view_definition,
            is_updatable,
            is_insertable_into,
            is_trigger_updatable,
            is_trigger_deletable,
            is_trigger_insertable_into
        FROM information_schema.views
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY table_schema, table_name
    """))
    
    views = {}
    for row in result:
        key = f"{row.table_schema}.{row.table_name}"
        views[key] = {
            'schema': row.table_schema,
            'name': row.table_name,
            'definition': row.view_definition,
            'updatable': row.is_updatable == 'YES',
            'insertable': row.is_insertable_into == 'YES',
            'trigger_updatable': row.is_trigger_updatable == 'YES',
            'trigger_deletable': row.is_trigger_deletable == 'YES',
            'trigger_insertable': row.is_trigger_insertable_into == 'YES'
        }
    
    db_info['views'] = views

async def extract_materialized_views(session, db_info):
    """Extrai informações sobre materialized views"""
    result = await session.execute(text("""
        SELECT 
            schemaname as schema_name,
            matviewname as view_name,
            definition,
            ispopulated as is_populated
        FROM pg_matviews
        WHERE schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schemaname, matviewname
    """))
    
    mat_views = {}
    for row in result:
        key = f"{row.schema_name}.{row.view_name}"
        mat_views[key] = {
            'schema': row.schema_name,
            'name': row.view_name,
            'definition': row.definition,
            'is_populated': row.is_populated
        }
    
    db_info['materialized_views'] = mat_views

async def extract_enums(session, db_info):
    """Extrai informações sobre enums"""
    result = await session.execute(text("""
        SELECT 
            n.nspname as schema_name,
            t.typname as enum_name,
            e.enumlabel as enum_value,
            e.enumsortorder as sort_order
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY n.nspname, t.typname, e.enumsortorder
    """))
    
    enums = {}
    for row in result:
        key = f"{row.schema_name}.{row.enum_name}"
        if key not in enums:
            enums[key] = {
                'schema': row.schema_name,
                'name': row.enum_name,
                'values': []
            }
        enums[key]['values'].append({
            'value': row.enum_value,
            'sort_order': row.sort_order
        })
    
    db_info['enums'] = enums

async def extract_statistics(session, db_info):
    """Extrai estatísticas do banco"""
    result = await session.execute(text("""
        SELECT 
            schemaname,
            tablename,
            attname,
            n_distinct,
            correlation,
            most_common_vals,
            most_common_freqs
        FROM pg_stats
        WHERE schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schemaname, tablename, attname
    """))
    
    stats = {}
    for row in result:
        table_key = f"{row.schemaname}.{row.tablename}"
        if table_key not in stats:
            stats[table_key] = {}
        
        stats[table_key][row.attname] = {
            'n_distinct': row.n_distinct,
            'correlation': row.correlation,
            'most_common_vals': row.most_common_vals,
            'most_common_freqs': row.most_common_freqs
        }
    
    db_info['statistics'] = stats

async def extract_record_counts(session, db_info):
    """Conta registros em cada tabela"""
    for table_key, table_info in db_info['tables'].items():
        if table_info['type'] == 'BASE TABLE':
            try:
                result = await session.execute(text(f"""
                    SELECT COUNT(*) as count FROM {table_key}
                """))
                count = result.scalar()
                db_info['tables'][table_key]['row_count'] = count
            except Exception as e:
                print(f"  ⚠️ Erro ao contar registros em {table_key}: {e}")
                db_info['tables'][table_key]['row_count'] = -1

def save_database_info(db_info, filename='database_complete_info.json'):
    """Salva as informações do banco em um arquivo JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(db_info, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 Informações salvas em: {filename}")

def print_summary(db_info):
    """Imprime um resumo das informações extraídas"""
    print("\n" + "="*80)
    print("📊 RESUMO DO BANCO DE DADOS")
    print("="*80)
    
    print(f"📅 Data de Extração: {db_info['extraction_date']}")
    print(f"🗄️ Banco: {db_info['database_info']['name']}")
    print(f"🔧 Versão: {db_info['database_info']['version'].split(',')[0]}")
    
    print(f"\n📋 Tabelas: {len(db_info['tables'])}")
    print(f"🔍 Índices: {len(db_info['indexes'])}")
    print(f"🔒 Constraints: {len(db_info['constraints'])}")
    print(f"🛡️ Políticas RLS: {len(db_info['rls_policies'])}")
    print(f"⚙️ Funções: {len(db_info['functions'])}")
    print(f"⚡ Triggers: {len(db_info['triggers'])}")
    print(f"👁️ Views: {len(db_info['views'])}")
    print(f"📊 Materialized Views: {len(db_info['materialized_views'])}")
    print(f"🏷️ Enums: {len(db_info['enums'])}")
    print(f"🔌 Extensões: {len(db_info['extensions'])}")
    
    # Tabelas com mais registros
    tables_with_records = [(k, v['row_count']) for k, v in db_info['tables'].items() if v['row_count'] > 0]
    tables_with_records.sort(key=lambda x: x[1], reverse=True)
    
    if tables_with_records:
        print(f"\n📈 Top 10 tabelas com mais registros:")
        for i, (table, count) in enumerate(tables_with_records[:10], 1):
            print(f"  {i:2d}. {table}: {count:,} registros")
    
    # Tabelas maiores (tamanho)
    tables_with_size = [(k, v['size_bytes']) for k, v in db_info['tables'].items() if v['size_bytes']]
    tables_with_size.sort(key=lambda x: x[1], reverse=True)
    
    if tables_with_size:
        print(f"\n💾 Top 10 tabelas maiores:")
        for i, (table, size_bytes) in enumerate(tables_with_size[:10], 1):
            size_mb = size_bytes / (1024 * 1024)
            print(f"  {i:2d}. {table}: {size_mb:.2f} MB")

async def main():
    """Função principal"""
    print("🚀 Iniciando extração completa do banco de dados...")
    print("="*80)
    
    # Extrair informações
    db_info = await extract_database_info()
    
    if db_info:
        # Salvar em JSON
        save_database_info(db_info)
        
        # Imprimir resumo
        print_summary(db_info)
        
        return db_info
    else:
        print("❌ Falha na extração das informações")
        return None

if __name__ == "__main__":
    # Configurar event loop compatível com Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
