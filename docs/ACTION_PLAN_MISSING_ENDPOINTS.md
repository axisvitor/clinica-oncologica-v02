# 🔧 Plano de Ação - Endpoints Faltantes no Backend

**Data**: 10/11/2025  
**Prioridade**: 🔴 **ALTA**  
**Tempo Estimado**: 2-4 horas  

---

## 📋 Contexto

A revisão completa do código identificou que o **frontend chama 4 endpoints que não estão implementados no backend v2**. Isso pode causar falhas quando usuários tentarem usar essas funcionalidades.

---

## ❌ Endpoints Faltando

### 1. DELETE `/api/v2/patients/{patient_id}`
**Frontend chamando**:
```typescript
delete: async (patientId: string) => {
  return client.delete<{ message: string }>(`/api/v2/patients/${patientId}`)
}
```

**Implementação necessária**: Soft delete de paciente

---

### 2. POST `/api/v2/patients/{patient_id}/activate`
**Frontend chamando**:
```typescript
activate: async (patientId: string) => {
  const patient = await client.post<PatientApiResponse>(`/api/v2/patients/${patientId}/activate`)
  return normalizePatientResponse(patient)
}
```

**Implementação necessária**: Ativar flow do paciente

---

### 3. POST `/api/v2/patients/{patient_id}/deactivate`
**Frontend chamando**:
```typescript
deactivate: async (patientId: string) => {
  const patient = await client.post<PatientApiResponse>(`/api/v2/patients/${patientId}/deactivate`)
  return normalizePatientResponse(patient)
}
```

**Implementação necessária**: Pausar flow do paciente

---

### 4. POST `/api/v2/patients/{patient_id}/restore`
**Frontend chamando**:
```typescript
restore: async (patientId: string) => {
  const patient = await client.post<PatientApiResponse>(`/api/v2/patients/${patientId}/restore`)
  return normalizePatientResponse(patient)
}
```

**Implementação necessária**: Restaurar paciente soft-deleted

---

## 🚀 Implementação Proposta

### Arquivo: `backend-hormonia/app/api/v2/patients_crud.py`

```python
@router.delete(
    "/{patient_id}",
    response_model=dict,
    summary="Delete patient (soft delete)",
    description="Soft delete a patient by setting deleted_at timestamp"
)
@limiter.limit("10/hour")
async def delete_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Soft delete a patient.
    
    Sets deleted_at timestamp without removing from database.
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )
    
    _ensure_patient_access(current_user, patient.doctor_id)
    
    # Soft delete
    from datetime import datetime
    patient.deleted_at = datetime.utcnow()
    db.commit()
    
    # Invalidate caches
    from app.infrastructure.cache import get_unified_cache_manager
    cache_manager = get_unified_cache_manager()
    cache_manager.invalidate_pattern(f"patient_by_id:*:{patient_id}*", namespace="cache")
    cache_manager.invalidate_pattern(f"patient_list:*:{patient.doctor_id}*", namespace="cache")
    
    logger.info(f"Patient {patient_id} soft deleted by {current_user.id}")
    
    return {"message": f"Patient {patient.name} deleted successfully"}


@router.post(
    "/{patient_id}/activate",
    response_model=PatientV2Response,
    summary="Activate patient",
    description="Activate patient flow state"
)
@limiter.limit("30/hour")
async def activate_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Activate patient flow.
    
    Sets flow_state to ACTIVE and resumes flow progression.
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )
    
    _ensure_patient_access(current_user, patient.doctor_id)
    
    # Activate flow
    patient.flow_state = FlowState.ACTIVE
    db.commit()
    db.refresh(patient)
    
    # Publish WebSocket event
    from app.services.websocket_events import websocket_events
    from app.schemas.websocket import WebSocketEventType
    await websocket_events.publish_patient_event(
        event_type=WebSocketEventType.PATIENT_FLOW_CHANGED,
        patient_id=patient_id,
        patient_name=patient.name,
        doctor_id=patient.doctor_id,
        changes={"flow_state": "ACTIVE"},
        metadata={"action": "activated"}
    )
    
    logger.info(f"Patient {patient_id} activated by {current_user.id}")
    
    return _serialize_patient(patient)


@router.post(
    "/{patient_id}/deactivate",
    response_model=PatientV2Response,
    summary="Deactivate patient",
    description="Pause patient flow state"
)
@limiter.limit("30/hour")
async def deactivate_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Pause patient flow.
    
    Sets flow_state to PAUSED and stops flow progression.
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.is_(None)
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with id {patient_id} not found"
        )
    
    _ensure_patient_access(current_user, patient.doctor_id)
    
    # Pause flow
    patient.flow_state = FlowState.PAUSED
    db.commit()
    db.refresh(patient)
    
    # Publish WebSocket event
    from app.services.websocket_events import websocket_events
    from app.schemas.websocket import WebSocketEventType
    await websocket_events.publish_patient_event(
        event_type=WebSocketEventType.PATIENT_FLOW_CHANGED,
        patient_id=patient_id,
        patient_name=patient.name,
        doctor_id=patient.doctor_id,
        changes={"flow_state": "PAUSED"},
        metadata={"action": "deactivated"}
    )
    
    logger.info(f"Patient {patient_id} deactivated by {current_user.id}")
    
    return _serialize_patient(patient)


@router.post(
    "/{patient_id}/restore",
    response_model=PatientV2Response,
    summary="Restore patient",
    description="Restore a soft-deleted patient"
)
@limiter.limit("10/hour")
async def restore_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_session),
):
    """
    Restore soft-deleted patient.
    
    Clears deleted_at timestamp to restore patient.
    """
    try:
        patient_uuid = UUID(patient_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patient ID format"
        )
    
    # Query including soft-deleted patients
    patient = db.query(Patient).filter(
        Patient.id == patient_uuid,
        Patient.deleted_at.isnot(None)  # Only soft-deleted patients
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No deleted patient found with id {patient_id}"
        )
    
    _ensure_patient_access(current_user, patient.doctor_id)
    
    # Restore patient
    patient.deleted_at = None
    db.commit()
    db.refresh(patient)
    
    # Invalidate caches
    from app.infrastructure.cache import get_unified_cache_manager
    cache_manager = get_unified_cache_manager()
    cache_manager.invalidate_pattern(f"patient_by_id:*:{patient_id}*", namespace="cache")
    cache_manager.invalidate_pattern(f"patient_list:*:{patient.doctor_id}*", namespace="cache")
    
    logger.info(f"Patient {patient_id} restored by {current_user.id}")
    
    return _serialize_patient(patient)
```

