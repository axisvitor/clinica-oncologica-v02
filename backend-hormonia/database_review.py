#!/usr/bin/env python3
"""
Review completa do banco de dados - Quiz Mensal, Perguntas Diárias e Flows
"""
import sys
sys.path.append('.')

from app.database import get_scoped_session
from sqlalchemy import text
import json

def review_quiz_templates():
    """Revisar templates de quiz no banco"""
    
    print("📋 REVIEW: Quiz Templates")
    print("-" * 40)
    
    with get_scoped_session() as db:
        # Verificar quiz templates
        result = db.execute(text("""
            SELECT 
                id, 
                name, 
                category, 
                is_active, 
                questions,
                created_at
            FROM quiz_templates 
            ORDER BY created_at DESC
        """))
        
        templates = result.fetchall()
        
        if templates:
            print(f"✅ {len(templates)} quiz templates encontrados:")
            
            for template in templates:
                status = "🟢 ATIVO" if template.is_active else "🔴 INATIVO"
                
                # Parse questions JSON
                try:
                    questions = json.loads(template.questions) if template.questions else []
                    question_count = len(questions)
                except:
                    question_count = "ERRO JSON"
                
                print(f"")
                print(f"   📝 {template.name}")
                print(f"      ID: {template.id}")
                print(f"      Categoria: {template.category}")
                print(f"      Status: {status}")
                print(f"      Perguntas: {question_count}")
                print(f"      Criado: {template.created_at}")
                
                # Mostrar algumas perguntas se existirem
                if isinstance(question_count, int) and question_count > 0:
                    try:
                        questions = json.loads(template.questions)
                        print(f"      Exemplos de perguntas:")
                        for i, q in enumerate(questions[:3]):  # Mostrar apenas 3
                            question_text = q.get('question', 'N/A')[:50]
                            print(f"        {i+1}. {question_text}...")
                    except:
                        print(f"      ⚠️  Erro ao parsear perguntas")
        else:
            print("❌ Nenhum quiz template encontrado!")
            
        return len(templates)

def review_flow_templates():
    """Revisar templates de flow"""
    
    print(f"\n📋 REVIEW: Flow Templates")
    print("-" * 40)
    
    with get_scoped_session() as db:
        # Verificar flow templates
        result = db.execute(text("""
            SELECT 
                ft.id,
                ft.name,
                ft.description,
                ft.is_active,
                fk.kind_key,
                fk.display_name as kind_display,
                ft.created_at
            FROM flow_templates ft
            LEFT JOIN flow_kinds fk ON ft.flow_kind_id = fk.id
            ORDER BY ft.created_at DESC
        """))
        
        templates = result.fetchall()
        
        if templates:
            print(f"✅ {len(templates)} flow templates encontrados:")
            
            for template in templates:
                status = "🟢 ATIVO" if template.is_active else "🔴 INATIVO"
                
                print(f"")
                print(f"   🔄 {template.name}")
                print(f"      ID: {template.id}")
                print(f"      Tipo: {template.kind_key} ({template.kind_display})")
                print(f"      Status: {status}")
                print(f"      Descrição: {template.description}")
                print(f"      Criado: {template.created_at}")
        else:
            print("❌ Nenhum flow template encontrado!")
            
        return len(templates)

def review_flow_kinds():
    """Revisar tipos de flow disponíveis"""
    
    print(f"\n📋 REVIEW: Flow Kinds")
    print("-" * 40)
    
    with get_scoped_session() as db:
        result = db.execute(text("""
            SELECT 
                id,
                kind_key,
                display_name,
                description,
                is_active,
                created_at
            FROM flow_kinds
            ORDER BY kind_key
        """))
        
        kinds = result.fetchall()
        
        if kinds:
            print(f"✅ {len(kinds)} tipos de flow encontrados:")
            
            for kind in kinds:
                status = "🟢 ATIVO" if kind.is_active else "🔴 INATIVO"
                
                print(f"")
                print(f"   🏷️  {kind.kind_key}")
                print(f"      Nome: {kind.display_name}")
                print(f"      Status: {status}")
                print(f"      Descrição: {kind.description}")
                print(f"      Criado: {kind.created_at}")
        else:
            print("❌ Nenhum flow kind encontrado!")
            
        return len(kinds)

