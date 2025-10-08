# Authentication Functions Audit Report
**Data**: 2025-10-08
**Projeto**: Clínica Oncológica v02

## 📋 Executive Summary

Este relatório documenta a localização e uso das funções críticas de autenticação `verify_password` e `create_access_token` no projeto.

## 🔍 Findings

### 1. verify_password() Function

#### ✅ Definição Principal (PRODUÇÃO)
**Arquivo**: `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\utils\security.py`
**Linhas**: 108-136

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash - handles edge cases."""
    if not plain_password or not hashed_password:
        return False

    # Ensure password is not too long
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    try:
        if pwd_context:
            # Use passlib - but handle the bug
            try:
                return pwd_context.verify(password_bytes.decode('utf-8'), hashed_password)
            except ValueError as e:
                if "password cannot be longer than 72 bytes" in str(e):
                    # This is the bug - password is fine but passlib thinks it's too long
                    # Fall back to direct bcrypt
                    logger.warning("Passlib bcrypt bug detected, using direct bcrypt")
                    return bcrypt_lib.checkpw(password_bytes, hashed_password.encode('utf-8'))
                else:
                    raise
        else:
            # Direct bcrypt fallback
            return bcrypt_lib.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to verify password: {e}")
        return False
```

**Características**:
- ✅ Validação de entrada (empty checks)
- ✅ Limite de 72 bytes (bcrypt limitation)
- ✅ Tratamento do bug do passlib
- ✅ Fallback para bcrypt nativo
- ✅ Error handling robusto
- ✅ Logging de erros

#### 📦 Backup/Alternative Version
**Arquivo**: `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\utils\security_bcrypt_backup.py`
**Linhas**: 137-157

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    import logging
    logger = logging.getLogger(__name__)

    if not plain_password or not hashed_password:
        return False

    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    try:
        if pwd_context:
            try:
                return pwd_context.verify(password_bytes.decode('utf-8'), hashed_password)
            except ValueError as e:
                if "password cannot be longer than 72 bytes" in str(e):
                    logger.warning("Passlib bcrypt bug detected, using direct bcrypt")
                    return bcrypt_lib.checkpw(password_bytes, hashed_password.encode('utf-8'))
                else:
                    raise
        else:
            return bcrypt_lib.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to verify password: {e}")
        return False
```

**Status**: Arquivo de backup (não usado em produção)

#### 📚 Documentação
**Arquivo**: `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\docs\security\AUTHENTICATION_GUIDE.md`
**Linha**: 833

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)
```

**Status**: Exemplo simplificado para documentação

---

### 2. create_access_token() Function

#### ✅ Definição Principal (PRODUÇÃO)
**Arquivo**: `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\utils\security.py`
**Linhas**: 209-217

```python
def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token using settings.SECRET_KEY and settings.ALGORITHM."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": int(expire.timestamp()),
        "type": "access"
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
```

**Características**:
- ✅ Usa configurações centralizadas (settings)
- ✅ Expiration time configurável
- ✅ Token type marker ("access")
- ✅ Timestamp conversion to int

#### 📦 Backup Version
**Arquivo**: `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\utils\security_bcrypt_backup.py`
**Linhas**: 194-208

```python
def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": int(expire.timestamp()),
        "type": "access"
    })

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
```

**Status**: Versão de backup (funcionalmente idêntica)

#### 🔄 Service Layer Wrapper
**Arquivo**: `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\services\auth.py`
**Linhas**: 118-128

```python
def create_access_token(
    self,
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token with optional custom expiration"""
    return create_access_token(data, expires_delta)
```

**Status**: Wrapper que delega para a função principal em `app.utils.security`

#### 🔄 Token Rotation Service Version
**Arquivo**: `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\services\token_rotation_service.py`
**Linhas**: 43-66

```python
def create_access_token(self, data: dict, user_id: str) -> str:
    """
    Create a new access token with rotation tracking.

    Args:
        data: Token payload data
        user_id: User ID for tracking

    Returns:
        str: JWT access token
    """
    expire_delta = timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Generate unique token ID for tracking
    token_id = self._generate_token_id()

    # Add rotation metadata to token
    data_with_rotation = {
        **data,
        "jti": token_id,  # JWT ID claim for rotation tracking
        "iat": datetime.utcnow().timestamp()  # Issued at time
    }

    # Create token using centralized function
    token = create_access_token(data_with_rotation, expire_delta)
