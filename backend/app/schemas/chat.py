from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatMessage(BaseModel):
    id: str
    sender_id: str
    channel: str  # hall/battle/private/spatial_normal/spatial_shout
    content_type: str = "text"  # text/audio/dice/system
    text: Optional[str] = None
    audio_url: Optional[str] = None
    recipients: Optional[List[str]] = None  # None=broadcast (hall/battle)
    # private=[a,b]
    # spatial=explicit list at send time
    timestamp: int = 0
    extra: Optional[Dict[str, Any]] = None  # spatial: attenuation, distance, is_shout