def review_quiz_sessions():
    """Revisar sessões de quiz ativas"""
    
    print(f"\n📋 REVIEW: Quiz Sessions")
    print("-" * 40)
    
    with get_scoped_session() as db:
        # Sessões recentes
        result = db.execute(text("""
            SELECT 
                qs.id,
                qs.patient_id,
                qs.quiz_template_id,
                qs.status,
                qs.started_at,
                qs.completed_at,
                qt.name as template_name,
                p.name as patient_name
            FROM quiz_sessions qs
            LEFT JOIN quiz_templates qt ON qs.quiz_template_id = qt.id
            LEFT JOIN patients p ON qs.patient_id = p.id
            ORDER BY qs.started_at DESC
            LIMIT 10
        """))
        
        sessions = result.fetchall()
        
        if sessions:
            print(f"✅ {len(sessions)} sessões de quiz recentes:")
            
            for session in sessions:
                print(f"")
                print(f"   🎯 Sessão {session.id}")
                print(f"      Paciente: {session.patient_name}")
                print(f"      Template: {session.template_name}")
                print(f"      Status: {session.status}")
                print(f"      Iniciado: {session.started_at}")
                print(f"      Completado: {session.completed_at}")
        else:
            print("ℹ️  Nenhuma sessão de quiz encontrada")
            
        # Estatísticas gerais
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_sessions,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress,
                COUNT(CASE WHEN status = 'abandoned' THEN 1 END) as abandoned
            FROM quiz_sessions
        """))
        
        stats = result.fetchone()
        
        print(f"\n📊 Estatísticas de Quiz Sessions:")
        print(f"   Total: {stats.total_sessions}")
        print(f"   Completadas: {stats.completed}")
        print(f"   Em progresso: {stats.in_progress}")
        print(f"   Abandonadas: {stats.abandoned}")
        
        return stats.total_sessions

def review_quiz_responses():
    """Revisar respostas de quiz"""
    
    print(f"\n📋 REVIEW: Quiz Responses")
    print("-" * 40)
    
    with get_scoped_session() as db:
        # Respostas recentes
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_responses,
                COUNT(DISTINCT patient_id) as unique_patients,
                COUNT(DISTINCT quiz_template_id) as unique_templates,
                MIN(responded_at) as first_response,
                MAX(responded_at) as last_response
            FROM quiz_responses
        """))
        
        stats = result.fetchone()
        
        print(f"📊 Estatísticas de Quiz Responses:")
        print(f"   Total respostas: {stats.total_responses}")
        print(f"   Pacientes únicos: {stats.unique_patients}")
        print(f"   Templates únicos: {stats.unique_templates}")
        print(f"   Primeira resposta: {stats.first_response}")
        print(f"   Última resposta: {stats.last_response}")
        
        # Respostas por template
        result = db.execute(text("""
            SELECT 
                qt.name as template_name,
                COUNT(qr.id) as response_count
            FROM quiz_responses qr
            JOIN quiz_templates qt ON qr.quiz_template_id = qt.id
            GROUP BY qt.id, qt.name
            ORDER BY response_count DESC
            LIMIT 5
        """))
        
        template_stats = result.fetchall()
        
        if template_stats:
            print(f"\n🏆 Top 5 Templates por Respostas:")
            for stat in template_stats:
                print(f"   {stat.template_name}: {stat.response_count} respostas")
        
        return stats.total_responses

def review_patient_flow_states():
    """Revisar estados de flow dos pacientes"""
    
    print(f"\n📋 REVIEW: Patient Flow States")
    print("-" * 40)
    
    with get_scoped_session() as db:
        # Estados de flow
        result = db.execute(text("""
            SELECT 
                pfs.patient_id,
                pfs.flow_template_id,
                pfs.current_step,
                pfs.status,
                pfs.next_scheduled_at,
                ft.name as template_name,
                p.name as patient_name
            FROM patient_flow_states pfs
            LEFT JOIN flow_templates ft ON pfs.flow_template_id = ft.id
            LEFT JOIN patients p ON pfs.patient_id = p.id
            ORDER BY pfs.next_scheduled_at ASC
            LIMIT 10
        """))
        
        states = result.fetchall()
        
        if states:
            print(f"✅ {len(states)} estados de flow ativos:")
            
            for state in states:
                print(f"")
                print(f"   👤 {state.patient_name}")
                print(f"      Template: {state.template_name}")
                print(f"      Step atual: {state.current_step}")
                print(f"      Status: {state.status}")
                print(f"      Próximo: {state.next_scheduled_at}")
        else:
            print("ℹ️  Nenhum estado de flow ativo encontrado")
            
        # Estatísticas por status
        result = db.execute(text("""
            SELECT 
                status,
                COUNT(*) as count
            FROM patient_flow_states
            GROUP BY status
            ORDER BY count DESC
        """))
        
        status_stats = result.fetchall()
        
        if status_stats:
            print(f"\n📊 Estados por Status:")
            for stat in status_stats:
                print(f"   {stat.status}: {stat.count}")
        
        return len(states)

