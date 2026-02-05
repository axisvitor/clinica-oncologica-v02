"""
Script para limpar pacientes de teste do banco de dados.
"""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

with conn.cursor() as cur:
    # 1. Identificar pacientes de teste (nome contém "Sim30" ou "Simulação" ou "Teste")
    print('=' * 70)
    print('🔍 PACIENTES DE TESTE IDENTIFICADOS')
    print('=' * 70)
    
    cur.execute('''
        SELECT id, name, created_at
        FROM patients 
        WHERE name LIKE '%Sim30%' 
           OR name LIKE '%Simulação%'
           OR name LIKE '%simulacao%'
           OR name LIKE '%Teste%'
           OR name LIKE '%teste%'
        ORDER BY created_at DESC
    ''')
    test_patients = cur.fetchall()
    
    if not test_patients:
        print("Nenhum paciente de teste encontrado.")
    else:
        print(f"Total: {len(test_patients)} pacientes de teste\n")
        for p in test_patients:
            print(f"  [{p['id']}] {p['name']} - {p['created_at']}")
        
        patient_ids = [str(p['id']) for p in test_patients]
        
        # 2. Contar registros relacionados
        print('\n' + '=' * 70)
        print('📊 REGISTROS RELACIONADOS QUE SERÃO DELETADOS')
        print('=' * 70)
        
        # Mensagens
        cur.execute('''
            SELECT COUNT(*) as total FROM messages WHERE patient_id = ANY(%s::uuid[])
        ''', (patient_ids,))
        msg_count = cur.fetchone()['total']
        print(f"Mensagens: {msg_count}")
        
        # Sagas
        cur.execute('''
            SELECT COUNT(*) as total FROM patient_onboarding_saga WHERE patient_id = ANY(%s::uuid[])
        ''', (patient_ids,))
        saga_count = cur.fetchone()['total']
        print(f"Sagas: {saga_count}")
        
        # Flow schedules (se existir)
        cur.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'flow_schedules'
            )
        ''')
        if cur.fetchone()['exists']:
            cur.execute('''
                SELECT COUNT(*) as total FROM flow_schedules WHERE patient_id = ANY(%s::uuid[])
            ''', (patient_ids,))
            flow_count = cur.fetchone()['total']
            print(f"Flow Schedules: {flow_count}")
        
        # 3. Executar deleção
        print('\n' + '=' * 70)
        print('🗑️ EXECUTANDO LIMPEZA...')
        print('=' * 70)
        
        # Deletar mensagens primeiro (FK)
        cur.execute('''
            DELETE FROM messages WHERE patient_id = ANY(%s::uuid[])
        ''', (patient_ids,))
        print(f"✅ Mensagens deletadas: {cur.rowcount}")
        
        # Deletar sagas
        cur.execute('''
            DELETE FROM patient_onboarding_saga WHERE patient_id = ANY(%s::uuid[])
        ''', (patient_ids,))
        print(f"✅ Sagas deletadas: {cur.rowcount}")
        
        # Deletar flow_schedules se existir
        cur.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'flow_schedules'
            )
        ''')
        if cur.fetchone()['exists']:
            cur.execute('''
                DELETE FROM flow_schedules WHERE patient_id = ANY(%s::uuid[])
            ''', (patient_ids,))
            print(f"✅ Flow Schedules deletados: {cur.rowcount}")
        
        # Deletar pacientes
        cur.execute('''
            DELETE FROM patients WHERE id = ANY(%s::uuid[])
        ''', (patient_ids,))
        print(f"✅ Pacientes deletados: {cur.rowcount}")
        
        # Commit
        conn.commit()
        print("\n✅ LIMPEZA CONCLUÍDA COM SUCESSO!")

conn.close()
