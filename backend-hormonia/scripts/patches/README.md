# Database Patches

Este diretório contém scripts históricos de correção (patches) para o banco de dados.

##   Aviso Importante

Estes scripts são **one-off patches** aplicados em momentos específicos do desenvolvimento para corrigir problemas de dados. Eles **NÃO devem ser executados novamente** em produção, pois já foram aplicados.

## =Ë Inventário de Patches

### Quiz Mensal - Patches de Migração

Scripts utilizados durante a migração do sistema de quiz mensal:

- `monthly_quiz_data_patch.py` - Migração inicial de dados do quiz mensal
- `monthly_quiz_question_patch.py` - Correção de estrutura de perguntas
- `monthly_quiz_response_patch.py` - Correção de respostas armazenadas
- `monthly_quiz_validation_patch.py` - Validação e correção de dados inconsistentes

## = Status

**Status**:  Aplicados e arquivados
**Última aplicação**: Durante migração para v2
**Ambiente**: Desenvolvimento/Staging

## =Ý Uso Histórico

Estes patches foram criados para resolver problemas específicos identificados durante o desenvolvimento:

1. **Migração de dados do quiz mensal** - Transferência de dados do sistema antigo
2. **Correção de estruturas** - Ajuste de schemas e tipos de dados
3. **Validação de integridade** - Garantia de consistência referencial

## =€ Para Desenvolvedores

Se você precisa fazer alterações no banco de dados:

1. **Use Alembic migrations** para mudanças de schema:
   ```bash
   alembic revision --autogenerate -m "description"
   alembic upgrade head
   ```

2. **Para correções de dados pontuais**, crie um novo script documentado neste diretório com:
   - Nome descritivo e data: `YYYY_MM_DD_description_patch.py`
   - Comentários explicando o problema e a solução
   - Verificações de segurança (dry-run, backup check)
   - Log de execução

3. **Nunca execute patches antigos** sem antes:
   - Verificar se já foram aplicados
   - Fazer backup completo do banco
   - Testar em ambiente de desenvolvimento

## =Ú Referências

- [Guia de Migrations](../docs/deployment/MIGRATIONS_GUIDE.md)
- [Documentação do Banco](../docs/db/BANCO_DE_DADOS_COMPLETO.md)
- [Schema Master](../SCHEMA_MASTER_COMPLETO.sql)

---

**Última atualização**: 2025-10-02
**Mantido por**: Backend Team
