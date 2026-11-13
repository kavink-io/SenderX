"""
SenderX Microsoft Teams Pydantic Validation Models
Strict validation for Microsoft Graph API v1.0 Teams messaging:
- Chat messages (1:1, Group chats via POST /chats/{chat-id}/messages)
- Channel messages (Team channels via POST /teams/{team-id}/channels/{channel-id}/messages)
- Text and HTML content formatting
- Adaptive Cards (application/vnd.microsoft.card.adaptive)
- File references and SharePoint attachments
- Message importance ('normal', 'high', 'urgent')
- Subject lines (for channel root threads)
"""

import json
import re
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# 1. MESSAGE BODY MODEL
# ---------------------------------------------------------------------------
class TeamsMessageBody(BaseModel):
    contentType: Literal["text", "html"] = Field("html", description="Body content type: 'text' or 'html'")
    content: str = Field(..., min_length=1, max_length=28000, description="Message text or HTML content (max 28KB)")

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message body content cannot be empty or whitespace only")
        return v


# ---------------------------------------------------------------------------
# 2. ADAPTIVE CARD & ATTACHMENT MODELS
# ---------------------------------------------------------------------------
class TeamsAdaptiveCard(BaseModel):
    type: Literal["AdaptiveCard"] = "AdaptiveCard"
    version: str = Field("1.4", description="Adaptive Card schema version (e.g. 1.2, 1.4, 1.5)")
    body: List[Dict[str, Any]] = Field(default_factory=list, description="Visual card elements (TextBlock, Image, Container, etc.)")
    actions: Optional[List[Dict[str, Any]]] = Field(None, description="Interactive action buttons (Action.OpenUrl, Action.Submit)")
    schema_url: Optional[str] = Field("http://adaptivecards.io/schemas/adaptive-card.json", alias="$schema")

    @field_validator("body")
    @classmethod
    def validate_body_elements(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("Adaptive Card requires at least one body element")
        return v


class TeamsAttachment(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    contentType: str = Field(..., min_length=1, description="Attachment MIME or special type")
    content: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Serialized card JSON or content object")
    contentUrl: Optional[str] = Field(None, description="URL of reference or file")
    name: Optional[str] = Field(None, max_length=256, description="Display name for files or cards")

    @model_validator(mode="after")
    def validate_attachment_payload(self):
        if self.contentType == "application/vnd.microsoft.card.adaptive":
            if not self.content:
                raise ValueError("Adaptive card attachment requires 'content' dictionary or JSON string")
        elif not self.content and not self.contentUrl:
            raise ValueError("Teams attachment requires either 'content' or 'contentUrl'")
        return self


# ---------------------------------------------------------------------------
# 3. RECIPIENT TARGET MODEL
# ---------------------------------------------------------------------------
class TeamsRecipientModel(BaseModel):
    target_type: Literal["chat", "channel"] = Field(..., description="Target type: 'chat' or 'channel'")
    chat_id: Optional[str] = Field(None, description="Chat thread ID (e.g. 19:meeting_...@thread.v2)")
    team_id: Optional[str] = Field(None, description="Microsoft 365 Team ID GUID")
    channel_id: Optional[str] = Field(None, description="Channel ID (e.g. 19:...@thread.tacv2)")

    @model_validator(mode="after")
    def validate_target_fields(self):
        if self.target_type == "chat":
            if not self.chat_id or not self.chat_id.strip():
                raise ValueError("Chat target requires a valid 'chat_id'")
        elif self.target_type == "channel":
            if not self.team_id or not self.team_id.strip():
                raise ValueError("Channel target requires a valid 'team_id' (Team GUID)")
            if not self.channel_id or not self.channel_id.strip():
                raise ValueError("Channel target requires a valid 'channel_id'")
        return self


# ---------------------------------------------------------------------------
# 4. TEAMS PAYLOAD VALIDATOR
# ---------------------------------------------------------------------------
class TeamsPayloadValidator:
    """Validates and normalizes Teams message requests into Microsoft Graph API payload."""

    CHAT_PREFIX = "chat:"
    CHANNEL_PREFIX = "channel:"

    @classmethod
    def resolve_recipient(cls, recipient: Optional[str], data: Dict[str, Any]) -> TeamsRecipientModel:
        """
        Resolve destination chat or channel from recipient string and data dictionary.
        Supported formats:
        - Chat:
            recipient="chat:19:xxx@thread.v2"
            recipient="19:xxx@thread.v2"
            data={"chat_id": "19:xxx@thread.v2"}
        - Channel:
            recipient="channel:<team_id>:<channel_id>"
            recipient="<team_id>:<channel_id>"
            data={"team_id": "...", "channel_id": "..."}
        """
        r_str = (recipient or "").strip()

        # 1. Explicit data fields take precedence
        chat_id = data.get("chat_id")
        team_id = data.get("team_id")
        channel_id = data.get("channel_id")

        if chat_id:
            return TeamsRecipientModel(target_type="chat", chat_id=str(chat_id).strip())

        if team_id and channel_id:
            return TeamsRecipientModel(
                target_type="channel",
                team_id=str(team_id).strip(),
                channel_id=str(channel_id).strip()
            )

        # 2. Inspect recipient string
        if r_str.startswith(cls.CHAT_PREFIX):
            clean_chat = r_str[len(cls.CHAT_PREFIX):].strip()
            return TeamsRecipientModel(target_type="chat", chat_id=clean_chat)

        if r_str.startswith(cls.CHANNEL_PREFIX):
            rest = r_str[len(cls.CHANNEL_PREFIX):].strip()
            parts = rest.split(":", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                return TeamsRecipientModel(target_type="channel", team_id=parts[0].strip(), channel_id=parts[1].strip())
            raise ValueError(
                f"Invalid Teams channel recipient '{r_str}'. Expected format: 'channel:<team_id>:<channel_id>'"
            )

        # 3. Check colon delimiter (team_id:channel_id)
        if ":" in r_str and not r_str.startswith("19:"):
            parts = r_str.split(":", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                return TeamsRecipientModel(target_type="channel", team_id=parts[0].strip(), channel_id=parts[1].strip())

        # 4. Check standard thread ID
        if r_str.startswith("19:") or "@thread." in r_str or "@unq.gbl.spaces" in r_str:
            # If team_id is provided in data, it's a channel
            if team_id:
                return TeamsRecipientModel(target_type="channel", team_id=str(team_id).strip(), channel_id=r_str)
            return TeamsRecipientModel(target_type="chat", chat_id=r_str)

        if not r_str and not chat_id and not (team_id and channel_id):
            raise ValueError(
                "Teams message requires a recipient (chat_id, or team_id and channel_id)"
            )

        # Default fallback to chat
        return TeamsRecipientModel(target_type="chat", chat_id=r_str)

    @classmethod
    def validate_and_format(
        cls,
        *args,
        message: Optional[Dict[str, Any]] = None,
        recipient: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Tuple[TeamsRecipientModel, Dict[str, Any]]:
        """
        Validate input and convert to Microsoft Graph API message payload.
        Returns tuple of (TeamsRecipientModel, graph_payload_dict).
        """
        if len(args) == 2:
            recipient = args[0]
            data = args[1]
        elif len(args) == 1:
            if isinstance(args[0], dict):
                message = args[0]
            else:
                recipient = args[0]

        if message is not None and isinstance(message, dict):
            if not recipient:
                recipient = message.get("recipient") or message.get("to")
            if data is None:
                data = message.get("data")
            if data is None:
                data = {
                    k: v for k, v in message.items()
                    if k not in ("recipient", "to", "channel", "provider", "message_id", "status", "created_at")
                }

        if data is None or not isinstance(data, dict):
            data = {}

        if not recipient and isinstance(data, dict):
            recipient = data.get("recipient") or data.get("to")

        # Resolve target recipient
        target = cls.resolve_recipient(recipient, data)

        # Content resolution (HTML vs Text)
        content_type: str = "html"
        content_str: str = ""

        if "html" in data:
            content_type = "html"
            content_str = str(data["html"])
        elif "html_body" in data:
            content_type = "html"
            content_str = str(data["html_body"])
        elif "text" in data:
            content_type = "text"
            content_str = str(data["text"])
        elif "message" in data:
            content_type = "text"
            content_str = str(data["message"])
        elif "body" in data:
            b_val = data["body"]
            if isinstance(b_val, dict):
                content_type = b_val.get("contentType", "html")
                content_str = b_val.get("content", "")
            else:
                content_str = str(b_val)
        elif "content" in data:
            content_str = str(data["content"])

        # Importance
        importance_raw = str(data.get("importance", "normal")).lower().strip()
        if importance_raw not in ("normal", "high", "urgent"):
            importance_raw = "normal"

        # Subject (for channel root messages)
        subject = data.get("subject")

        # Attachments (Adaptive Cards, File references)
        attachments_list: List[Dict[str, Any]] = []

        # 1. Explicit adaptive_card in data
        if "adaptive_card" in data or "card" in data:
            card_dict = data.get("adaptive_card") or data.get("card")
            if isinstance(card_dict, str):
                try:
                    card_dict = json.loads(card_dict)
                except Exception:
                    pass

            if isinstance(card_dict, dict):
                validated_card = TeamsAdaptiveCard(**card_dict)
                card_att = TeamsAttachment(
                    contentType="application/vnd.microsoft.card.adaptive",
                    content=validated_card.model_dump(by_alias=True, exclude_none=True)
                )
                attachments_list.append(card_att.model_dump(exclude_none=True))

        # 2. General attachments array
        if "attachments" in data and isinstance(data["attachments"], list):
            for att_raw in data["attachments"]:
                if isinstance(att_raw, dict):
                    # Handle raw card inside attachment
                    if att_raw.get("contentType") == "application/vnd.microsoft.card.adaptive":
                        content_inner = att_raw.get("content")
                        if isinstance(content_inner, str):
                            try:
                                content_inner = json.loads(content_inner)
                            except Exception:
                                pass
                        if isinstance(content_inner, dict):
                            validated_card = TeamsAdaptiveCard(**content_inner)
                            att_raw["content"] = validated_card.model_dump(by_alias=True, exclude_none=True)

                    att_model = TeamsAttachment(**att_raw)
                    attachments_list.append(att_model.model_dump(exclude_none=True))

        # Ensure content is not empty if no attachments
        if not content_str and not attachments_list:
            raise ValueError(
                "Teams message requires either body content (text/html) or an attachment (e.g. Adaptive Card)"
            )

        # If only attachments are given without body, provide a placeholder per Graph requirements
        if not content_str and attachments_list:
            content_str = "<attachment></attachment>"
            content_type = "html"

        # Validate message body
        body_model = TeamsMessageBody(contentType=content_type, content=content_str)

        graph_payload: Dict[str, Any] = {
            "body": body_model.model_dump(),
            "importance": importance_raw
        }

        if subject and target.target_type == "channel":
            graph_payload["subject"] = str(subject)

        if attachments_list:
            graph_payload["attachments"] = attachments_list

        return target, graph_payload
