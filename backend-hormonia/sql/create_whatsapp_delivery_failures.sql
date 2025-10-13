-- ====================================================================================
-- WhatsApp Delivery Failures (DLQ) – criação da tabela e objetos auxiliares
-- Execute este script em uma sessão com privilégios suficientes (ex.: superuser ou
-- usuário com permissão para criar tabelas/índices/funções).
-- ====================================================================================

BEGIN;

-- 1) Garante que o suporte a UUID aleatório esteja disponível
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2) Cria (se não existir) a tabela whatsapp_delivery_failures
CREATE TABLE IF NOT EXISTS public.whatsapp_delivery_failures (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES public.patients(id) ON DELETE CASCADE,
    phone_number        VARCHAR(20) NOT NULL,
    message_type        VARCHAR(50) NOT NULL,
    message_content     TEXT,
    error_message       TEXT NOT NULL,
    error_code          VARCHAR(50),
    retry_count         INTEGER NOT NULL DEFAULT 0,
    max_retries         INTEGER NOT NULL DEFAULT 3,
    next_retry_at       TIMESTAMPTZ,
    last_retry_at       TIMESTAMPTZ,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    resolved_at         TIMESTAMPTZ,
    metadata            JSONB DEFAULT '{}'::jsonb,
    reviewed_by         UUID REFERENCES public.users(id) ON DELETE SET NULL,
    original_message_id UUID REFERENCES public.messages(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT whatsapp_delivery_failures_status_check
        CHECK (status IN ('pending', 'retrying', 'failed', 'resolved'))
);

COMMENT ON TABLE public.whatsapp_delivery_failures
    IS 'Dead Letter Queue (DLQ) para falhas de envio de mensagens WhatsApp.';
COMMENT ON COLUMN public.whatsapp_delivery_failures.metadata
    IS 'Informações adicionais da falha, em JSONB.';
COMMENT ON COLUMN public.whatsapp_delivery_failures.status
    IS 'Status do item na fila: pending | retrying | failed | resolved.';

-- 3) Índices auxiliares para performance em consultas frequentes
CREATE INDEX IF NOT EXISTS idx_whatsapp_delivery_failures_patient
    ON public.whatsapp_delivery_failures(patient_id);

CREATE INDEX IF NOT EXISTS idx_whatsapp_delivery_failures_status_nextretry
    ON public.whatsapp_delivery_failures(status, next_retry_at);

CREATE INDEX IF NOT EXISTS idx_whatsapp_delivery_failures_created_at
    ON public.whatsapp_delivery_failures(created_at DESC);

-- 4) Cria (se necessário) a função genérica que atualiza o campo updated_at
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   pg_proc
        WHERE  proname = 'update_updated_at_column'
           AND pg_catalog.pg_function_is_visible(oid)
    ) THEN
        CREATE OR REPLACE FUNCTION public.update_updated_at_column()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $func$
        BEGIN
            NEW.updated_at := timezone('utc', now());
            RETURN NEW;
        END;
        $func$;
    END IF;
END;
$$;

-- 5) Cria o trigger para manter updated_at sempre atualizado
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE  tgname = 'trg_whatsapp_delivery_failures_updated_at'
    ) THEN
        CREATE TRIGGER trg_whatsapp_delivery_failures_updated_at
        BEFORE UPDATE ON public.whatsapp_delivery_failures
        FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
    END IF;
END;
$$;

COMMIT;

-- ====================================================================================
-- Após a execução:
--   • A tabela whatsapp_delivery_failures estará criada (com relações e índices).
--   • O campo updated_at será ajustado automaticamente em updates.
--   • Sempre que um paciente for excluído, os registros associados nesta tabela serão
--     removidos automaticamente (ON DELETE CASCADE).
-- ====================================================================================
