# Guia de Rotação de Chaves de Criptografia

> **Última Atualização:** 2025-11-26
> **Versão:** 1.0

## Visão Geral

Este documento descreve o procedimento para rotação das chaves de criptografia usadas para proteger dados sensíveis (CPF, email, telefone) no sistema Hormonia, em conformidade com a LGPD.

## Variáveis de Ambiente

| Variável | Descrição | Tamanho | Uso |
|----------|-----------|---------|-----|
| `PHI_ENCRYPTION_KEY` | Chave principal AES-256-GCM (base64) | 32 bytes | Criptografia de dados (novo fluxo) |
| `ENCRYPTION_KEY_CURRENT` | Chave atual (Fernet, legado) | 32 bytes | Criptografia de dados legados |
| `ENCRYPTION_KEY_PREVIOUS` | Chave anterior (para re-criptografia) | 32 bytes | Migração de dados legados |
| `HASH_SALT` | Salt para hashes de busca (hex) | 32 bytes | Geração de hashes de busca |

## Quando Rotacionar Chaves

### Rotação Programada
- **Frequência recomendada:** Anual (12 meses)
- **Data sugerida:** Durante janela de manutenção planejada
- **Objetivo:** Prevenção e boas práticas de segurança

### Rotação de Emergência
Executar **imediatamente** em caso de:
- ✅ Suspeita de comprometimento da chave
- ✅ Vazamento acidental em logs ou código
- ✅ Saída de funcionário com acesso às chaves (30 dias)
- ✅ Incidente de segurança confirmado
- ✅ Requisição de auditoria ou compliance

## Procedimento de Rotação

### Fase 1: Preparação (1-2 dias antes)

#### 1.1 Backup Completo
```bash
# Backup do banco de dados
pg_dump -h $DB_HOST -U $DB_USER -d hormonia > backup_pre_rotation_$(date +%Y%m%d).sql
gzip backup_pre_rotation_$(date +%Y%m%d).sql

# Verificar integridade do backup
gunzip -c backup_pre_rotation_*.sql.gz | head -n 100

# Armazenar em local seguro
aws s3 cp backup_pre_rotation_*.sql.gz s3://hormonia-backups/encryption-rotation/
```

#### 1.2 Gerar Nova Chave
```python
# generate_encryption_key.py
import os
import base64
import secrets
from cryptography.fernet import Fernet

# Gerar chave base64 de 32 bytes (novo fluxo AES-256-GCM)
phi_key = base64.b64encode(os.urandom(32)).decode("ascii")
print(f"PHI_ENCRYPTION_KEY (base64, 32 bytes): {phi_key}")

# Gerar chave Fernet (legado)
legacy_key = Fernet.generate_key().decode("ascii")
print(f"ENCRYPTION_KEY_CURRENT (Fernet): {legacy_key}")

# Gerar salt para hashes de busca
hash_salt = secrets.token_hex(32)  # 32 bytes = 64 caracteres hex
print(f"HASH_SALT (hex, 32 bytes): {hash_salt}")
```

#### 1.3 Documentar Chaves Antigas
```bash
# Salvar chaves atuais em cofre seguro (AWS Secrets Manager, 1Password, etc.)
export OLD_PHI_ENCRYPTION_KEY=$PHI_ENCRYPTION_KEY
export OLD_ENCRYPTION_KEY_CURRENT=$ENCRYPTION_KEY_CURRENT
export OLD_HASH_SALT=$HASH_SALT

# Documentar timestamp
echo "Chave antiga salva em: $(date -Iseconds)" >> key_rotation_log.txt
```

### Fase 2: Atualização de Variáveis (Durante Manutenção)

#### 2.1 Parar Serviços
```bash
# Ativar modo de manutenção
echo "MAINTENANCE_MODE=true" >> .env

# Parar workers e API
docker-compose stop api worker
# OU
systemctl stop hormonia-api hormonia-worker
```

#### 2.2 Atualizar Variáveis de Ambiente
```bash
# Mover chave atual para previous (legado)
export ENCRYPTION_KEY_PREVIOUS=$ENCRYPTION_KEY_CURRENT

# Definir novas chaves
export PHI_ENCRYPTION_KEY="nova_chave_base64_32_bytes"
export ENCRYPTION_KEY_CURRENT="nova_chave_fernet_base64"
export HASH_SALT="novo_salt_hex_64_chars"

# Atualizar arquivo .env
cat >> .env <<EOF
PHI_ENCRYPTION_KEY=$PHI_ENCRYPTION_KEY
ENCRYPTION_KEY_CURRENT=$ENCRYPTION_KEY_CURRENT
ENCRYPTION_KEY_PREVIOUS=$ENCRYPTION_KEY_PREVIOUS
HASH_SALT=$HASH_SALT
EOF
```

### Fase 3: Re-criptografia de Dados