```

**Status**: Versão estendida com tracking de rotação de tokens

---

## 🔗 Import Chain Analysis

### ❌ PROBLEMA CRÍTICO IDENTIFICADO

**Arquivo**: `c:\Meu Projetos\clinica-oncologica-v02\backend-hormonia\app\routers\quiz_auth.py`
**Linha**: 12

```python
from app.core.security import verify_password, create_access_token
```

### 🚨 Issue: Módulo `app.core.security` NÃO EXISTE!

**Evidências**:
1. ✅ Arquivo `app/core/__init__.py` existe mas NÃO exporta security functions
2. ❌ Arquivo `app/core/security.py` NÃO existe no diretório
3. ❌ Busca por `**/core/security.py` retornou: "No files found"

**Arquivos verificados em `app/core/`**:
```
✅ application_factory.py
✅ async_context_manager.py
✅ database.py
✅ event_loop_manager.py
✅ lifecycle_manager.py
✅ middleware_setup.py
✅ permissions.py
✅ redis_client_factory.py
✅ router_registry.py
✅ security_config.py  ⚠️ (mas não exporta as funções)
✅ session_manager.py
❌ security.py (NÃO EXISTE)
```

---

## 📊 Imports Map

### ✅ CORRETOS (Produção)
```python
# app/services/auth.py (linha 16)
from app.utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token as verify_jwt_token,
    validate_password_strength
)

# app/services/user_admin_service.py (linha 22)
from app.utils.security import get_password_hash, verify_password

# app/services/admin_user_service.py (linha 28)
from app.utils.security import get_password_hash, verify_password, validate_password_strength

# app/api/v1/admin/users.py (linha 42)
from app.utils.security import get_password_hash

# app/services/audit_service.py (linha 19)
from app.utils.security import mask_sensitive_url, mask_dict_secrets
```

### ❌ INCORRETO (CRITICAL BUG)
```python
# app/routers/quiz_auth.py (linha 12) ❌
from app.core.security import verify_password, create_access_token
```

---

## 🔧 Recommended Actions

### PRIORITY 1: CRITICAL FIX

**Problema**: `quiz_auth.py` importa de módulo inexistente `app.core.security`

**Soluções Possíveis**:

#### Opção A: Corrigir Import (RECOMENDADO)
```python
# Arquivo: app/routers/quiz_auth.py
# Trocar linha 12 de:
from app.core.security import verify_password, create_access_token

# Para:
from app.utils.security import verify_password, create_access_token
```

**Prós**:
- ✅ Correção simples
- ✅ Alinha com resto do código
- ✅ Usa módulo de produção correto
- ✅ Sem side effects

**Contras**:
- Nenhum

#### Opção B: Criar app/core/security.py como Proxy
```python
# Criar: app/core/security.py
"""Proxy module for backwards compatibility"""
from app.utils.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_password_hash,
    hash_password,
    validate_password_strength
)

__all__ = [
    'verify_password',
    'create_access_token',
    'create_refresh_token',
    'verify_token',
    'get_password_hash',
    'hash_password',
    'validate_password_strength'
]
```

**Prós**:
- ✅ Mantém compatibilidade com código existente
- ✅ Permite migração gradual
- ✅ Centraliza exports

**Contras**:
- ❌ Adiciona layer desnecessário
- ❌ Pode confundir desenvolvedores
- ❌ Manutenção extra

### PRIORITY 2: Verificar Deployment

**Ações**:
1. ✅ Verificar se `quiz_auth.py` está sendo usado em produção
2. ✅ Verificar logs de erro para ImportError
3. ✅ Executar testes de integração
4. ✅ Validar funcionamento do endpoint de quiz auth

### PRIORITY 3: Code Cleanup

**Ações**:
1. ✅ Remover ou arquivar `security_bcrypt_backup.py` se não estiver em uso
2. ✅ Consolidar funções duplicadas
3. ✅ Atualizar documentação com imports corretos
4. ✅ Adicionar testes de import

---

## 📝 Usage Analysis

### Funções Usadas em:

**verify_password**:
- ✅ `app/services/auth.py` (via `app.utils.security`)
- ✅ `app/services/user_admin_service.py` (via `app.utils.security`)
- ✅ `app/services/admin_user_service.py` (via `app.utils.security`)
- ❌ `app/routers/quiz_auth.py` (via `app.core.security` - BROKEN)

**create_access_token**:
- ✅ `app/services/auth.py` (via `app.utils.security`)
- ✅ `app/services/token_rotation_service.py` (via `app.utils.security`)
- ❌ `app/routers/quiz_auth.py` (via `app.core.security` - BROKEN)

---

## 🧪 Testing Recommendations

### 1. Test Import
```python
# tests/test_imports.py
def test_quiz_auth_imports():
    """Verify quiz_auth can import authentication functions"""
    try:
        from app.routers.quiz_auth import router
        assert router is not None
    except ImportError as e:
        pytest.fail(f"Import error in quiz_auth: {e}")
