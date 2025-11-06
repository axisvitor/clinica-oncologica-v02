#!/usr/bin/env python3
"""Inspecionar tabela patient_onboarding_saga diretamente."""

from sqlalchemy import create_engine, text, inspect
from app.config import settings

print("=" * 70)
print("INSPEÇÃO DA TABELA patient_onboarding_saga")
print("=" * 70)

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    # 1. Verificar se a tabela existe
    print("\n=== 1. VERIFICANDO EXISTÊNCIA DA TABELA ===")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if "patient_onboarding_saga" in tables:
        print("✅ Tabela 'patient_onboarding_saga' existe")
        
        # 2. Verificar colunas
        print("\n=== 2. COLUNAS DA TABELA ===")
        columns = inspector.get_columns("patient_onboarding_saga")
        for col in columns:
            print(f"   - {col['name']}: {col['type']}")
        
        # 3. Contar registros
        print("\n=== 3. TOTAL DE REGISTROS ===")
        count_result = conn.execute(text("SELECT COUNT(*) FROM patient_onboarding_saga")).fetchone()
        total = count_result[0]
        print(f"   Total: {total} registros")
        
        # 4. Últimos 5 registros
        print("\n=== 4. ÚLTIMOS 5 REGISTROS ===")
        saga_query = text("""
            SELECT id, patient_id, doctor_id, status, current_step, 
                   retry_count, started_at, completed_at, failed_at,
                   error_message
            FROM patient_onboarding_saga 
            ORDER BY started_at DESC
            LIMIT 5
        """)
        saga_results = conn.execute(saga_query).fetchall()
        
        if saga_results:
            for saga in saga_results:
                print(f"\n   Saga ID: {saga[0]}")
                print(f"   Patient ID: {saga[1]}")
                print(f"   Doctor ID: {saga[2]}")
                print(f"   Status: {saga[3]}")
                print(f"   Current Step: {saga[4]}")
                print(f"   Retry Count: {saga[5]}")
                print(f"   Started: {saga[6]}")
                print(f"   Completed: {saga[7]}")
                print(f"   Failed: {saga[8]}")
                if saga[9]:
                    print(f"   Error: {saga[9][:100]}")
                print("   " + "-" * 60)
        else:
            print("   ⚠️  Nenhum registro encontrado")
        
        # 5. Verificar tipo enum saga_status
        print("\n=== 5. TIPO ENUM saga_status ===")
        enum_query = text("""
            SELECT enumlabel 
            FROM pg_enum 
            WHERE enumtypid = (
                SELECT oid FROM pg_type WHERE typname = 'saga_status'
            )
            ORDER BY enumsortorder
        """)
        try:
            enum_values = conn.execute(enum_query).fetchall()
            if enum_values:
                print("   Valores do enum 'saga_status':")
                for val in enum_values:
                    print(f"      - {val[0]}")
            else:
                print("   ⚠️  Enum 'saga_status' não encontrado")
        except Exception as e:
            print(f"   ⚠️  Erro ao consultar enum: {e}")
        
    else:
        print("❌ Tabela 'patient_onboarding_saga' NÃO EXISTE")
        print("\nTabelas disponíveis:")
        for table in sorted(tables):
            print(f"   - {table}")

print("\n" + "=" * 70)
print("Inspeção completa!")
print("=" * 70)