#### 3.1 Script de Re-criptografia
```python
# scripts/rotate_encryption_key.py
import asyncio
from sqlalchemy import select
from app.database import async_session_maker
from app.models.patient import Patient
from app.services.encryption_service import EncryptionService

async def rotate_encryption_keys():
    """Re-encrypt all sensitive data with new key."""

    # Instanciar serviço com nova chave
    new_service = EncryptionService()

    # Instanciar serviço com chave anterior para descriptografia
    old_service = EncryptionService(use_previous_key=True)

    async with async_session_maker() as db:
        # Buscar todos os pacientes
        result = await db.execute(select(Patient))
        patients = result.scalars().all()

        total = len(patients)
        print(f"Re-criptografando {total} pacientes...")

        for idx, patient in enumerate(patients, 1):
            try:
                # Re-criptografar CPF
                if patient.cpf_encrypted:
                    cpf = old_service.decrypt_cpf(patient.cpf_encrypted)
                    patient.cpf_encrypted, patient.cpf_hash = new_service.encrypt_cpf(cpf)

                # Re-criptografar Email
                if patient.email_encrypted:
                    email = old_service.decrypt_email(patient.email_encrypted)
                    patient.email_encrypted, patient.email_hash = new_service.encrypt_email(email)

                # Re-criptografar Telefone
                if patient.phone_encrypted:
                    phone = old_service.decrypt_phone(patient.phone_encrypted)
                    patient.phone_encrypted, patient.phone_hash = new_service.encrypt_phone(phone)

                # Commit a cada 100 registros
                if idx % 100 == 0:
                    await db.commit()
                    print(f"Progresso: {idx}/{total} ({idx/total*100:.1f}%)")

            except Exception as e:
                print(f"ERRO no paciente {patient.id}: {e}")
                await db.rollback()
                raise

        # Commit final
        await db.commit()
        print(f"✅ Re-criptografia concluída: {total} pacientes")

if __name__ == "__main__":
    asyncio.run(rotate_encryption_keys())
```

#### 3.2 Executar Re-criptografia
```bash
# Executar script
python scripts/rotate_encryption_key.py

# Monitorar progresso
tail -f rotation.log
```

### Fase 4: Validação

#### 4.1 Testes de Descriptografia
```python
# scripts/validate_encryption.py
import asyncio
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models.patient import Patient
from app.services.encryption_service import EncryptionService

async def validate_encryption():
    """Validate that all data can be decrypted with new key."""

    service = EncryptionService()

    async with async_session_maker() as db:
        # Contar pacientes com dados criptografados
        result = await db.execute(
            select(func.count(Patient.id)).where(Patient.cpf_encrypted.isnot(None))
        )
        total = result.scalar()

        # Testar descriptografia de amostra
        result = await db.execute(select(Patient).limit(10))
        patients = result.scalars().all()

        errors = 0
        for patient in patients:
            try:
                if patient.cpf_encrypted:
                    cpf = service.decrypt_cpf(patient.cpf_encrypted)
                    assert len(cpf) == 11, f"CPF inválido: {cpf}"

                if patient.email_encrypted:
                    email = service.decrypt_email(patient.email_encrypted)
                    assert "@" in email, f"Email inválido: {email}"

                if patient.phone_encrypted:
                    phone = service.decrypt_phone(patient.phone_encrypted)
                    assert phone.isdigit(), f"Telefone inválido: {phone}"

            except Exception as e:
                print(f"❌ ERRO no paciente {patient.id}: {e}")
                errors += 1

        if errors == 0:
            print(f"✅ Validação bem-sucedida: {total} pacientes, 10 testados")
        else:
            print(f"❌ Validação falhou: {errors} erros encontrados")
            return False

    return True

if __name__ == "__main__":
    success = asyncio.run(validate_encryption())
    exit(0 if success else 1)
```

#### 4.2 Executar Validação
```bash
# Validar dados
python scripts/validate_encryption.py

# Se sucesso, prosseguir. Se falha, reverter para backup.
```

### Fase 5: Ativação e Limpeza

#### 5.1 Reiniciar Serviços
```bash
# Remover modo de manutenção
sed -i '/MAINTENANCE_MODE/d' .env

# Reiniciar serviços
docker-compose up -d api worker
# OU
systemctl start hormonia-api hormonia-worker

# Verificar saúde
curl http://localhost:8000/health
```

#### 5.2 Monitorar Logs
```bash
# Monitorar por 24 horas
tail -f /var/log/hormonia/api.log | grep -i "encryption\|decrypt"
```

#### 5.3 Limpeza (Após 30 dias sem problemas)
```bash
# Remover chave anterior
sed -i '/ENCRYPTION_KEY_PREVIOUS/d' .env

# Documentar rotação concluída
echo "Rotação de chave concluída em: $(date -Iseconds)" >> key_rotation_log.txt

# Arquivar logs
tar -czf rotation_logs_$(date +%Y%m%d).tar.gz rotation.log key_rotation_log.txt
aws s3 cp rotation_logs_*.tar.gz s3://hormonia-backups/encryption-rotation/
```

## Recuperação em Caso de Perda de Chave

### Cenário: Chave de Criptografia Perdida

**IMPORTANTE:** Se a chave de criptografia for perdida, os dados criptografados são **PERMANENTEMENTE INACESSÍVEIS**. Não existe backdoor ou método de recuperação.

### Medidas Preventivas