def review_messages():
    """Revisar mensagens do sistema"""
    
    print(f"\n📋 REVIEW: Messages")
    print("-" * 40)
    
    with get_scoped_session() as db:
        # Estatísticas de mensagens
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(CASE WHEN direction = 'outbound' THEN 1 END) as outbound,
                COUNT(CASE WHEN direction = 'inbound' THEN 1 END) as inbound,
                COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent,
                COUNT(CASE WHEN status = 'delivered' THEN 1 END) as delivered,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
            FROM messages
        """))
        
        stats = result.fetchone()
        
        print(f"📊 Estatísticas de Messages:")
        print(f"   Total mensagens: {stats.total_messages}")
        print(f"   Enviadas: {stats.outbound}")
        print(f"   Recebidas: {stats.inbound}")
        print(f"   Status sent: {stats.sent}")
        print(f"   Status delivered: {stats.delivered}")
        print(f"   Status failed: {stats.failed}")
        
        return stats.total_messages

def check_system_readiness():
    """Verificar se o sistema está pronto para uso"""
    
    print(f"\n🔍 VERIFICAÇÃO DE PRONTIDÃO DO SISTEMA")
    print("=" * 50)
    
    issues = []
    
    # 1. Verificar se há quiz templates ativos
    with get_scoped_session() as db:
        result = db.execute(text("SELECT COUNT(*) FROM quiz_templates WHERE is_active = true"))
        active_quiz_templates = result.scalar()
        
        if active_quiz_templates == 0:
            issues.append("❌ Nenhum quiz template ativo encontrado")
        else:
            print(f"✅ {active_quiz_templates} quiz templates ativos")
    
    # 2. Verificar se há flow templates ativos
    with get_scoped_session() as db:
        result = db.execute(text("SELECT COUNT(*) FROM flow_templates WHERE is_active = true"))
        active_flow_templates = result.scalar()
        
        if active_flow_templates == 0:
            issues.append("❌ Nenhum flow template ativo encontrado")
        else:
            print(f"✅ {active_flow_templates} flow templates ativos")
    
    # 3. Verificar se há flow kinds ativos
    with get_scoped_session() as db:
        result = db.execute(text("SELECT COUNT(*) FROM flow_kinds WHERE is_active = true"))
        active_flow_kinds = result.scalar()
        
        if active_flow_kinds == 0:
            issues.append("❌ Nenhum flow kind ativo encontrado")
        else:
            print(f"✅ {active_flow_kinds} flow kinds ativos")
    
    # 4. Verificar se há pacientes
    with get_scoped_session() as db:
        result = db.execute(text("SELECT COUNT(*) FROM patients"))
        total_patients = result.scalar()
        
        if total_patients == 0:
            issues.append("⚠️  Nenhum paciente cadastrado")
        else:
            print(f"✅ {total_patients} pacientes cadastrados")
    
    # Resultado final
    print(f"\n" + "=" * 50)
    
    if issues:
        print(f"⚠️  PROBLEMAS ENCONTRADOS:")
        for issue in issues:
            print(f"   {issue}")
        print(f"\n🔧 AÇÕES NECESSÁRIAS:")
        print(f"   1. Criar/ativar quiz templates")
        print(f"   2. Criar/ativar flow templates")
        print(f"   3. Verificar flow kinds")
        print(f"   4. Cadastrar pacientes de teste")
    else:
        print(f"🎉 SISTEMA PRONTO PARA USO!")
        print(f"   Todos os componentes necessários estão presentes")

def main():
    """Executar review completa do banco"""
    
    print("🔍 REVIEW COMPLETA DO BANCO DE DADOS")
    print("=" * 60)
    
    try:
        # 1. Quiz Templates
        quiz_count = review_quiz_templates()
        
        # 2. Flow Templates
        flow_count = review_flow_templates()
        
        # 3. Flow Kinds
        kinds_count = review_flow_kinds()
        
        # 4. Quiz Sessions
        sessions_count = review_quiz_sessions()
        
        # 5. Quiz Responses
        responses_count = review_quiz_responses()
        
        # 6. Patient Flow States
        states_count = review_patient_flow_states()
        
        # 7. Messages
        messages_count = review_messages()
        
        # 8. Verificação final
        check_system_readiness()
        
        print(f"\n📊 RESUMO GERAL:")
        print(f"   Quiz Templates: {quiz_count}")
        print(f"   Flow Templates: {flow_count}")
        print(f"   Flow Kinds: {kinds_count}")
        print(f"   Quiz Sessions: {sessions_count}")
        print(f"   Quiz Responses: {responses_count}")
        print(f"   Flow States: {states_count}")
        print(f"   Messages: {messages_count}")
        
    except Exception as e:
        print(f"❌ Erro durante review: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()