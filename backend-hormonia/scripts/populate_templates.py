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
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Carregar variáveis de ambiente do .env
from dotenv import load_dotenv
env_path = backend_dir / '.env'
load_dotenv(env_path)

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
    
    # Mapear flow_kind_key para flow_kind_id
    flow_kind_map = {}
    kind_query = text("SELECT id, kind_key FROM flow_kinds")
    for row in session.execute(kind_query):
        flow_kind_map[row.kind_key] = row.id
    
    for flow_file in flow_files:
        file_path = templates_dir / flow_file
        if not file_path.exists():
            print(f"  ⚠️  Arquivo não encontrado: {flow_file}")
            continue
        
        print(f"  📄 Processando: {flow_file}")
        template_data = load_yaml_template(file_path)
        
        # Determinar flow_kind_id baseado no template
        flow_kind_key = template_data.get('flow_kind', 'onboarding')
        if flow_kind_key not in flow_kind_map:
            print(f"    ⚠️  Flow kind não encontrado: {flow_kind_key}")
            continue
        
        flow_kind_id = flow_kind_map[flow_kind_key]
        
        # Extrair número da versão (ex: "2.0.0" -> 2)
        version_str = template_data.get('version', '1.0.0')
        version_number = int(version_str.split('.')[0])
        
        # Verificar se já existe
        check_query = text("""
            SELECT id FROM flow_template_versions 
            WHERE flow_kind_id = :flow_kind_id AND version_number = :version_number
        """)
        existing = session.execute(
            check_query,
            {"flow_kind_id": flow_kind_id, "version_number": version_number}
        ).first()
        
        if existing:
            print(f"    ℹ️  Template já existe: {template_data['name']} v{version_number}")
            continue
        
        # Inserir novo template
        insert_query = text("""
            INSERT INTO flow_template_versions (
                id, flow_kind_id, version_number, template_name, description, 
                steps, metadata, is_active, is_draft, created_at, updated_at
            ) VALUES (
                :id, :flow_kind_id, :version_number, :template_name, :description,
                :steps, :metadata, :is_active, :is_draft, :created_at, :updated_at
            )
        """)
        
        template_id = str(uuid4())
        now = datetime.now()
        
        # Preparar steps e metadata
        steps = template_data.get('steps', template_data.get('days', []))
        metadata = {
            'version': version_str,
            'flow_kind': flow_kind_key,
            'original_data': template_data
        }
        
        session.execute(insert_query, {
            "id": template_id,
            "flow_kind_id": flow_kind_id,
            "version_number": version_number,
            "template_name": template_data['name'],
            "description": template_data.get('description', ''),
            "steps": json.dumps(steps, ensure_ascii=False),
            "metadata": json.dumps(metadata, ensure_ascii=False),
            "is_active": True,
            "is_draft": False,
            "created_at": now,
            "updated_at": now
        })
        
        print(f"    ✅ Template criado: {template_data['name']} v{version_number}")
    
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
    
    # version é VARCHAR no schema, não INTEGER
    version_str = str(template_data.get('version', '1.0.0'))
    
    # Verificar se já existe
    check_query = text("""
        SELECT id FROM quiz_templates 
        WHERE name = :name AND version = :version
    """)
    existing = session.execute(
        check_query,
        {"name": template_data['name'], "version": version_str}
    ).first()
    
    if existing:
        print(f"    ℹ️  Quiz template já existe: {template_data['name']} v{version_str}")
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
    now = datetime.now()
    
    session.execute(insert_query, {
        "id": template_id,
        "name": template_data['name'],
        "version": version_str,
        "description": template_data.get('description', ''),
        "questions": json.dumps(template_data['questions'], ensure_ascii=False),
        "is_active": template_data.get('is_active', True),
        "created_at": now,
        "updated_at": now
    })
    
    session.commit()
    print(f"    ✅ Quiz template criado: {template_data['name']} v{version_str}")
    print("  ✅ Quiz templates populados com sucesso!")


def populate_message_templates(session: Session):
    """Popula templates de mensagens (armazenados em flow_messages)."""
    print("\n📋 Populando Message Templates...")
    print("    ℹ️  Tabela 'message_templates' não existe no schema atual")
    print("    ℹ️  Templates de mensagens estão em 'flow_messages' (vinculados aos flows)")
    print("    ℹ️  Mensagens serão criadas automaticamente quando flows forem executados")
    print("  ✅ Message templates configurados nos flows YAML!")


def populate_flow_kinds(session: Session):
    """Popula flow_kinds com tipos de flow."""
    print("\n📋 Populando Flow Kinds...")
    
    flow_kinds = [
        {
            "kind_key": "onboarding",
            "display_name": "Onboarding",
            "description": "Fluxo de boas-vindas e introdução inicial (primeiros 15 dias)"
        },
        {
            "kind_key": "daily_checkin",
            "display_name": "Check-in Diário",
            "description": "Acompanhamento diário de sintomas e bem-estar"
        },
        {
            "kind_key": "monthly_quiz",
            "display_name": "Quiz Mensal",
            "description": "Avaliação mensal completa de saúde"
        },
        {
            "kind_key": "treatment_followup",
            "display_name": "Acompanhamento de Tratamento",
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
                id, kind_key, display_name, description, is_active, created_at, updated_at
            ) VALUES (
                :id, :kind_key, :display_name, :description, :is_active, :created_at, :updated_at
            )
        """)
        
        kind_id = str(uuid4())
        now = datetime.now()
        
        session.execute(insert_query, {
            "id": kind_id,
            "kind_key": kind['kind_key'],
            "display_name": kind['display_name'],
            "description": kind['description'],
            "is_active": True,
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