#### 1. Armazenamento Redundante
```bash
# Múltiplas cópias em locais seguros
1. AWS Secrets Manager (produção)
2. 1Password/LastPass (equipe técnica)
3. Cofre físico (sede da empresa)
4. Backup criptografado em S3 (com outra chave)
```

#### 2. Procedimento de Acesso
```markdown
# Matriz de Responsabilidade
| Papel | Acesso | Aprovação |
|-------|--------|-----------|
| CTO | Leitura direta | N/A |
| DevOps Lead | Leitura via 2FA | CTO |
| Backend Dev | Somente em emergência | CTO + DevOps Lead |
| DBA | Somente em emergência | CTO + DevOps Lead |
```

#### 3. Documentação Obrigatória
- Localização de todas cópias da chave
- Contatos de emergência com acesso
- Procedimento de aprovação para acesso
- Logs de auditoria de todas leituras da chave

### Se a Chave For Perdida

#### Impacto Imediato
1. ❌ Dados criptografados permanentemente inacessíveis:
   - CPF de pacientes
   - Emails de pacientes
   - Telefones de pacientes
2. ❌ Sistema incapaz de:
   - Buscar pacientes por CPF/email/telefone
   - Exibir dados pessoais
   - Gerar relatórios com PII

#### Ações de Emergência

**Dia 0 (Descoberta):**
```bash
# 1. Ativar plano de crise
# 2. Notificar CTO/CEO imediatamente
# 3. Preservar todos logs e backups
# 4. Congelar sistema (modo manutenção)
```

**Dias 1-2 (Avaliação):**
- Verificar todos locais de backup da chave
- Confirmar irreversibilidade da perda
- Quantificar pacientes afetados
- Avaliar backups de banco (últimos 90 dias)

**Dias 3-10 (Notificação):**
- Notificar ANPD (Art. 48 LGPD): 2 dias úteis
- Notificar pacientes afetados (se alto risco)
- Comunicar transparentemente o ocorrido
- Oferecer medidas compensatórias

**Dias 11+ (Recuperação):**
- Restaurar backup mais recente (se chave disponível)
- OU re-coletar dados dos pacientes:
  - Criar novo formulário de cadastro
  - Solicitar reenvio de dados pessoais
  - Oferecer suporte assistido
- Implementar novos controles preventivos
- Atualizar políticas de segurança

#### Comunicação com Titulares
```
Assunto: Notificação de Incidente de Segurança - Sistema Hormonia

Prezado(a) Paciente,

Informamos que em [DATA], identificamos a perda irreversível da chave de
criptografia utilizada para proteger seus dados pessoais (CPF, email, telefone).

IMPACTO:
- Seus dados criptografados não podem ser descriptografados
- Seus dados NÃO foram acessados por terceiros
- Será necessário re-cadastrar suas informações

AÇÕES TOMADAS:
- Notificação imediata à ANPD
- Implementação de controles adicionais
- [Outras medidas...]

PRÓXIMOS PASSOS:
1. Acesse [LINK] para re-cadastrar seus dados
2. Nossa equipe está disponível para suporte: [CONTATO]

Pedimos desculpas pelo transtorno.

Atenciosamente,
[DPO - Encarregado de Dados]
```

## Checklist de Rotação

### Antes da Rotação
- [ ] Backup completo do banco de dados
- [ ] Novas chaves geradas (base64, 32 bytes)
- [ ] Novo HASH_SALT gerado (32 bytes / 64 hex)
- [ ] Chaves antigas documentadas e salvas
- [ ] Janela de manutenção agendada
- [ ] Equipe técnica notificada
- [ ] Rollback plan preparado

### Durante a Rotação
- [ ] Modo de manutenção ativado
- [ ] Serviços parados
- [ ] Variáveis de ambiente atualizadas
- [ ] Script de re-criptografia executado
- [ ] Validação de dados bem-sucedida
- [ ] Serviços reiniciados
- [ ] Modo de manutenção desativado

### Após a Rotação
- [ ] Testes de integração executados
- [ ] Logs monitorados por 24h
- [ ] Métricas de performance verificadas
- [ ] Equipe de suporte treinada
- [ ] Documentação atualizada
- [ ] Após 30 dias: chave anterior removida

## Frequência Recomendada

| Cenário | Frequência | Notas |
|---------|------------|-------|
| **Rotação preventiva** | Anual | Durante manutenção planejada |
| **Suspeita de comprometimento** | Imediato | Dentro de 24 horas |
| **Após saída de funcionário** | 30 dias | Com acesso a sistemas críticos |
| **Requisição de auditoria** | Conforme demanda | Compliance/certificação |
| **Mudança de provedor cloud** | Imediato | Antes da migração |

## Contato

**Em caso de dúvidas ou emergências:**
- **DPO (Encarregado de Dados):** dpo@hormonia.com.br
- **CTO:** cto@hormonia.com.br
- **DevOps Lead:** devops@hormonia.com.br
- **Suporte 24/7:** +55 (11) XXXX-XXXX

---

**Última Revisão:** 2025-11-26
**Próxima Revisão:** 2026-01-26
**Responsável:** Equipe de Segurança da Informação
