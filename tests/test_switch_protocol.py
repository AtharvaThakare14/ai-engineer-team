"""Tests for Switch Agent Protocol client and wire contract."""

import json
import pytest
from engineering_team.integrations.switch_client import SwitchClient
from engineering_team.models import SwitchEvent


@pytest.mark.asyncio
async def test_switch_mock_registration(switch_client: SwitchClient):
    """Test registering an agent in Switch."""
    resp = await switch_client.register_agent(name="engineer-bot")
    assert resp.id.startswith("agent_engineer-bot_")
    assert len(resp.api_key) > 0


@pytest.mark.asyncio
async def test_switch_connection_state_frame(switch_client: SwitchClient):
    """Test handling of connection_state frames."""
    frame = json.dumps({
        "type": "connection_state",
        "cursor": 42,
        "generation": "gen_abc123",
        "rooms": ["room_1", "room_2"]
    })
    await switch_client.handle_event(frame)
    assert switch_client.cursor == 42
    assert switch_client.generation == "gen_abc123"
    assert "room_1" in switch_client.claimed_rooms


@pytest.mark.asyncio
async def test_switch_addressed_message_routing(switch_client: SwitchClient):
    """Test that only addressed messages trigger registered handlers."""
    received = []

    def handler(evt: SwitchEvent):
        received.append(evt)

    switch_client.add_message_handler(handler)

    # 1. Send unaddressed message -> should be ignored
    unaddressed_frame = json.dumps({
        "event": "message",
        "room_id": "room_dev",
        "cursor": 43,
        "payload": {
            "content": "Hey everyone",
            "sender_id": "alice",
            "addressed": False,
            "message_id": "msg_001"
        }
    })
    await switch_client.handle_event(unaddressed_frame)
    assert len(received) == 0

    # 2. Send addressed message -> should be received
    addressed_frame = json.dumps({
        "event": "message",
        "room_id": "room_dev",
        "cursor": 44,
        "payload": {
            "content": "@engineer-bot fix the bug in app.py",
            "sender_id": "alice",
            "addressed": True,
            "message_id": "msg_002"
        }
    })
    await switch_client.handle_event(addressed_frame)
    assert len(received) == 1
    assert received[0].payload.content == "@engineer-bot fix the bug in app.py"
    assert switch_client.cursor == 44


@pytest.mark.asyncio
async def test_duplicate_message_prevention(switch_client: SwitchClient):
    """Test that messages with identical message_ids are not processed twice."""
    received = []
    switch_client.add_message_handler(lambda evt: received.append(evt))

    msg_frame = json.dumps({
        "event": "message",
        "room_id": "room_dev",
        "payload": {
            "content": "@engineer-bot test task",
            "sender_id": "bob",
            "addressed": True,
            "message_id": "msg_duplicate"
        }
    })

    # Send first time
    await switch_client.handle_event(msg_frame)
    assert len(received) == 1

    # Send duplicate
    await switch_client.handle_event(msg_frame)
    assert len(received) == 1  # Still 1


@pytest.mark.asyncio
async def test_post_message_and_call_operation(switch_client: SwitchClient):
    """Test posting messages and calling operations."""
    res_msg = await switch_client.post_message("room_dev", "Hello team!")
    assert res_msg["status"] == "sent"
    assert len(switch_client.sent_messages) == 1

    res_op = await switch_client.call_operation("update_agent_detail", addressing="anyone")
    assert res_op["result"] == "mock_success_update_agent_detail"
