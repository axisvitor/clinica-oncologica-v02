# 🚨 CORREÇÕES CRÍTICAS DE PERFORMANCE E BUGS

## 📋 PROBLEMAS IDENTIFICADOS:

### 🔥 CRÍTICOS (Impacto Alto):
1. **Firebase Auth**: `_get_user_from_db` assinatura incorreta
2. **Monthly Quiz**: 404s corretos mas lentos (7-8s)
3. **Dashboard Analytics**: Consultas N+1 (80+ queries)
4. **Reports/Alerts**: 500 errors (PaginationParams)
5. **Login/Sessão**: 3.3s de latência

### ⚡ PERFORMANCE:
6. **Índices Faltando**: messages, alerts
7. **Cache**: monthly-quiz stats sem cache
8. **Quick Stats**: múltiplas consultas
9. **User Preferences**: 404 endpoint inexistente

### 🔧 HOUSEKEEPING:
10. **Paralelismo Excessivo**: múltiplas chamadas simultâneas
11. **Query Monitor**: overhead desnecessário

## 🎯 PLANO DE EXECUÇÃO:
1. Corrigir Firebase Auth (crítico)
2. Implementar índices de performance
3. Otimizar monthly-quiz (404 rápido)
4. Consolidar analytics queries
5. Corrigir PaginationParams
6. Implementar cache estratégico
7. Adicionar user preferences endpoint
8. Otimizar login/sessão