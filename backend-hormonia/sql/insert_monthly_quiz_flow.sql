-- Script para atualizar flow_template_versions com dados do arquivo JSON

-- Inserir flow_kind se não existir
INSERT INTO public.flow_kinds (id, kind_key, display_name, description, is_active, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'monthly_quiz',
    'Quiz Mensal',
    'Fluxo de questionário mensal para pacientes',
    true,
    NOW(),
    NOW()
) ON CONFLICT (kind_key) DO NOTHING;

-- Obter o ID do flow_kind
DO $$
DECLARE
    v_flow_kind_id UUID;
BEGIN
    SELECT id INTO v_flow_kind_id FROM public.flow_kinds WHERE kind_key = 'monthly_quiz';
    
    -- Inserir a nova versão do template
    INSERT INTO public.flow_template_versions (
        id,
        flow_kind_id,
        version_number,
        template_name,
        description,
        steps,
        metadata,
        is_active,
        is_draft,
        created_by,
        created_at,
        updated_at
    ) VALUES (
        gen_random_uuid(),
        v_flow_kind_id,
        1,
        'Quiz Mensal - Versão 1.0',
        'Fluxo de questionário mensal para acompanhamento de pacientes',
        '[
            {
                "step_number": 1,
                "step_key": "welcome",
                "step_type": "message",
                "content": {
                    "text": "Olá! 👋 Bem-vindo ao seu questionário mensal de acompanhamento. Vamos verificar como você está se sentindo este mês.",
                    "message_type": "text"
                },
                "actions": [],
                "next_step_key": "question_1",
                "conditions": {}
            },
            {
                "step_number": 2,
                "step_key": "question_1",
                "step_type": "quiz_question",
                "content": {
                    "text": "Como você está se sentindo em relação ao seu tratamento neste mês?",
                    "message_type": "quiz_question",
                    "question": {
                        "question_id": "monthly_feeling",
                        "question_text": "Como você está se sentindo em relação ao seu tratamento neste mês?",
                        "question_type": "single_choice",
                        "options": [
                            {"value": "muito_bem", "text": "Muito bem", "score": 5},
                            {"value": "bem", "text": "Bem", "score": 4},
                            {"value": "regular", "text": "Regular", "score": 3},
                            {"value": "mal", "text": "Mal", "score": 2},
                            {"value": "muito_mal", "text": "Muito mal", "score": 1}
                        ],
                        "required": true,
                        "allow_other": false
                    }
                },
                "actions": [],
                "next_step_key": "question_2",
                "conditions": {}
            },
            {
                "step_number": 3,
                "step_key": "question_2",
                "step_type": "quiz_question",
                "content": {
                    "text": "Você conseguiu seguir suas orientações médicas corretamente este mês?",
                    "message_type": "quiz_question",
                    "question": {
                        "question_id": "treatment_compliance",
                        "question_text": "Você conseguiu seguir suas orientações médicas corretamente este mês?",
                        "question_type": "single_choice",
                        "options": [
                            {"value": "sempre", "text": "Sempre", "score": 5},
                            {"value": "maioria_vezes", "text": "Na maioria das vezes", "score": 4},
                            {"value": "as_vezes", "text": "Às vezes", "score": 3},
                            {"value": "raramente", "text": "Raramente", "score": 2},
                            {"value": "nunca", "text": "Nunca", "score": 1}
                        ],
                        "required": true,
                        "allow_other": false
                    }
                },
                "actions": [],
                "next_step_key": "question_3",
                "conditions": {}
            },
            {
                "step_number": 4,
                "step_key": "question_3",
                "step_type": "quiz_question",
                "content": {
                    "text": "Você teve algum efeito colateral que te incomodou este mês?",
                    "message_type": "quiz_question",
                    "question": {
                        "question_id": "side_effects",
                        "question_text": "Você teve algum efeito colateral que te incomodou este mês?",
                        "question_type": "single_choice",
                        "options": [
                            {"value": "nenhum", "text": "Nenhum", "score": 5},
                            {"value": "leves", "text": "Leves", "score": 4},
                            {"value": "moderados", "text": "Moderados", "score": 3},
                            {"value": "severos", "text": "Severos", "score": 2},
                            {"value": "muito_severos", "text": "Muito severos", "score": 1}
                        ],
                        "required": true,
                        "allow_other": false
                    }
                },
                "actions": [],
                "next_step_key": "question_4",
                "conditions": {}
            },
            {
                "step_number": 5,
                "step_key": "question_4",
                "step_type": "quiz_question",
                "content": {
                    "text": "Como está sua qualidade de vida geral neste mês?",
                    "message_type": "quiz_question",
                    "question": {
                        "question_id": "quality_of_life",
                        "question_text": "Como está sua qualidade de vida geral neste mês?",
                        "question_type": "single_choice",
                        "options": [
                            {"value": "excelente", "text": "Excelente", "score": 5},
                            {"value": "boa", "text": "Boa", "score": 4},
                            {"value": "razoavel", "text": "Razoável", "score": 3},
                            {"value": "ruim", "text": "Ruim", "score": 2},
                            {"value": "muito_ruim", "text": "Muito ruim", "score": 1}
                        ],
                        "required": true,
                        "allow_other": false
                    }
                },
                "actions": [],
                "next_step_key": "question_5",
                "conditions": {}
            },
            {
                "step_number": 6,
                "step_key": "question_5",
                "step_type": "quiz_question",
                "content": {
                    "text": "Você tem alguma dúvida ou preocupação que gostaria de discutir com seu médico?",
                    "message_type": "quiz_question",
                    "question": {
                        "question_id": "concerns",
                        "question_text": "Você tem alguma dúvida ou preocupação que gostaria de discutir com seu médico?",
                        "question_type": "single_choice",
                        "options": [
                            {"value": "nao", "text": "Não", "score": 5},
                            {"value": "poucas", "text": "Poucas", "score": 4},
                            {"value": "algumas", "text": "Algumas", "score": 3},
                            {"value": "muitas", "text": "Muitas", "score": 2},
                            {"value": "urgentes", "text": "Urgentes", "score": 1}
                        ],
                        "required": true,
                        "allow_other": false
                    }
                },
                "actions": [],
                "next_step_key": "completion",
                "conditions": {}
            },
            {
                "step_number": 7,
                "step_key": "completion",
                "step_type": "message",
                "content": {
                    "text": "Obrigado por responder ao questionário! 🎉 Suas respostas ajudam seu médico a acompanhar melhor seu tratamento. Seu médico será notificado sobre suas respostas e entrará em contato se necessário.",
                    "message_type": "text"
                },
                "actions": [],
                "next_step_key": null,
                "conditions": {}
            }
        ]'::jsonb,
        '{"schedule": {"frequency": "monthly", "day_of_month": 1, "time": "09:00"}, "notifications": {"reminders": [1, 3, 7], "completion_message": true}}'::jsonb,
        true,
        false,
        NULL,
        NOW(),
        NOW()
    );
    
    RAISE NOTICE 'Flow template version para monthly_quiz inserida com sucesso';
END $$;

-- Verificar se a inserção foi bem-sucedida
SELECT 
    ftv.id,
    ftv.template_name,
    ftv.version_number,
    ftv.is_active,
    fk.display_name as flow_kind_name,
    jsonb_array_length(ftv.steps) as total_steps
FROM public.flow_template_versions ftv
JOIN public.flow_kinds fk ON ftv.flow_kind_id = fk.id
WHERE fk.kind_key = 'monthly_quiz'
ORDER BY ftv.version_number DESC
LIMIT 1;