```

### 2. Integration Test
```python
# tests/integration/test_quiz_auth.py
def test_quiz_login_endpoint(client):
    """Test quiz login endpoint functionality"""
    response = client.post("/api/quiz/auth/login", json={
        "email": "test@example.com",
        "password": "TestPassword123!",
        "remember_me": False
    })
    assert response.status_code in [200, 401]  # Should not be 500 (ImportError)
```

---

## 📊 Security Status

### Implementação Atual (app/utils/security.py)

**✅ STRENGTHS**:
- Bcrypt com rounds=12
- Tratamento do bug do passlib
- Limite de 72 bytes respeitado
- Error handling robusto
- Logging adequado
- JWT com expiration
- Token type markers

**⚠️ IMPROVEMENTS NEEDED**:
- Adicionar rate limiting no verify_password (proteção contra brute force)
- Implementar account lockout após tentativas falhadas
- Adicionar pepper além do salt do bcrypt
- Considerar argon2 como alternativa ao bcrypt
- Implementar token refresh rotation
- Adicionar token blacklisting

---

## 🎯 Action Items

### Immediate (P0)
- [ ] **FIX**: Corrigir import em `quiz_auth.py` linha 12
- [ ] **TEST**: Executar suite de testes após correção
- [ ] **VERIFY**: Testar endpoint `/api/quiz/auth/login` em staging

### Short-term (P1)
- [ ] **CLEANUP**: Remover ou arquivar `security_bcrypt_backup.py`
- [ ] **DOCS**: Atualizar documentação com estrutura correta de imports
- [ ] **TEST**: Adicionar testes de import verification

### Medium-term (P2)
- [ ] **REVIEW**: Consolidar funções duplicadas entre services
- [ ] **SECURITY**: Implementar rate limiting em verify_password
- [ ] **MONITORING**: Adicionar métricas para tentativas de login

### Long-term (P3)
- [ ] **EVALUATE**: Considerar migração para argon2
- [ ] **IMPLEMENT**: Token rotation completo
- [ ] **ENHANCE**: Adicionar MFA support

---

## 📚 Related Files

```
backend-hormonia/
├── app/
│   ├── core/
│   │   ├── __init__.py (não exporta security)
│   │   └── security_config.py (configuração, não funções)
│   ├── utils/
│   │   ├── security.py ✅ (PRODUÇÃO)
│   │   └── security_bcrypt_backup.py (backup)
│   ├── routers/
│   │   └── quiz_auth.py ❌ (import incorreto)
│   └── services/
│       ├── auth.py ✅
│       ├── admin_user_service.py ✅
│       └── token_rotation_service.py ✅
└── docs/
    └── security/
        ├── AUTHENTICATION_GUIDE.md
        └── JWT_SECURITY_ANALYSIS.md
```

---

## 🔍 Conclusion

**CRITICAL FINDING**: O arquivo `app/routers/quiz_auth.py` contém um import quebrado:
```python
from app.core.security import verify_password, create_access_token  # ❌ MÓDULO NÃO EXISTE
```

**RECOMENDAÇÃO**: Corrigir imediatamente para:
```python
from app.utils.security import verify_password, create_access_token  # ✅ CORRETO
```

**IMPACTO**:
- 🔴 **CRITICAL**: Endpoint de autenticação do quiz pode estar completamente quebrado
- 🔴 **CRITICAL**: ImportError em runtime ao acessar rotas de quiz auth
- 🟡 **MEDIUM**: Possível bypass de autenticação se fallback existe

**NEXT STEPS**:
1. Aplicar correção imediatamente
2. Executar testes end-to-end
3. Verificar logs de produção
4. Implementar testes de import
