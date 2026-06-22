from app.schemas.chat import ChatMessage


def test_chat_message_text():
    m = ChatMessage(
        id="m1", sender_id="p1", channel="hall",
        content_type="text", text="hello",
    )
    assert m.channel == "hall"
    assert m.text == "hello"
    assert m.recipients is None


def test_spatial_message_has_recipients():
    m = ChatMessage(
        id="m2", sender_id="p1", channel="spatial_normal",
        content_type="text", text="help", recipients=["p2", "p3"],
    )
    assert m.recipients == ["p2", "p3"]
