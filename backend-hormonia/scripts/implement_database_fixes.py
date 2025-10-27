#!/usr/bin/env python3
"""
Script para implementar as correções críticas identificadas na análise do banco de dados
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_patient_model_completeness():
    """Adiciona campos médicos ausentes no modelo Patient"""
    
    print("🏥 Corrigindo modelo Patient - Adicionando campos médicos...")
    print("=" * 60)
    
    try:
        # Ler o arquivo atual do modelo Patient
        patient_model_path = "backend-hormonia/app/models/patient.py"
        
        with open(patient_model_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se os campos já existem
        missing_fields = []
        
        if 'medical_history' not in content:
            missing_fields.append('medical_history')
        if 'treatment_type' not in content:
            missing_fields.append('treatment_type')
        if 'diagnosis_date' not in content:
            missing_fields.append('diagnosis_date')
        if 'birth_date' not in content:
            missing_fields.append('birth_date')
        if 'cpf' not in content:
            missing_fields.append('cpf')
        
        if not missing_fields:
            print("   ✅ Todos os campos médicos já estão presentes no modelo")
            return True
        
        print(f"   📋 Campos ausentes identificados: {', '.join(missing_fields)}")
        
        # Adicionar imports necessários se não existirem
        if 'from datetime import date' not in content and 'diagnosis_date' in missing_fields:
            content = content.replace(
                'from datetime import datetime',
                'from datetime import datetime, date'
            )
        
        # Encontrar onde adicionar os campos (após os campos existentes)
        # Procurar por uma linha que termine com vírgula ou o final da classe
        lines = content.split('\n')
        insert_index = -1
        
        for i, line in enumerate(lines):
            if 'current_day' in line and '=' in line:
                insert_index = i + 1
                break
        
        if insert_index == -1:
            print("   ❌ Não foi possível encontrar local para inserir campos")
            return False
        
        # Preparar novos campos
        new_fields = []
        
        if 'medical_history' in missing_fields:
            new_fields.append('    medical_history: Optional[str] = Column(Text, nullable=True)')
        
        if 'treatment_type' in missing_fields:
            new_fields.append('    treatment_type: Optional[str] = Column(String(100), nullable=True)')
        
        if 'diagnosis_date' in missing_fields:
            new_fields.append('    diagnosis_date: Optional[date] = Column(Date, nullable=True)')
        
        if 'birth_date' in missing_fields:
            new_fields.append('    birth_date: Optional[date] = Column(Date, nullable=True)')
        
        if 'cpf' in missing_fields:
            new_fields.append('    cpf: Optional[str] = Column(String(14), nullable=True, index=True)')
        
        # Inserir os novos campos
        for field in new_fields:
            lines.insert(insert_index, field)
            insert_index += 1
        
        # Escrever o arquivo modificado
        new_content = '\n'.join(lines)
        
        with open(patient_model_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"   ✅ Adicionados {len(new_fields)} campos ao modelo Patient")
        for field in new_fields:
            field_name = field.split(':')[0].strip()
            print(f"      - {field_name}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao corrigir modelo Patient: {e}")
        return False

def fix_patient_schema_completeness():
    """Adiciona campos médicos ausentes no schema Patient"""
    
    print("\n📋 Corrigindo schema Patient - Adicionando campos médicos...")
    print("=" * 60)
    
    try:
        # Ler o arquivo de schemas
        schema_path = "backend-hormonia/app/schemas/patient.py"
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se os campos já existem nos schemas
        schemas_to_update = ['PatientCreate', 'PatientUpdate', 'PatientResponse']
        
        for schema_name in schemas_to_update:
            if f'class {schema_name}' in content:
                print(f"   🔍 Verificando schema {schema_name}...")
                
                # Encontrar a classe
                class_start = content.find(f'class {schema_name}')
                if class_start == -1:
                    continue
                
                # Encontrar o final da classe (próxima classe ou final do arquivo)
                next_class = content.find('\nclass ', class_start + 1)
                if next_class == -1:
                    class_content = content[class_start:]
                else:
                    class_content = content[class_start:next_class]
                
                # Verificar campos ausentes
                missing_in_schema = []
                
                if 'medical_history' not in class_content:
                    missing_in_schema.append('medical_history')
                if 'treatment_type' not in class_content:
                    missing_in_schema.append('treatment_type')
                if 'diagnosis_date' not in class_content:
                    missing_in_schema.append('diagnosis_date')
                if 'birth_date' not in class_content:
                    missing_in_schema.append('birth_date')
                if 'cpf' not in class_content:
                    missing_in_schema.append('cpf')
                
                if missing_in_schema:
                    print(f"      📝 Campos ausentes em {schema_name}: {', '.join(missing_in_schema)}")
                else:
                    print(f"      ✅ {schema_name} já possui todos os campos")
        
        # Adicionar imports necessários
        if 'from datetime import date' not in content:
            content = content.replace(
                'from datetime import datetime',
                'from datetime import datetime, date'
            )
        
        # Exemplo de adição para PatientResponse (mais comum)
        if 'class PatientResponse' in content and 'medical_history' not in content:
            # Encontrar onde adicionar os campos
            patient_response_start = content.find('class PatientResponse')
            
            # Procurar por um campo existente para inserir após ele
            insert_point = content.find('current_day:', patient_response_start)
            if insert_point != -1:
                # Encontrar o final da linha
                line_end = content.find('\n', insert_point)
                
                new_fields = '''
    medical_history: Optional[str] = Field(None, description="Histórico médico do paciente")
    treatment_type: Optional[str] = Field(None, description="Tipo de tratamento")
    diagnosis_date: Optional[date] = Field(None, description="Data do diagnóstico")
    birth_date: Optional[date] = Field(None, description="Data de nascimento")
    cpf: Optional[str] = Field(None, description="CPF do paciente")'''
                
                content = content[:line_end] + new_fields + content[line_end:]
        
        # Escrever arquivo modificado
        with open(schema_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("   ✅ Schemas atualizados com campos médicos")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao corrigir schemas: {e}")
        return False

def create_whatsapp_message_model():
    """Cria modelo para persistir mensagens do WhatsApp"""
    
    print("\n📱 Criando modelo WhatsAppMessage...")
    print("=" * 60)
    
    try:
        model_content = '''
"""
Modelo para persistir mensagens do WhatsApp no banco de dados
"""

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from app.core.database import Base


class WhatsAppMessage(Base):
    """Modelo para mensagens do WhatsApp."""
    
    __tablename__ = "whatsapp_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    phone_number = Column(String(20), nullable=False, index=True)
    message_type = Column(String(50), nullable=False)  # text, image, audio, etc
    content = Column(JSONB, nullable=False)
    status = Column(String(20), default="sent")  # sent, delivered, read, failed
    
    # Relacionamento com paciente (opcional)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)
    patient = relationship("Patient", back_populates="whatsapp_messages")
    
    # Timestamps
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    
    # Metadados
    direction = Column(String(10), nullable=False)  # inbound, outbound
    message_id_external = Column(String(255), nullable=True)  # ID da Evolution API
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Contexto do flow (se aplicável)
    flow_context = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<WhatsAppMessage(id={self.id}, phone={self.phone_number}, type={self.message_type})>"


class WhatsAppContact(Base):
    """Modelo para contatos do WhatsApp."""
    
    __tablename__ = "whatsapp_contacts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    phone_number = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=True)
    
    # Relacionamento com paciente
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)
    patient = relationship("Patient", back_populates="whatsapp_contact")
    
    # Status do contato
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)
    
    # Metadados
    profile_picture_url = Column(String(500), nullable=True)
    last_seen = Column(DateTime, nullable=True)
    metadata = Column(JSONB, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<WhatsAppContact(phone={self.phone_number}, name={self.name})>"
'''
        
        # Criar arquivo do modelo
        model_path = "backend-hormonia/app/models/whatsapp.py"
        
        with open(model_path, 'w', encoding='utf-8') as f:
            f.write(model_content)
        
        print("   ✅ Modelo WhatsAppMessage criado")
        print(f"   📁 Arquivo: {model_path}")
        
        # Atualizar __init__.py dos modelos
        init_path = "backend-hormonia/app/models/__init__.py"
        
        try:
            with open(init_path, 'r', encoding='utf-8') as f:
                init_content = f.read()
            
            if 'from .whatsapp import' not in init_content:
                # Adicionar import
                init_content += "\nfrom .whatsapp import WhatsAppMessage, WhatsAppContact\n"
                
                with open(init_path, 'w', encoding='utf-8') as f:
                    f.write(init_content)
                
                print("   ✅ Import adicionado ao __init__.py")
        
        except Exception as e:
            print(f"   ⚠️ Aviso: Não foi possível atualizar __init__.py: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao criar modelo WhatsApp: {e}")
        return False

def create_admin_models():
    """Cria modelos básicos para sistema de admin"""
    
    print("\n🔐 Criando modelos básicos de Admin...")
    print("=" * 60)
    
    try:
        admin_model_content = '''
"""
Modelos básicos para sistema de administração
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4
from enum import Enum

