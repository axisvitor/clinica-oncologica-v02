#!/usr/bin/env python3
"""
Script para popular o banco de dados com templates de flows e quiz.

Este script lê os arquivos YAML da pasta app/templates e popula as tabelas:
- flow_template_versions (flows diários)
- quiz_templates (quiz mensal)
- message_templates (mensagens de WhatsApp)
"""
import sys
import os
from pathlib import Path
import yaml
import json
from datetime import datetime
from uuid import uuid4

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import settings

# Configuração do banco
DATABASE_URL = settings.DATABASE_URL.replace('+psycopg', '')  # Remove psycopg3 driver
engine = create_engine(DATABASE_URL)


def load_yaml_template(file_path: Path) -> dict:
    """Carrega um template YAML."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def populate_flow_templates(session: Session):
    """Popula flow_template_versions com templates de flows diários."""
    print("\n📋 Populando Flow Templates...")
    
    templates_dir = Path(__file__).parent.parent / 'app' / 'templates' / 'flows'
    flow_files = [
        'initial_15_days.yaml',
        'days_16_45.yaml',
        'monthly_recurring.yaml'
    ]
    
    for flow_file in flow_files:
        file_path = templates_dir / flow_file
        if not file_path.exists():
            print(f"  ⚠️  Arquivo não encontrado: {flow_file}")
            continue
        
        print(f"  📄 Processando: {flow_file}")
        template_data = load_yaml_template(file_path)
        
        # Verificar se já existe
        check_query = text("""
            SELECT id FROM flow_template_versions 
            WHERE template_name = :name AND version = :version
        """)
        existing = session.execute(
            check_query,
            {"name": template_data['name'], "version": template_data['version']}
        ).first()
        
        if existing:
            print(f"    ℹ️  Template já existe: {template_data['name']} v{template_data['version']}")
            continue
        
        # Inserir novo template
        insert_query = text("""
            INSERT INTO flow_template_versions (
                id, template_name, version, description, 
                template_data, is_active, created_at, updated_at
            ) VALUES (
                :id, :name, :version, :description,
                :template_data, :is_active, :created_at, :updated_at
            )
        """)
        
        template_id = str(uuid4())
        now = datetime.utcnow()
        
        session.execute(insert_query, {
            "id": template_id,
            "name": template_data['name'],
            "version": template_data['version'],
            "description": template_data.get('description', ''),
            "template_data": json.dumps(template_data, ensure_ascii=False),
            "is_active": True,
            "created_at": now,
            "updated_at": now
        })
        
        print(f"    ✅ Template criado: {template_data['name']} v{template_data['version']}")
    
    session.commit()
    print("  ✅ Flow templates populados com sucesso!")


def populate_quiz_templates(session: Session):
    """Popula quiz_templates com template de quiz mensal."""
    print("\n📋 Populando Quiz Templates...")
    
    template_file = Path(__file__).parent.parent / 'app' / 'templates' / 'quiz' / 'monthly_comprehensive.yaml'
    
    if not template_file.exists():
        print("  ⚠️  Arquivo monthly_comprehensive.yaml não encontrado")
        return
    
    print(f"  📄 Processando: monthly_comprehensive.yaml")
    template_data = load_yaml_template(template_file)
    
    # Verificar se já existe
    check_query = text("""
        SELECT id FROM quiz_templates 
        WHERE name = :name AND version = :version
    """)
    existing = session.execute(
        check_query,
        {"name": template_data['name'], "version": template_data['version']}
    ).first()
    
    if existing:
        print(f"    ℹ️  Quiz template já existe: {template_data['name']} v{template_data['version']}")
        return
    
    # Inserir novo template
    insert_query = text("""
        INSERT INTO quiz_templates (
            id, name, version, description, questions,
            is_active, created_at, updated_at
        ) VALUES (
            :id, :name, :version, :description, :questions,
            :is_active, :created_at, :updated_at
        )
    """)
    
    template_id = str(uuid4())
    now = datetime.utcnow()
    
    session.execute(insert_query, {
        "id": template_id,
        "name": template_data['name'],
        "version": template_data['version'],
        "description": template_data.get('description', ''),
        "questions": json.dumps(template_data['questions'], ensure_ascii=False),
        "is_active": template_data.get('is_active', True),
        "created_at": now,
        "updated_at": now
    })
    
    session.commit()
    print(f"    ✅ Quiz template criado: {template_data['name']} v{template_data['version']}")
    print("  ✅ Quiz templates populados com sucesso!")


def populate_message_templates(session: Session):
    """Popula message_templates com mensagens de WhatsApp."""
    print("\n📋 Populando Message Templates...")
    
    # Templates de mensagens comuns
    templates = [
        {
            "name": "welcome_message",
            "content": "Olá {patient_name}! 👋\n\nSeja muito bem-vinda! Sou a Hormon[IA], sua assistente pessoal nessa jornada. Estou aqui para te apoiar, organizar tudo e tornar seu dia a dia mais leve. 💜\n\nVamos juntas? 🌸",
            "variables": ["patient_name"],
            "category": "onboarding"
        },
        {
            "name": "daily_checkin",
            "content": "Bom dia, {patient_name}! ☀️\n\nComo você está se sentindo hoje?",
            "variables": ["patient_name"],
            "category": "daily"
        },
        {
            "name": "medication_reminder",
            "content": "Oi {patient_name}! ⏰\n\nLembrete carinhoso: hora de tomar sua medicação. 💊\n\nJá tomou?",
            "variables": ["patient_name"],
            "category": "reminder"
        },
        {
            "name": "quiz_invitation",
            "content": "Olá {patient_name}! 📝\n\nChegou a hora do nosso quiz mensal! É rapidinho e vai me ajudar a te apoiar melhor.\n\nAcesse aqui: {quiz_link}\n\nVálido por 72 horas. 💜",
            "variables": ["patient_name", "quiz_link"],
            "category": "quiz"
        },
        {
            "name": "appointment_reminder",
            "content": "Oi {patient_name}! 📅\n\nLembrete: você tem consulta amanhã às {appointment_time}.\n\nNão esqueça de levar seus exames! 💜",
            "variables": ["patient_name", "appointment_time"],
            "category": "appointment"
        }
    ]
    
    for template in templates:
        # Verificar se já existe
        check_query = text("SELECT id FROM message_templates WHERE name = :name")
        existing = session.execute(check_query, {"name": template['name']}).first()
        
        if existing:
            print(f"    ℹ️  Template já existe: {template['name']}")
            continue
        
        # Inserir novo template
        insert_query = text("""
            INSERT INTO message_templates (
                id, name, content, variables, category, active, created_at, updated_at
            ) VALUES (
                :id, :name, :content, :variables, :category, :active, :created_at, :updated_at
            )
        """)
        
        template_id = str(uuid4())
        now = datetime.utcnow()
        
        session.execute(insert_query, {
            "id": template_id,
            "name": template['name'],
            "content": template['content'],
            "variables": template['variables'],
            "category": template['category'],
            "active": True,
            "created_at": now,
            "updated_at": now
        })
        
        print(f"    ✅ Template criado: {template['name']}")
    
    session.commit()
    print("  ✅ Message templates populados com sucesso!")


def populate_flow_kinds(session: Session):
    """Popula flow_kinds com tipos de flow."""
    print("\n📋 Populando Flow Kinds...")
    
    flow_kinds = [
        {
            "kind_key": "onboarding",
            "name": "Onboarding",
            "description": "Fluxo de boas-vindas e introdução inicial (primeiros 15 dias)"
        },
        {
            "kind_key": "daily_checkin",
            "name": "Check-in Diário",
            "description": "Acompanhamento diário de sintomas e bem-estar"
        },
        {
            "kind_key": "monthly_quiz",
            "name": "Quiz Mensal",
            "description": "Avaliação mensal completa de saúde"
        },
        {
            "kind_key": "treatment_followup",
            "name": "Acompanhamento de Tratamento",
            "description": "Monitoramento contínuo do tratamento hormonal"
        }
    ]
    
    for kind in flow_kinds:
        # Verificar se já existe
        check_query = text("SELECT id FROM flow_kinds WHERE kind_key = :kind_key")
        existing = session.execute(check_query, {"kind_key": kind['kind_key']}).first()
        
        if existing:
            print(f"    ℹ️  Flow kind já existe: {kind['kind_key']}")
            continue
        
        # Inserir novo flow kind
        insert_query = text("""
            INSERT INTO flow_kinds (
                id, kind_key, name, description, created_at, updated_at
            ) VALUES (
                :id, :kind_key, :name, :description, :created_at, :updated_at
            )
        """)
        
        kind_id = str(uuid4())
        now = datetime.utcnow()
        
        session.execute(insert_query, {
            "id": kind_id,
            "kind_key": kind['kind_key'],
            "name": kind['name'],
            "description": kind['description'],
            "created_at": now,
            "updated_at": now
        })
        
        print(f"    ✅ Flow kind criado: {kind['kind_key']}")
    
    session.commit()
    print("  ✅ Flow kinds populados com sucesso!")


def main():
    """Função principal."""
    print("=" * 60)
    print("🚀 POPULANDO TEMPLATES NO BANCO DE DADOS")
    print("=" * 60)
    
    try:
        with Session(engine) as session:
            # 1. Popular flow kinds primeiro (dependência)
            populate_flow_kinds(session)
            
            # 2. Popular flow templates
            populate_flow_templates(session)
            
            # 3. Popular quiz templates
            populate_quiz_templates(session)
            
            # 4. Popular message templates
            populate_message_templates(session)
        
        print("\n" + "=" * 60)
        print("✅ TODOS OS TEMPLATES FORAM POPULADOS COM SUCESSO!")
        print("=" * 60)
        print("\n📊 Próximos passos:")
        print("  1. Verificar templates no banco de dados")
        print("  2. Testar criação de paciente (deve iniciar flow)")
        print("  3. Verificar envio de mensagens")
        print("  4. Monitorar logs do Celery Beat")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
