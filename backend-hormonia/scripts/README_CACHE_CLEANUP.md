# Python Cache Cleanup Scripts

## 📋 Visão Geral

Scripts para limpar arquivos de cache Python que não deveriam estar no repositório Git.

## 🔍 Problema Identificado

- **1.154 diretórios** `__pycache__/` no repositório
- **7.587 arquivos** `.pyc` rastreados pelo Git
- Diretórios `venv/` e `venv_linux/` no controle de versão

## 🛠️ Scripts Disponíveis

### 1. `clean_python_cache.sh`
**Remove fisicamente** todos os arquivos de cache Python do projeto.

```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1
./backend-hormonia/scripts/clean_python_cache.sh
```

**O que faz:**
- Remove todos os diretórios `__pycache__/`
- Remove todos os arquivos `.pyc` e `.pyo`
- Remove `.pytest_cache/`, `.tox/`, `.mypy_cache/`, `.ruff_cache/`
- Remove `*.egg-info/`, `.coverage`, `htmlcov/`
- Exibe estatísticas de limpeza

**Seguro para executar múltiplas vezes** - operação idempotente.

---

### 2. `git_remove_cache.sh`
**Remove do Git** (unstage) sem deletar do disco.

```bash
cd /mnt/c/Meu\ Projetos/clinica-oncologica-v02-1
./backend-hormonia/scripts/git_remove_cache.sh
```

**O que faz:**
- Remove `__pycache__/` do índice Git
- Remove `*.pyc` e `*.pyo` do rastreamento
- Remove `venv/`, `venv_linux/`, `ENV/` do Git
- Remove `.pytest_cache/` e outros caches de teste
- Mantém os arquivos no disco

**Importante:** Após executar, você precisa fazer commit:
```bash
git commit -m "chore: remove Python cache files from git tracking"
```

---

## 🚀 Execução Completa Recomendada

Execute na seguinte ordem:

```bash
# 1. Limpar fisicamente os arquivos
./backend-hormonia/scripts/clean_python_cache.sh

# 2. Remover do Git
./backend-hormonia/scripts/git_remove_cache.sh

# 3. Verificar mudanças
git status

# 4. Fazer commit
git commit -m "chore: remove Python cache files and venv from repository"

# 5. Push (se necessário)
git push
```

---

## 📝 Atualização do .gitignore

O `.gitignore` na raiz do projeto foi atualizado com:

```gitignore
# Python - Bytecode and Cache
__pycache__/
*.pyc
*.pyo

# Virtual Environments
venv/
venv_linux/
**/.venv/

# Testing
.pytest_cache/
**/.pytest_cache/
.mypy_cache/
.ruff_cache/
.tox/
```

---

## ✅ Verificação

Após executar os scripts, verifique:

```bash
# Deve retornar 0
find . -type d -name "__pycache__" | wc -l

# Deve retornar 0
find . -type f -name "*.pyc" | wc -l

# Git status não deve mostrar __pycache__ ou .pyc
git status
```

---

## 🔄 Prevenção Futura

**Adicione ao seu workflow:**

```bash
# Antes de commit, limpe o cache
./backend-hormonia/scripts/clean_python_cache.sh

# Configure Git hooks (opcional)
echo "./backend-hormonia/scripts/clean_python_cache.sh" > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## 🐛 Troubleshooting

### Erro: "Permission denied"
```bash
chmod +x backend-hormonia/scripts/*.sh
```

### Arquivos ainda aparecem no Git
```bash
# Force remove do índice
git rm -r --cached --force **/__pycache__
git commit -m "chore: force remove cache files"
```

### Cache reaparece após instalação de pacotes
**Normal!** Python gera cache automaticamente. O `.gitignore` impedirá que sejam rastreados.

---

## 📊 Impacto Estimado

- **Redução de arquivos rastreados:** ~8.700 arquivos
- **Redução de tamanho do repo:** Variável (depende do histórico)
- **Tempo de execução:** ~30-60 segundos

---

## 🔐 Segurança

Os scripts são seguros:
- Não modificam código-fonte
- Não afetam dependências instaladas
- Podem ser revertidos (arquivos podem ser regenerados)
- Usam `--ignore-unmatch` para evitar erros

---

## 📚 Referências

- [Python .gitignore patterns](https://github.com/github/gitignore/blob/main/Python.gitignore)
- [Git rm documentation](https://git-scm.com/docs/git-rm)
- [Managing Python cache](https://docs.python.org/3/using/cmdline.html#cmdoption-B)
