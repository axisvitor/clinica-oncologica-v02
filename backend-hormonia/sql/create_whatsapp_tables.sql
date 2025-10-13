-- Idempotent creation of WhatsApp persistence tables
-- Aligns with backend-hormonia/app/integrations/whatsapp/models/message.py

DO $$ BEGIN
    -- whatsapp_messages
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema='public' AND table_name='whatsapp_messages'
    ) THEN
        CREATE TABLE public.whatsapp_messages (
            id TEXT PRIMARY KEY,
            instance_name TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            message_type TEXT NOT NULL,
            content TEXT NULL,
            media_url TEXT NULL,
            media_caption TEXT NULL,
            status TEXT DEFAULT 'pending',
            external_id TEXT UNIQUE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            sent_at TIMESTAMP WITHOUT TIME ZONE NULL,
            delivered_at TIMESTAMP WITHOUT TIME ZONE NULL,
            read_at TIMESTAMP WITHOUT TIME ZONE NULL,
            failed_at TIMESTAMP WITHOUT TIME ZONE NULL,
            retry_count INTEGER DEFAULT 0,
            error_message TEXT NULL,
            message_data JSON NULL
        );
        CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_instance ON public.whatsapp_messages(instance_name);
        CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_chat ON public.whatsapp_messages(chat_id);
        CREATE INDEX IF NOT EXISTS ix_whatsapp_messages_external ON public.whatsapp_messages(external_id);
    END IF;

    -- whatsapp_contacts
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema='public' AND table_name='whatsapp_contacts'
    ) THEN
        CREATE TABLE public.whatsapp_contacts (
            id TEXT PRIMARY KEY,
            instance_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            formatted_number TEXT NOT NULL,
            name TEXT NULL,
            profile_picture_url TEXT NULL,
            is_whatsapp_user BOOLEAN DEFAULT TRUE,
            last_seen TIMESTAMP WITHOUT TIME ZONE NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            contact_data JSON NULL
        );
        CREATE INDEX IF NOT EXISTS ix_whatsapp_contacts_instance ON public.whatsapp_contacts(instance_name);
        CREATE INDEX IF NOT EXISTS ix_whatsapp_contacts_phone ON public.whatsapp_contacts(phone_number);
    END IF;

    -- whatsapp_instances
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema='public' AND table_name='whatsapp_instances'
    ) THEN
        CREATE TABLE public.whatsapp_instances (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'disconnected',
            qr_code TEXT NULL,
            webhook_url TEXT NULL,
            phone_number TEXT NULL,
            profile_name TEXT NULL,
            profile_picture_url TEXT NULL,
            is_connected BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            last_activity TIMESTAMP WITHOUT TIME ZONE NULL,
            settings JSON NULL
        );
        CREATE INDEX IF NOT EXISTS ix_whatsapp_instances_name ON public.whatsapp_instances(name);
    END IF;
END $$;


