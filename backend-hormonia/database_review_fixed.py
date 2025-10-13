#!/usr/bin/env python3
"""
Review completa do banco de dados - VERSÃO CORRIGIDA
Baseada nas tabelas que realmente existem no banco
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
                version,
                description,
                passing_score,
                time_limit_minutes,
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
                except Exception as e:
                    question_count = f"ERRO JSON: {str(e)[:50]}"
                
                print(f"")
                print(f"   📝 {template.name} (v{template.version})")
                print(f"      ID: {template.id}")
                print(f"      Categoria: {template.category}")
                print(f"      Status: {status}")
                print(f"      Perguntas: {question_count}")
                print(f"      Descrição: {template.description}")
                print(f"      Pontuação mínima: {template.passing_score}")
                print(f"      Tempo limite: {template.time_limit_minutes} min")
                print(f"      Criado: {template.created_at}")
                
                # Mostrar algumas perguntas se existirem
                if isinstance(question_count, int) and question_count > 0:
                    try:
                        questions = json.loads(template.questions)
                        print(f"      📋 Exemplos de perguntas:")
                        for i, q in enumerate(questions[:3]):  # Mostrar apenas 3
                            question_text = q.get('question', q.get('text', 'N/A'))[:60]
                            question_type = q.get('type', 'unknown')
                            print(f"        {i+1}. [{question_type}] {question_text}...")
                    except Exception as e:
                        print(f"      ⚠️  Erro ao parsear perguntas: {e}")
        else:
            print("❌ Nenhum quiz template encontrado!")
            
        return len(templates)

def review_flow_template_versions():
    """Revisar versões de templates de flow"""
    
    print(f"\n📋 REVIEW: Flow Template Versions")
    print("-" * 40)
    
    with get_scoped_session() as db:
        # Verificar flow template versions
        result = db.execute(text("""
            SELECT 
                ftv.id,
                ftv.template_name,
                ftv.version_number,
                ftv.description,
                ftv.is_active,
                fk.kind_key,
                fk.display_name as kind_display,
                ftv.created_at
            FROM flow_template_versions ftv
            LEFT JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
            ORDER BY ftv.created_at DESC
        """))
        
        templates = result.fetchall()
        
        if templates:
            print(f"✅ {len(templates)} flow template versions encontrados:")
            
            for template in templates:
                status = "🟢 ATIVO" if template.is_active else "🔴 INATIVO"
                
                print(f"")
                print(f"   🔄 {template.template_name} (v{template.version_number})")
                print(f"      ID: {template.id}")
                print(f"      Tipo: {template.kind_key} ({template.kind_display})")
                print(f"      Status: {status}")
                print(f"      Descrição: {template.description}")
                print(f"      Criado: {template.created_at}")
        else:
            print("❌ Nenhum flow template version encontrado!")
            
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
                qt.name as template_name
            FROM quiz_sessions qs
            LEFT JOIN quiz_templates qt ON qs.quiz_template_id = qt.id
            ORDER BY qs.started_at DESC
            LIMIT 10
        """))
        
        sessions = result.fetchall()
        
        if sessions:
            print(f"✅ {len(sessions)} sessões de quiz recentes:")
            
            for session in sessions:
                print(f"")
                print(f"   🎯 Sessão {session.id}")
                print(f"      Paciente ID: {session.patient_id}")
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

def review_patients():
    """Revisar pacientes no sistema"""
    
    print(f"\n📋 REVIEW: Patients")
    print("-" * 40)
    
    with get_scoped_session() as db:
        # Verificar se tabela patients existe
        try:
            result = db.execute(text("""
                SELECT 
                    COUNT(*) as total_patients,
                    COUNT(CASE WHEN flow_state = 'active' THEN 1 END) as active_patients,
                    COUNT(CASE WHEN flow_state = 'paused' THEN 1 END) as paused_patients,
                    COUNT(CASE WHEN flow_state = 'completed' THEN 1 END) as completed_patients
                FROM patients
            """))
            
            stats = result.fetchone()
            
            print(f"📊 Estatísticas de Pacientes:")
            print(f"   Total: {stats.total_patients}")
            print(f"   Ativos: {stats.active_patients}")
            print(f"   Pausados: {stats.paused_patients}")
            print(f"   Completados: {stats.completed_patients}")
            
            if stats.total_patients > 0:
                # Mostrar alguns pacientes
                result = db.execute(text("""
                    SELECT id, name, email, treatment_type, flow_state, created_at
                    FROM patients
                    ORDER BY created_at DESC
                    LIMIT 5
                """))
                
                patients = result.fetchall()
                
                print(f"\n👥 Últimos 5 pacientes:")
                for patient in patients:
                    print(f"   - {patient.name} ({patient.email})")
                    print(f"     Tratamento: {patient.treatment_type}")
                    print(f"     Estado: {patient.flow_state}")
                    print(f"     Criado: {patient.created_at}")
                    print()
            
            return stats.total_patients
            
        except Exception as e:
            print(f"❌ Tabela patients não existe ou erro: {e}")
            return 0

