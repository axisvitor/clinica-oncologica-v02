# [P0] Corrigir Event Loop Leak em Background Flow Tasks

## 🚨 Prioridade: P0 - CRÍTICO

**Componente:** WhatsApp Webhook Handler  
**Arquivo:** `file:backend-hormonia/app/integrations/whatsapp/api/webhooks.py:397-446`  
**Impacto:** Memory leak, degradação de performance, possível crash

---

## 📝 Descrição do Problema

A função `_trigger_flow_response_async()` tem um bug onde o event loop pode não ser fechado corretamente se uma exception ocorrer antes da criação do loop.

### Código Atual (Bugado)

```python
async def _trigger_flow_response_async(patient_id: str, content: str):
    def _run_hybrid_flow():
        try:
            loop = asyncio.new_event_loop()  # ❌ Se falhar aqui, loop não definido
            asyncio.set_event_loop(loop)
            
            with get_scoped_session() as sync_db:
                engine = get_enhanced_flow_engine(sync_db)
                loop.run_until_complete(
                    engine.process_patient_response(patient_id, content)
                )
            
            loop.close()  # ⚠️ Pode não executar se exception antes
            
        except Exception as e:
            logger.error(...)
            try:
                loop.close()  # ❌ NameError se loop não foi criado
            except Exception as close_err:
                logger.debug(...)
```

### Problema

1. Se exception ocorrer antes de `loop = asyncio.new_event_loop()`, a variável `loop` não existe
2. No bloco `except`, tentar acessar `loop.close()` causa `NameError`
3. Event loop não é fechado → memory leak
4. Ao longo do tempo, múltiplos loops vazam memória

---

## ✅ Solução Proposta

### Código Corrigido

```python
async def _trigger_flow_response_async(patient_id: str, content: str):
    """
    Trigger flow engine in background with proper event loop management.
    
    FIX P0-1: Ensure event loop is always closed, even if exception occurs
    before loop creation.
    """
    import asyncio
    from app.database import get_scoped_session
    from app.services.enhanced_flow_engine import get_enhanced_flow_engine
    
    logger.info(f"Starting background flow processing for patient {patient_id}")
    
    def _run_hybrid_flow():
        loop = None  # ✅ Declare outside try to ensure it's always defined
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            with get_scoped_session() as sync_db:
                engine = get_enhanced_flow_engine(sync_db)
                loop.run_until_complete(
                    engine.process_patient_response(patient_id, content)
                )
            
            logger.info(f"Completed flow processing for patient {patient_id}")
        
        except Exception as e:
            logger.error(
                f"Error in background flow thread for patient {patient_id}: {e}",
                exc_info=True
            )
        
        finally:
            # ✅ Always close loop, even if exception occurred
            if loop is not None:
                try:
                    loop.close()
                    logger.debug(f"Event loop closed for patient {patient_id}")
                except Exception as close_err:
                    logger.debug(
                        f"Event loop close error (non-critical): {close_err}"
                    )
    
    # Run in executor to avoid blocking main event loop
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run_hybrid_flow)
    except Exception as e:
        logger.error(f"Failed to schedule background flow task: {e}", exc_info=True)
```

---

## 🎯 Acceptance Criteria

### Funcional

- [ ] Event loop sempre fechado, mesmo com exceptions
- [ ] Logging adequado em todos os caminhos de execução
- [ ] Flow engine continua funcionando normalmente
- [ ] Mensagens de follow-up enviadas corretamente

### Performance

- [ ] Sem memory leak após 1000 mensagens processadas
- [ ] Tempo de processamento < 5s (p95)
- [ ] Sem degradação de performance ao longo do tempo

### Testes

- [ ] Teste unitário: exception antes de criar loop
- [ ] Teste unitário: exception durante `run_until_complete()`
- [ ] Teste unitário: exception no `finally` block
- [ ] Teste de carga: 100 webhooks concorrentes
- [ ] Teste de memory leak: 1000 mensagens sem crescimento de memória

---

## 🧪 Plano de Testes

### Teste 1: Exception Antes de Criar Loop

```python
@pytest.mark.asyncio
async def test_event_loop_leak_before_creation(mocker):
    """Testa que loop não vaza se exception antes de criar."""
    
    # Mock get_scoped_session para falhar
    mocker.patch(
        'app.database.get_scoped_session',
        side_effect=Exception("DB connection failed")
    )
    
    # Executar função
    await _trigger_flow_response_async("patient_123", "test message")
    
    # Verificar que não há event loops abertos
    # (não deve ter NameError)
    assert True  # Se chegou aqui, não teve NameError
```

### Teste 2: Memory Leak com 1000 Mensagens

```python
@pytest.mark.load
async def test_no_memory_leak_1000_messages():
    """Testa que não há memory leak após 1000 mensagens."""
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Processar 1000 mensagens
    for i in range(1000):
        await _trigger_flow_response_async(f"patient_{i}", f"message {i}")
    
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    # Memória não deve crescer mais de 50MB
    assert memory_increase < 50, f"Memory leak detected: {memory_increase}MB increase"
```

---

## 📊 Impacto Estimado

### Antes da Correção

- Memory leak: ~1MB por 100 mensagens
- Após 10.000 mensagens: ~100MB vazados
- Possível crash após 24h de operação

### Depois da Correção

- Memory leak: 0MB
- Operação estável por tempo indefinido
- Performance consistente

---

## 🔗 Referências

- **Spec:** `spec:329825c3-b03b-4873-a5bd-7d304c0082f6/whatsapp-integration-review`
- **Debug Report:** `file:docs/features/whatsapp/whatsapp-integration-debug-report.md`
- **Arquivo:** `file:backend-hormonia/app/integrations/whatsapp/api/webhooks.py`

---

## ⏱️ Estimativa

- **Desenvolvimento:** 2 horas
- **Testes:** 3 horas
- **Code Review:** 1 hora
- **Total:** 6 horas (1 dia)

---

## 🚀 Deploy Plan

1. Implementar correção em branch `fix/p0-event-loop-leak`
2. Executar testes unitários e de carga
3. Code review com 2 aprovações
4. Deploy em staging
5. Monitorar memória por 24h
6. Deploy em produção
7. Monitorar por 48h

---

**Criado:** 2025-01-08  
**Prioridade:** P0 - CRÍTICO  
**Estimativa:** 1 dia