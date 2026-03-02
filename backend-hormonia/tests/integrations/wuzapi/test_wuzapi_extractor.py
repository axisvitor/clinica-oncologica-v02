from app.integrations.wuzapi.extractor import (
    RECEIPT_TYPE_TO_STATUS,
    WuzAPIInboundMessage,
    WuzAPIMessageExtractor,
    WuzAPIReceiptEvent,
)


def make_message_payload(
    message_id="ABC123",
    sender="5511987654321@s.whatsapp.net",
    conversation="Hello",
    extended_text=None,
    push_name="Test",
    is_from_me=False,
    wrap=True,
):
    msg = {}
    if conversation is not None:
        msg["Conversation"] = conversation
    if extended_text is not None:
        msg["ExtendedTextMessage"] = {"Text": extended_text}
    inner = {
        "Info": {
            "ID": message_id,
            "Sender": sender,
            "PushName": push_name,
            "IsFromMe": is_from_me,
        },
        "Message": msg,
    }
    if wrap:
        return {"type": "Message", "event": inner}
    return inner


def make_receipt_payload(
    receipt_type="read",
    message_ids=None,
    info_id="ABC123",
    sender="5511987654321@s.whatsapp.net",
):
    inner = {
        "Info": {"ID": info_id, "Sender": sender},
        "Receipt": {"Type": receipt_type},
    }
    if message_ids is not None:
        inner["Receipt"]["MessageIDs"] = message_ids
    return {"type": "ReadReceipt", "event": inner}


class TestExtractMessage:
    def test_extract_message_standard_jid(self):
        payload = make_message_payload(sender="5511987654321@s.whatsapp.net")
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert isinstance(result, WuzAPIInboundMessage)
        assert result.phone == "5511987654321"
        assert result.is_lid is False

    def test_extract_message_conversation_text(self):
        payload = make_message_payload(conversation="Hello doctor")
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result.text == "Hello doctor"

    def test_extract_message_extended_text(self):
        payload = make_message_payload(conversation=None, extended_text="Extended hello")
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result.text == "Extended hello"

    def test_extract_message_no_text(self):
        payload = make_message_payload(conversation=None, extended_text=None)
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result.text == ""

    def test_extract_message_lid_jid(self):
        payload = make_message_payload(sender="12345@lid")
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result.phone == "12345"
        assert result.is_lid is True

    def test_extract_message_hosted_lid(self):
        payload = make_message_payload(sender="12345@hosted.lid")
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result.phone == "12345"
        assert result.is_lid is True

    def test_extract_message_ad_jid(self):
        payload = make_message_payload(sender="55119.0:1@s.whatsapp.net")
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result.phone == "55119"

    def test_extract_message_missing_id(self):
        payload = make_message_payload(message_id=None)
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result is None

    def test_extract_message_missing_sender(self):
        payload = make_message_payload(sender="")
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result is None

    def test_extract_message_flat_payload(self):
        payload = make_message_payload(wrap=False)
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result.message_id == "ABC123"
        assert result.phone == "5511987654321"

    def test_extract_message_push_name(self):
        payload = make_message_payload(push_name="Maria")
        result = WuzAPIMessageExtractor.extract_message(payload)
        assert result.push_name == "Maria"


class TestExtractReceipt:
    def test_extract_receipt_read(self):
        payload = make_receipt_payload(receipt_type="read", message_ids=["A1"])
        result = WuzAPIMessageExtractor.extract_receipt(payload)
        assert isinstance(result, WuzAPIReceiptEvent)
        assert result.receipt_type == "read"
        assert result.message_ids == ["A1"]

    def test_extract_receipt_delivered_empty_string(self):
        payload = make_receipt_payload(receipt_type="", message_ids=["A1"])
        result = WuzAPIMessageExtractor.extract_receipt(payload)
        assert result.receipt_type == ""

    def test_extract_receipt_played(self):
        payload = make_receipt_payload(receipt_type="played", message_ids=["A1"])
        result = WuzAPIMessageExtractor.extract_receipt(payload)
        assert result.receipt_type == "played"

    def test_extract_receipt_no_message_ids_fallback_to_info_id(self):
        payload = make_receipt_payload(message_ids=[], info_id="FALLBACK123")
        result = WuzAPIMessageExtractor.extract_receipt(payload)
        assert result.message_ids == ["FALLBACK123"]

    def test_extract_receipt_no_ids_returns_none(self):
        payload = make_receipt_payload(message_ids=[], info_id="")
        result = WuzAPIMessageExtractor.extract_receipt(payload)
        assert result is None

    def test_receipt_type_to_status_mapping(self):
        assert RECEIPT_TYPE_TO_STATUS == {
            "": "delivered",
            "sender": "sent",
            "read": "read",
            "read-self": "read",
            "played": "played",
            "played-self": "played",
            "retry": "delivered",
        }

    def test_jid_to_phone_empty(self):
        assert WuzAPIMessageExtractor._jid_to_phone("") == ""
