import asyncio
from fastapi import WebSocket
from services.matching_service import generate_clue_for_guest


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
                                       countdown_seconds: int = 10,
                                       round_number: int = 1):
        """Run synchronized countdown then reveal matches."""
        # Countdown
        for i in range(countdown_seconds, 0, -1):
            await self.broadcast(event_id, {
                "type": "countdown",
                "seconds_remaining": i,
                "round": round_number,
            })
            await asyncio.sleep(1)

        # Reveal: send each guest their personal match
        for match in matches:
            insights = match.get("insights", {})
            # Build category labels for top_shared_values from insights
            cat_scores = insights.get("category_scores", {})
            top_shared = [v.get("label", k) for k, v in
                          sorted(cat_scores.items(),
                                 key=lambda x: x[1].get("score", 0),
                                 reverse=True)[:3]]

            reveal_data = {
                "name": match["guest_b_name"],
                "compatibility_score": round(match["compatibility_score"], 2),
                "match_type": match["match_type"],
                "top_shared_values": top_shared or match.get("top_shared_values", []),
                "insights": insights,
                "round": round_number,
            }
            await self.send_personal(event_id, match["guest_a_id"], {
                "type": "reveal",
                "match": reveal_data,
            })

            reveal_data_b = {
                "name": match["guest_a_name"],
                "compatibility_score": round(match["compatibility_score"], 2),
                "match_type": match["match_type"],
                "top_shared_values": top_shared or match.get("top_shared_values", []),
                "insights": insights,
                "round": round_number,
            }
            await self.send_personal(event_id, match["guest_b_id"], {
                "type": "reveal",
                "match": reveal_data_b,
            })

    async def send_clues_to_all(self, event_id: str, matches: list[dict],
                                clue_number: int):
        """Send personalized clues to all matched guests."""
        for match in matches:
            clue_for_a = generate_clue_for_guest(match, "a", clue_number)
            clue_for_b = generate_clue_for_guest(match, "b", clue_number)

            await self.send_personal(event_id, match["guest_a_id"], {
                "type": "clue",
                "clue_number": clue_number,
                "clue_text": clue_for_a,
            })
            await self.send_personal(event_id, match["guest_b_id"], {
                "type": "clue",
                "clue_number": clue_number,
                "clue_text": clue_for_b,
            })


manager = ConnectionManager()
