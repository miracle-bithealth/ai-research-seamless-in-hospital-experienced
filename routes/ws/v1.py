from fastapi import WebSocket, APIRouter
from app.controllers.NavigationController import navigationController

router = APIRouter()


@router.websocket("/navigate")
async def ws_navigate(websocket: WebSocket):
    await navigationController.handle_websocket(websocket)