"""Tests for webhook message extraction utilities."""

from app.services.webhook.utils.message_extractor import extract_message_data


def test_extract_message_data_prefers_remote_jid_alt_for_lid():
    payload = {
        "instance": "meuwhatsapp",
        "data": {
            "key": {
                "id": "msg-1",
                "fromMe": False,
                "remoteJid": "173396503580849@lid",
                "remoteJidAlt": "5594991307744@s.whatsapp.net",
                "addressingMode": "lid",
            },
            "message": {"conversation": "ok"},
            "messageTimestamp": 1739846400,
            "pushName": "Paciente",
        },
    }

    extracted = extract_message_data(payload)

    assert extracted is not None
    assert extracted["phone"] == "5594991307744"
    assert extracted["metadata"]["remote_jid"] == "5594991307744@s.whatsapp.net"
    assert extracted["metadata"]["remote_jid_raw"] == "173396503580849@lid"
    assert extracted["metadata"]["remote_jid_alt"] == "5594991307744@s.whatsapp.net"
    assert extracted["metadata"]["is_lid"] is True


def test_extract_message_data_prefers_participant_alt_when_available():
    payload = {
        "instance": "meuwhatsapp",
        "data": {
            "key": {
                "id": "msg-2",
                "fromMe": False,
                "remoteJid": "12036300000000@g.us",
                "participant": "173396503580849@lid",
                "participantAlt": "5594991307744@s.whatsapp.net",
            },
            "message": {"conversation": "resposta"},
            "messageTimestamp": 1739846400,
        },
    }

    extracted = extract_message_data(payload)

    assert extracted is not None
    assert extracted["phone"] == "5594991307744"
    assert extracted["metadata"]["participant_jid"] == "5594991307744@s.whatsapp.net"
    assert extracted["metadata"]["participant_jid_raw"] == "173396503580849@lid"