---

## ✅ Checklist de Implementação

- [ ] Adicionar endpoint `DELETE /{patient_id}` (soft delete)
- [ ] Adicionar endpoint `POST /{patient_id}/activate`
- [ ] Adicionar endpoint `POST /{patient_id}/deactivate`
- [ ] Adicionar endpoint `POST /{patient_id}/restore`
- [ ] Testar cada endpoint via Postman/Insomnia
- [ ] Atualizar documentação OpenAPI/Swagger
- [ ] Adicionar testes unitários
- [ ] Validar integração com frontend
- [ ] Deploy em homologação
- [ ] Verificar logs e métricas

---

## 🧪 Casos de Teste

### 1. Delete Patient
```bash
DELETE /api/v2/patients/{patient_id}
Authorization: Bearer {token}

# Espera: 200 OK
{
  "message": "Patient João Silva deleted successfully"
}
```

### 2. Activate Patient
```bash
POST /api/v2/patients/{patient_id}/activate
Authorization: Bearer {token}

# Espera: 200 OK + PatientV2Response com flow_state="active"
```

### 3. Deactivate Patient
```bash
POST /api/v2/patients/{patient_id}/deactivate
Authorization: Bearer {token}

# Espera: 200 OK + PatientV2Response com flow_state="paused"
```

### 4. Restore Patient
```bash
POST /api/v2/patients/{patient_id}/restore
Authorization: Bearer {token}

# Espera: 200 OK + PatientV2Response com deleted_at=null
```

---

## 📝 Notas Técnicas

1. **Soft Delete**: Usa `deleted_at` timestamp para permitir auditoria
2. **RBAC**: Validação via `_ensure_patient_access()` garante que apenas o médico responsável ou admin pode modificar
3. **Rate Limiting**: 
   - Delete/Restore: 10/hour (operações sensíveis)
   - Activate/Deactivate: 30/hour
4. **Cache Invalidation**: Limpa cache de patient após operações
5. **WebSocket Events**: Publica eventos para atualização em tempo real no frontend
6. **Logging**: Registra todas as operações para auditoria

---

## 🎯 Prioridade de Implementação

1. **DELETE** (mais usado) - 30 min
2. **ACTIVATE/DEACTIVATE** (fluxo de trabalho) - 45 min
3. **RESTORE** (menos usado) - 30 min
4. **Testes** - 1 hora

**Total Estimado: 2h45min**

---

## 📚 Referências

- Documentação completa: `docs/COMPLETE_CODE_REVIEW_2025-11-10.md`
- Análise de fluxo de paciente: `backend-hormonia/docs/database/PATIENT_FLOW_COMPLETE_ANALYSIS.md`
- Frontend API Client: `frontend-hormonia/src/lib/api-client/patients.ts`
