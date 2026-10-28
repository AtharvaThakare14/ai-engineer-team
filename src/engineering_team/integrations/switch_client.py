"""Switch Agent Protocol Client.

Implements the official Switch wire contract:
- WebSocket connection: /agents/{agent_id}/connection/ws
- REST operations: POST /agents/{agent_id}/ops/{operation}
- Messaging: POST /agents/{agent_id}/message
- Registration: POST /agents
- Heartbeats: Ping/Pong with cursor tracking
- Addressing policy and message deduplication
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Set
import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from engineering_team.config import Settings
from engineering_team.models import (
    SwitchEvent,
    SwitchRegistrationRequest,
    SwitchRegistrationResponse,
)

logger = logging.getLogger(__name__)


class SwitchClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.switch_server_url.rstrip("/")
        self.agent_id = settings.switch_agent_id
        self.api_key = settings.switch_api_key
        self.connection_id = str(uuid.uuid4())
        self.cursor: int = 0
        self.generation: Optional[str] = None
        self.claimed_rooms: Set[str] = {settings.switch_default_room_id}

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running: bool = False
        self._processed_message_ids: Set[str] = set()
        self._message_handlers: List[Callable[[SwitchEvent], Any]] = []

        # Outbox for mock / offline testing
        self.mock_mode: bool = not bool(self.api_key)
        self.sent_messages: List[Dict[str, Any]] = []

    def add_message_handler(self, handler: Callable[[SwitchEvent], Any]) -> None:
        """Register an async callback for incoming addressed messages."""
        self._message_handlers.append(handler)

    async def register_agent(
        self,
        name: str = "engineer-bot",
        description: str = "AI Engineering Team Agent",
        display_name: str = "AI Engineer",
        overwrite: bool = True
    ) -> SwitchRegistrationResponse:
        """Register the agent with Switch server using the registration token."""
        if self.mock_mode:
            self.agent_id = f"agent_{name}_{uuid.uuid4().hex[:4]}"
            self.api_key = f"key_{uuid.uuid4().hex[:12]}"
            logger.info("Mock Switch registration succeeded: %s", self.agent_id)
            return SwitchRegistrationResponse(id=self.agent_id, api_key=self.api_key)

        reg_req = SwitchRegistrationRequest(
            name=name,
            description=description,
            display_name=display_name,
            overwrite=overwrite
        )

        headers = {
            "Authorization": f"Bearer {self.settings.switch_registration_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/agents",
                json=reg_req.model_dump(),
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            self.agent_id = data["id"]
            self.api_key = data["api_key"]
            logger.info("Registered agent %s with ID %s", name, self.agent_id)
            return SwitchRegistrationResponse(id=self.agent_id, api_key=self.api_key)

    async def configure_addressing(self, addressing: str = "anyone") -> Dict[str, Any]:
        """Configure who can talk to the agent: owner_only, owner_and_owner_agents, or anyone."""
        if self.mock_mode or not self.agent_id or not self.api_key:
            return {"status": "mock_configured", "addressing": addressing}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"agent_id": self.agent_id, "addressing": addressing}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/agents/{self.agent_id}/ops/update_agent_detail",
                json=payload,
                headers=headers
            )
            resp.raise_for_status()
            return resp.json()

    async def post_message(self, room_id: str, content: str) -> Dict[str, Any]:
        """Post a message to a Switch room via POST /agents/{agent_id}/message."""
        payload = {"room_id": room_id, "content": content}
        self.sent_messages.append(payload)

        if self.mock_mode or not self.api_key:
            logger.info("[Mock Switch] Posted to room %s: %s", room_id, content[:60])
            return {"status": "sent", "room_id": room_id, "message_id": str(uuid.uuid4())}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(
                    f"{self.base_url}/agents/{self.agent_id}/message",
                    json=payload,
                    headers=headers
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as exc:
            logger.warning("Could not reach Switch server at %s (%s). Buffering message locally.", self.base_url, exc)
            return {"status": "buffered_offline", "room_id": room_id, "error": str(exc)}

    async def call_operation(self, operation: str, **kwargs) -> Any:
        """Invoke an operation on Switch server via POST /agents/{agent_id}/ops/{operation}."""
        if self.mock_mode or not self.api_key:
            logger.info("[Mock Switch] Called op %s with args: %s", operation, kwargs)
            return {"result": f"mock_success_{operation}"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Switch-Connection-Id": self.connection_id,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/agents/{self.agent_id}/ops/{operation}",
                    json=kwargs,
                    headers=headers
                )
                resp.raise_for_status()
                return resp.json().get("result")
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as exc:
            logger.warning("Could not reach Switch server at %s for operation %s: %s", self.base_url, operation, exc)
            return {"error": "offline", "operation": operation}

    async def handle_event(self, raw_message: str) -> None:
        """Parse, validate, deduplicate and route an incoming event frame."""
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON frame: %s", raw_message[:100])
            return

        frame_type = data.get("type") or data.get("event")

        # Handle Ping / Pong liveness
        if frame_type == "ping":
            await self._respond_pong()
            return

        # Handle Connection State frame
        if frame_type == "connection_state":
            self.cursor = data.get("cursor", self.cursor)
            self.generation = data.get("generation")
            if "rooms" in data and isinstance(data["rooms"], list):
                self.claimed_rooms.update(data["rooms"])
            logger.info("Updated connection state: cursor=%s, rooms=%s", self.cursor, self.claimed_rooms)
            return

        # Handle Message Events
        if frame_type == "message" or "payload" in data:
            try:
                event = SwitchEvent.model_validate(data)
            except Exception as e:
                logger.warning("Could not parse SwitchEvent: %s", e)
                return

            if event.cursor is not None:
                self.cursor = max(self.cursor, event.cursor)

            msg_id = event.payload.message_id
            if msg_id in self._processed_message_ids:
                logger.debug("Skipping duplicate message %s", msg_id)
                return
            self._processed_message_ids.add(msg_id)

            # Act on messages only if addressed to this agent or direct message
            if event.payload.addressed:
                logger.info("Received addressed message: %s", event.payload.content[:50])
                for handler in self._message_handlers:
                    try:
                        res = handler(event)
                        if asyncio.iscoroutine(res):
                            asyncio.create_task(res)
                    except Exception as ex:
                        logger.exception("Error in message handler: %s", ex)

    async def _respond_pong(self) -> None:
        """Reply to a ping frame with a pong carrying the current cursor."""
        pong_frame = json.dumps({"type": "pong", "cursor": self.cursor})
        if self._ws and not self._ws.closed:
            await self._ws.send(pong_frame)
            logger.debug("Sent pong with cursor %d", self.cursor)

    async def connect_and_listen(self) -> None:
        """Open WebSocket to Switch and listen for events."""
        if self.mock_mode:
            logger.info("[Mock Switch] Running in mock mode, skipping live WebSocket.")
            return

        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        endpoint = f"{ws_url}/agents/{self.agent_id}/connection/ws"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Switch-Connection-Id": self.connection_id
        }

        self._running = True
        retry_delay = 2

        while self._running:
            try:
                logger.info("Connecting to Switch WebSocket: %s", endpoint)
                async with websockets.connect(endpoint, extra_headers=headers) as ws:
                    self._ws = ws
                    retry_delay = 2
                    logger.info("Connected to Switch WebSocket.")

                    async for message in ws:
                        if not self._running:
                            break
                        await self.handle_event(message)

            except (ConnectionClosed, OSError, Exception) as exc:
                if not self._running:
                    break
                logger.warning("Switch WebSocket disconnected (%s). Retrying in %ds...", exc, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)

    def stop(self) -> None:
        """Stop listening and disconnect."""
        self._running = False
        if self._ws:
            asyncio.create_task(self._ws.close())
