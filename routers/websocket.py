from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.connection_manager import manager
from services.matching_service import get_match_for_guest
from services.event_service import get_event

router = APIRouter()


@router.websocket("/ws/event/{event_id}/{guest_id}")
async def websocket_endpoint(websocket: WebSocket, event_id: str, guest_id: str):
    await manager.connect(event_id, guest_id, websocket)
    try:
        event = await get_event(event_id)
        if event:
            if event["status"] == "revealed":
                # Late joiner: send match for current round
                match = await get_match_for_guest(
                    event_id, guest_id,
                    round_number=event["current_round"]
                )
                if match:
                    await websocket.send_json({
                        "type": "reveal",
                        "match": match,
                    })
            elif event["status"] == "clues":
                # Late joiner during clues phase
                await websocket.send_json({
                    "type": "clues_phase",
                    "round": event["current_round"],
                    "message": "Matching abgeschlossen! Hinweise folgen...",
                })

        # Send current waiting status
        connected = manager.get_connected_count(event_id)
        await websocket.send_json({
            "type": "waiting",
            "guests_connected": connected,
        })

        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(event_id, guest_id)
