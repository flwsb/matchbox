import asyncio
import json
from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections per event room."""

    def __init__(self):
        self.rooms: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, event_id: str, guest_id: str, websocket: WebSocket):
        await websocket.accept()
        if event_id not in self.rooms:
            self.rooms[event_id] = {}
        self.rooms[event_id][guest_id] = websocket

    def disconnect(self, event_id: str, guest_id: str):
        if event_id in self.rooms:
            self.rooms[event_id].pop(guest_id, None)
            if not self.rooms[event_id]:
                del self.rooms[event_id]

    def get_connected_count(self, event_id: str) -> int:
        return len(self.rooms.get(event_id, {}))

    async def broadcast(self, event_id: str, message: dict):
        if event_id not in self.rooms:
            return
        disconnected = []
        for guest_id, ws in self.rooms[event_id].items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(guest_id)
        for gid in disconnected:
            self.disconnect(event_id, gid)

    async def send_personal(self, event_id: str, guest_id: str, message: dict):
        ws = self.rooms.get(event_id, {}).get(guest_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(event_id, guest_id)

    async def run_countdown_and_reveal(self, event_id: str, matches: list[dict],
                                       countdown_seconds: int = 10):
        """Run synchronized countdown then reveal matches."""
        # Countdown
        for i in range(countdown_seconds, 0, -1):
            await self.broadcast(event_id, {
                "type": "countdown",
                "seconds_remaining": i,
            })
            await asyncio.sleep(1)

        # Reveal: send each guest their personal match
        for match in matches:
            await self.send_personal(event_id, match["guest_a_id"], {
                "type": "reveal",
                "match": {
                    "name": match["guest_b_name"],
                    "compatibility_score": round(match["compatibility_score"], 2),
                    "match_type": match["match_type"],
                    "top_shared_values": match.get("top_shared_values", []),
                },
            })
            await self.send_personal(event_id, match["guest_b_id"], {
                "type": "reveal",
                "match": {
                    "name": match["guest_a_name"],
                    "compatibility_score": round(match["compatibility_score"], 2),
                    "match_type": match["match_type"],
                    "top_shared_values": match.get("top_shared_values", []),
                },
            })


manager = ConnectionManager()