from app.core.database import Base


class AdminRole(str, Enum):
    """Roles de administrador."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    OPERATOR = "operator"


class AdminUser(Base):
    """Modelo para usuários administrativos."""
    
    __tablename__ = "admin_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Informações pessoais
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=True)
    
    # Configurações de conta
    role = Column(String(20), nullable=False, default=AdminRole.OPERATOR.value)
    department = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    
    # Segurança
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255), nullable=True)
    must_change_password = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Auditoria
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(INET, nullable=True)
    last_password_change = Column(DateTime, default=datetime.utcnow)
    
    # Configurações
    max_concurrent_sessions = Column(Integer, default=3)
    metadata = Column(JSONB, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    
    # Relacionamentos
    sessions = relationship("AdminSession", back_populates="admin_user")
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_locked(self):
        return self.locked_until and self.locked_until > datetime.utcnow()
    
    def __repr__(self):
        return f"<AdminUser(email={self.email}, role={self.role})>"


class AdminSession(Base):
    """Modelo para sessões administrativas."""
    
    __tablename__ = "admin_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    
    # Tokens
    session_token = Column(String(255), nullable=False, unique=True, index=True)
    refresh_token = Column(String(255), nullable=True, unique=True)
    
    # Informações da sessão
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    logout_reason = Column(String(100), nullable=True)
    
    # Metadados
    metadata = Column(JSONB, default=dict)
    
    # Relacionamentos
    admin_user = relationship("AdminUser", back_populates="sessions")
    
    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f"<AdminSession(user_id={self.admin_user_id}, active={self.is_active})>"
'''
        
        # Criar arquivo do modelo
        admin_model_path = "backend-hormonia/app/models/admin.py"
        
        with open(admin_model_path, 'w', encoding='utf-8') as f:
            f.write(admin_model_content)
        
        print("   ✅ Modelos de Admin criados")
        print(f"   📁 Arquivo: {admin_model_path}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao criar modelos de Admin: {e}")
        return False

def update_patient_relationships():
    """Atualiza relacionamentos do modelo Patient"""
    
    print("\n🔗 Atualizando relacionamentos do Patient...")
    print("=" * 60)
    
    try:
        # Ler modelo Patient atual
        patient_path = "backend-hormonia/app/models/patient.py"
        
        with open(patient_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se relacionamentos já existem
        relationships_to_add = []
        
        if 'whatsapp_messages' not in content:
            relationships_to_add.append(
                '    whatsapp_messages = relationship("WhatsAppMessage", back_populates="patient")'
            )
        
        if 'whatsapp_contact' not in content:
            relationships_to_add.append(
                '    whatsapp_contact = relationship("WhatsAppContact", back_populates="patient", uselist=False)'
            )
        
        if relationships_to_add:
            # Encontrar onde adicionar (antes do final da classe)
            # Procurar por __repr__ ou final da classe
            insert_point = content.rfind('def __repr__')
            if insert_point == -1:
                insert_point = content.rfind('class Patient')
                # Encontrar o final da classe
                insert_point = content.find('\n\n', insert_point)
            
            if insert_point != -1:
                # Adicionar relacionamentos
                new_relationships = '\n    # Relacionamentos WhatsApp\n' + '\n'.join(relationships_to_add) + '\n'
                content = content[:insert_point] + new_relationships + content[insert_point:]
                
                # Escrever arquivo
                with open(patient_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"   ✅ Adicionados {len(relationships_to_add)} relacionamentos")
                for rel in relationships_to_add:
                    rel_name = rel.split('=')[0].strip()
                    print(f"      - {rel_name}")
            else:
                print("   ⚠️ Não foi possível encontrar local para inserir relacionamentos")
        else:
            print("   ✅ Relacionamentos já existem")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao atualizar relacionamentos: {e}")
        return False

def main():
    """Função principal"""
    
    print("🔧 IMPLEMENTAÇÃO DE CORREÇÕES CRÍTICAS DO BANCO DE DADOS")
    print("=" * 70)
    print("Baseado na análise comparativa entre schema DB e código")
    print()
    
    # Executar correções
    fixes = [
        ("Modelo Patient - Campos Médicos", fix_patient_model_completeness),
        ("Schema Patient - Campos Médicos", fix_patient_schema_completeness),
        ("Modelo WhatsApp Messages", create_whatsapp_message_model),
        ("Modelos Admin Básicos", create_admin_models),
        ("Relacionamentos Patient", update_patient_relationships),
    ]
    
    results = []
    
    for fix_name, fix_function in fixes:
        print(f"\n🔄 Executando: {fix_name}")
        print("-" * 50)
        
        try:
            success = fix_function()
            results.append((fix_name, success))
            
            if success:
                print(f"✅ {fix_name}: SUCESSO")
            else:
                print(f"❌ {fix_name}: FALHOU")
                
        except Exception as e:
            print(f"❌ {fix_name}: ERRO - {e}")
            results.append((fix_name, False))
    
    # Resumo final
    print("\n" + "=" * 70)
    print("📊 RESUMO DA EXECUÇÃO")
    print("=" * 70)
    
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"✅ Sucessos: {successful}/{total}")
    print(f"❌ Falhas: {total - successful}/{total}")
    print()
    
    for fix_name, success in results:
        status = "✅ SUCESSO" if success else "❌ FALHOU"
        print(f"   {status}: {fix_name}")
    
    print("\n" + "=" * 70)
    
    if successful == total:
        print("🎉 TODAS AS CORREÇÕES FORAM APLICADAS COM SUCESSO!")
        print("\n📋 PRÓXIMOS PASSOS:")
        print("1. Executar migrações do banco de dados")
        print("2. Testar endpoints atualizados")
        print("3. Implementar testes de integração")
        print("4. Atualizar documentação da API")
    else:
        print("⚠️ ALGUMAS CORREÇÕES FALHARAM")
        print("\n📋 AÇÕES NECESSÁRIAS:")
        print("1. Revisar erros acima")
        print("2. Corrigir problemas manualmente")
        print("3. Re-executar script")
    
    print("\n📖 Consulte docs/DATABASE_CODE_ANALYSIS.md para detalhes completos")

if __name__ == "__main__":
    main()