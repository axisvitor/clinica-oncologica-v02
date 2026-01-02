"""
Script para verificar os dados da simulação - usando schema real do banco.
"""
import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect(
    "postgresql://neoplasias:imdA4mXfM0IxZuVj778E@database-clinica-neoplasias.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require",
    row_factory=dict_row
)

PATIENT_ID = 'bfa15d69-1fa8-42d4-9cb2-8e51804428b8'

def table_exists(cur, table_name):
    cur.execute('''
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = %s
        )
    ''', (table_name,))
    return cur.fetchone()['exists']

with conn.cursor() as cur:
    # 1. Buscar paciente da simulação
    print('=' * 70)
    print('📋 PACIENTE DA SIMULAÇÃO (tabela: patients)')
    print('=' * 70)
    cur.execute('''
        SELECT id, name, doctor_id, flow_state, current_day, 
               treatment_type, treatment_phase, created_at
        FROM patients 
        WHERE id = %s
    ''', (PATIENT_ID,))
    patient = cur.fetchone()
    if patient:
        print(f"✅ ID: {patient['id']}")
        print(f"✅ Nome: {patient['name']}")
        print(f"   Doctor ID: {patient['doctor_id']}")
        print(f"✅ Flow State: {patient['flow_state']}")
        print(f"✅ Current Day: {patient['current_day']}")
        print(f"   Treatment Type: {patient['treatment_type']}")
        print(f"   Treatment Phase: {patient['treatment_phase']}")
        print(f"   Criado em: {patient['created_at']}")
    else:
        print('❌ Paciente NÃO encontrado com esse ID!')

    # 2. Contar mensagens (tabela: messages)
    print()
    print('=' * 70)
    print('📨 MENSAGENS DO PACIENTE (tabela: messages)')
    print('=' * 70)
    cur.execute('SELECT COUNT(*) as total FROM messages WHERE patient_id = %s', (PATIENT_ID,))
    msg_count = cur.fetchone()['total']
    print(f"Total de mensagens: {msg_count}")
    
    if msg_count > 0:
        # Status das mensagens
        cur.execute('''
            SELECT status, COUNT(*) as count
            FROM messages 
            WHERE patient_id = %s
            GROUP BY status
        ''', (PATIENT_ID,))
        statuses = cur.fetchall()
        print('Status das mensagens:')
        for s in statuses:
            print(f"  - {s['status']}: {s['count']}")
        
        # Últimas 5 mensagens
        print()
        print('Últimas 5 mensagens:')
        cur.execute('''
            SELECT id, type, direction, content, status, created_at
            FROM messages 
            WHERE patient_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        ''', (PATIENT_ID,))
        msgs = cur.fetchall()
        for m in msgs:
            content_preview = (m['content'] or '')[:40] + '...' if m['content'] and len(m['content']) > 40 else m['content']
            print(f"  [{m['direction']}] {m['type']} - {content_preview} ({m['status']})")
    else:
        print('❌ Nenhuma mensagem encontrada para este paciente!')

    # 3. Estatísticas gerais
    print()
    print('=' * 70)
    print('📊 ESTATÍSTICAS GERAIS DO BANCO')
    print('=' * 70)
    
    cur.execute('SELECT COUNT(*) as total FROM patients')
    print(f"Total de pacientes: {cur.fetchone()['total']}")
    
    cur.execute('SELECT COUNT(*) as total FROM messages')
    print(f"Total de mensagens: {cur.fetchone()['total']}")
    
    if table_exists(cur, 'doctors'):
        cur.execute('SELECT COUNT(*) as total FROM doctors')
        print(f"Total de médicos: {cur.fetchone()['total']}")
    
    if table_exists(cur, 'users'):
        cur.execute('SELECT COUNT(*) as total FROM users')
        print(f"Total de users: {cur.fetchone()['total']}")
    
    if table_exists(cur, 'quiz_responses'):
        cur.execute('SELECT COUNT(*) as total FROM quiz_responses')
        print(f"Total de quiz_responses: {cur.fetchone()['total']}")
    
    if table_exists(cur, 'quiz_sessions'):
        cur.execute('SELECT COUNT(*) as total FROM quiz_sessions')
        print(f"Total de quiz_sessions: {cur.fetchone()['total']}")

    # 4. Últimos 5 pacientes criados
    print()
    print('=' * 70)
    print('📋 ÚLTIMOS 5 PACIENTES CRIADOS')
    print('=' * 70)
    cur.execute('''
        SELECT id, name, flow_state, current_day, doctor_id, created_at
        FROM patients 
        ORDER BY created_at DESC
        LIMIT 5
    ''')
    for p in cur.fetchall():
        doc = str(p['doctor_id'])[:8] if p['doctor_id'] else 'None'
        print(f"  {p['name']:30} | state={p['flow_state'] or 'N/A':10} | day={p['current_day'] or 0:3} | doc={doc}")

    # 5. Verificar Flow Schedules
    if table_exists(cur, 'flow_schedules'):
        print()
        print('=' * 70)
        print('📅 FLOW SCHEDULES DO PACIENTE (tabela: flow_schedules)')
        print('=' * 70)
        cur.execute('SELECT COUNT(*) as total FROM flow_schedules WHERE patient_id = %s', (PATIENT_ID,))
        sched_count = cur.fetchone()['total']
        print(f"Total de schedules: {sched_count}")
        if sched_count > 0:
            cur.execute('''
                SELECT id, day_number, scheduled_date, status, message_type, executed_at
                FROM flow_schedules
                WHERE patient_id = %s
                ORDER BY day_number DESC
                LIMIT 5
            ''', (PATIENT_ID,))
            for s in cur.fetchall():
                print(f"  Day {s['day_number']}: {s['scheduled_date']} - {s['status']} ({s['message_type']})")

    # 6. Listar todas as tabelas encontradas
    print()
    print('=' * 70)
    print('� TABELAS NO BANCO DE DADOS')
    print('=' * 70)
    cur.execute('''
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    ''')
    tables = [r['table_name'] for r in cur.fetchall()]
    print(f"Total: {len(tables)} tabelas")
    for t in tables:
        print(f"  - {t}")

conn.close()
print()
print('=' * 70)
print('✅ VERIFICAÇÃO CONCLUÍDA!')
print('=' * 70)