def review_messages():
    """Revisar mensagens do sistema"""
    
    print(f"\n📋 REVIEW: Messages")
    print("-" * 40)
    
    with get_scoped_session() as db:
        try:
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
            
        except Exception as e:
            print(f"❌ Tabela messages não existe ou erro: {e}")
            return 0

def check_system_readiness():
    """Verificar se o sistema está pronto para uso"""
    
    print(f"\n🔍 VERIFICAÇÃO DE PRONTIDÃO DO SISTEMA")
    print("=" * 50)
    
    issues = []
    warnings = []
    
    with get_scoped_session() as db:
        # 1. Verificar se há quiz templates ativos
        try:
            result = db.execute(text("SELECT COUNT(*) FROM quiz_templates WHERE is_active = true"))
            active_quiz_templates = result.scalar()
            
            if active_quiz_templates == 0:
                issues.append("❌ Nenhum quiz template ativo encontrado")
            else:
                print(f"✅ {active_quiz_templates} quiz templates ativos")
        except:
            issues.append("❌ Tabela quiz_templates não acessível")
        
        # 2. Verificar se há flow template versions ativos
        try:
            result = db.execute(text("SELECT COUNT(*) FROM flow_template_versions WHERE is_active = true"))
            active_flow_templates = result.scalar()
            
            if active_flow_templates == 0:
                warnings.append("⚠️  Nenhum flow template version ativo encontrado")
            else:
                print(f"✅ {active_flow_templates} flow template versions ativos")
        except:
            warnings.append("⚠️  Tabela flow_template_versions não acessível")
        
        # 3. Verificar se há flow kinds ativos
        try:
            result = db.execute(text("SELECT COUNT(*) FROM flow_kinds WHERE is_active = true"))
            active_flow_kinds = result.scalar()
            
            if active_flow_kinds == 0:
                warnings.append("⚠️  Nenhum flow kind ativo encontrado")
            else:
                print(f"✅ {active_flow_kinds} flow kinds ativos")
        except:
            warnings.append("⚠️  Tabela flow_kinds não acessível")
        
        # 4. Verificar se há pacientes
        try:
            result = db.execute(text("SELECT COUNT(*) FROM patients"))
            total_patients = result.scalar()
            
            if total_patients == 0:
                warnings.append("⚠️  Nenhum paciente cadastrado")
            else:
                print(f"✅ {total_patients} pacientes cadastrados")
        except:
            warnings.append("⚠️  Tabela patients não acessível")
        
        # 5. Verificar usuários admin
        try:
            result = db.execute(text("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = true"))
            admin_users = result.scalar()
            
            if admin_users == 0:
                warnings.append("⚠️  Nenhum usuário admin ativo encontrado")
            else:
                print(f"✅ {admin_users} usuários admin ativos")
        except:
            warnings.append("⚠️  Tabela users não acessível")
    
    # Resultado final
    print(f"\n" + "=" * 50)
    
    if issues:
        print(f"❌ PROBLEMAS CRÍTICOS:")
        for issue in issues:
            print(f"   {issue}")
    
    if warnings:
        print(f"\n⚠️  AVISOS:")
        for warning in warnings:
            print(f"   {warning}")
    
    if not issues and not warnings:
        print(f"🎉 SISTEMA PRONTO PARA USO!")
        print(f"   Todos os componentes necessários estão presentes")
    elif not issues:
        print(f"✅ SISTEMA FUNCIONAL!")
        print(f"   Componentes críticos presentes, alguns avisos menores")
    else:
        print(f"🔧 AÇÕES NECESSÁRIAS:")
        print(f"   1. Resolver problemas críticos listados acima")
        print(f"   2. Verificar configuração do banco de dados")
        print(f"   3. Executar migrações se necessário")

def main():
    """Executar review completa do banco"""
    
    print("🔍 REVIEW COMPLETA DO BANCO DE DADOS - VERSÃO CORRIGIDA")
    print("=" * 70)
    
    try:
        # 1. Quiz Templates
        quiz_count = review_quiz_templates()
        
        # 2. Flow Template Versions
        flow_count = review_flow_template_versions()
        
        # 3. Flow Kinds
        kinds_count = review_flow_kinds()
        
        # 4. Quiz Sessions
        sessions_count = review_quiz_sessions()
        
        # 5. Patients
        patients_count = review_patients()
        
        # 6. Messages
        messages_count = review_messages()
        
        # 7. Verificação final
        check_system_readiness()
        
        print(f"\n📊 RESUMO GERAL:")
        print(f"   Quiz Templates: {quiz_count}")
        print(f"   Flow Template Versions: {flow_count}")
        print(f"   Flow Kinds: {kinds_count}")
        print(f"   Quiz Sessions: {sessions_count}")
        print(f"   Patients: {patients_count}")
        print(f"   Messages: {messages_count}")
        
    except Exception as e:
        print(f"❌ Erro durante review: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()