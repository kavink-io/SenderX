"""
SenderX WhatsApp Cloud API Pydantic Validation Models
Strict validation for Meta WhatsApp Business Platform Cloud API message types:
- Text messages (with optional URL preview)
- Media messages (Image, Video, Audio, Document with caption and filename)
- Location messages (Latitude, Longitude, Name, Address)
- Interactive Reply Buttons (up to 3 buttons)
- Interactive List Messages (Header, Body, Footer, Sections, Rows)
- Interactive Call-to-Action URL Buttons
- Template Messages (Meta approved templates with dynamic component parameters)
- Contact Cards (Name, Phone numbers, Emails)
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import re
from urllib.parse import urlsplit

PHONE_REGEX = re.compile(r"^\+?[1-9]\d{6,14}$")


def normalize_wa_phone(phone: str) -> str:
    """Normalize phone number to international digits string required by Meta."""
    if not phone or not isinstance(phone, str):
        raise ValueError("Phone number must be a non-empty string")
    clean = re.sub(r"[\s\-\(\)\.]", "", phone.strip())
    if clean.startswith("whatsapp:"):
        clean = clean[len("whatsapp:"):]
    clean_digits = clean.lstrip("+")
    if not clean_digits.isdigit() or not (7 <= len(clean_digits) <= 15):
        raise ValueError(f"Invalid WhatsApp phone number '{phone}'. Must contain 7 to 15 international digits.")
    return clean_digits


# ---------------------------------------------------------------------------
# 1. TEXT MESSAGE
# ---------------------------------------------------------------------------
class WhatsAppTextMessage(BaseModel):
    body: str = Field(..., min_length=1, max_length=4096, description="Text body of the message (max 4096 chars)")
    preview_url: bool = Field(False, description="Whether to generate a link preview if URL is present")


# ---------------------------------------------------------------------------
# 2. MEDIA MESSAGES
# ---------------------------------------------------------------------------
class WhatsAppMediaItem(BaseModel):
    id: Optional[str] = Field(None, description="Media ID uploaded via WhatsApp Cloud API")
    link: Optional[str] = Field(None, description="Publicly accessible HTTP/HTTPS media URL")
    caption: Optional[str] = Field(None, max_length=1024, description="Optional caption for image, video, or document")
    filename: Optional[str] = Field(None, max_length=256, description="Optional filename for document messages")

    @model_validator(mode="after")
    def validate_id_or_link(self):
        if not self.id and not self.link:
            raise ValueError("Media message requires either 'id' (Meta Media ID) or 'link' (HTTP/HTTPS URL)")
        if self.link and not (self.link.startswith("http://") or self.link.startswith("https://")):
            raise ValueError(f"Invalid media URL '{self.link}'. Must start with http:// or https://")
        return self


# ---------------------------------------------------------------------------
# 3. LOCATION MESSAGE
# ---------------------------------------------------------------------------
class WhatsAppLocationMessage(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")
    name: Optional[str] = Field(None, max_length=256, description="Location venue or place name")
    address: Optional[str] = Field(None, max_length=512, description="Location street address")


# ---------------------------------------------------------------------------
# 4. INTERACTIVE REPLY BUTTONS
# ---------------------------------------------------------------------------
class WhatsAppReplyButton(BaseModel):
    type: Literal["reply"] = "reply"
    reply: Dict[str, str] = Field(..., description="Reply button details containing 'id' and 'title'")

    @field_validator("reply")
    @classmethod
    def validate_reply(cls, v: Dict[str, str]) -> Dict[str, str]:
        if not isinstance(v, dict):
            raise ValueError("Button reply must be a dictionary")
        raw_id = str(v.get("id", ""))
        btn_id = raw_id.strip()
        title = str(v.get("title", "")).strip()
        if not btn_id or len(btn_id) > 256:
            raise ValueError("Button reply 'id' is required (1-256 chars)")
        if raw_id != btn_id:
            raise ValueError("Button reply 'id' cannot have leading or trailing whitespace")
        if not title or len(title) > 20:
            raise ValueError(f"Button reply 'title' must be 1-20 characters (got: '{title}')")
        return {"id": btn_id, "title": title}


# ---------------------------------------------------------------------------
# 5. INTERACTIVE LIST MESSAGE
# ---------------------------------------------------------------------------
class WhatsAppListRow(BaseModel):
    id: str = Field(..., min_length=1, max_length=200, description="Unique row ID")
    title: str = Field(..., min_length=1, max_length=24, description="Row title (max 24 chars)")
    description: Optional[str] = Field(None, max_length=72, description="Optional row description (max 72 chars)")

    @model_validator(mode="after")
    def normalize_and_validate_text(self):
        normalized_id = self.id.strip()
        if not normalized_id:
            raise ValueError("List row 'id' is required")
        if normalized_id != self.id:
            raise ValueError("List row 'id' cannot have leading or trailing whitespace")
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("List row 'title' is required")
        if self.description is not None:
            self.description = self.description.strip()
            if not self.description:
                self.description = None
        return self


class WhatsAppListSection(BaseModel):
    title: Optional[str] = Field(None, max_length=24, description="Section title (max 24 chars)")
    rows: List[WhatsAppListRow] = Field(..., min_length=1, max_length=10, description="List rows (1-10 per section)")

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("List section 'title' cannot be empty")
        if len(normalized) > 24:
            raise ValueError("List section 'title' cannot exceed 24 characters")
        return normalized


# ---------------------------------------------------------------------------
# 6. INTERACTIVE MESSAGES (Buttons, List, CTA URL)
# ---------------------------------------------------------------------------
class WhatsAppInteractiveHeader(BaseModel):
    type: Literal["text", "image", "video", "document"] = "text"
    text: Optional[str] = Field(None, max_length=60)
    image: Optional[WhatsAppMediaItem] = None
    video: Optional[WhatsAppMediaItem] = None
    document: Optional[WhatsAppMediaItem] = None

    @model_validator(mode="after")
    def validate_header_content(self):
        content = {
            "text": self.text,
            "image": self.image,
            "video": self.video,
            "document": self.document,
        }
        if content.get(self.type) is None:
            raise ValueError(f"Interactive header type '{self.type}' requires matching content")
        if any(value is not None for key, value in content.items() if key != self.type):
            raise ValueError("Interactive header may contain content only for its declared type")
        if self.text is not None:
            self.text = self.text.strip()
            if not self.text:
                raise ValueError("Interactive header text cannot be empty")
        return self


class WhatsAppInteractiveMessage(BaseModel):
    type: Literal["button", "list", "cta_url", "product", "product_list", "catalog_message", "flow"] = Field(..., description="Interactive message type")
    header: Optional[WhatsAppInteractiveHeader] = None
    body: Optional[Dict[str, str]] = Field(None, description="Optional or required message body depending on interactive type")
    footer: Optional[Dict[str, str]] = None
    action: Dict[str, Any] = Field(..., description="Interactive actions (buttons, sections, or cta_url parameters)")

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: Dict[str, str]) -> Dict[str, str]:
        if v is None:
            return None
        if not isinstance(v, dict) or not v.get("text"):
            raise ValueError("Interactive body must contain a non-empty 'text' field (max 1024 chars)")
        text = str(v["text"]).strip()
        if len(text) > 1024:
            raise ValueError("Interactive body text exceeds maximum 1024 characters")
        return {"text": text}

    @field_validator("footer")
    @classmethod
    def validate_footer(cls, value: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if value is None:
            return None
        if not isinstance(value, dict) or not value.get("text"):
            raise ValueError("Interactive footer must contain a non-empty 'text' field")
        text = str(value["text"]).strip()
        if not text:
            raise ValueError("Interactive footer text cannot be empty")
        if len(text) > 60:
            raise ValueError("Interactive footer text exceeds maximum 60 characters")
        return {"text": text}

    @model_validator(mode="after")
    def validate_interactive_action(self):
        action = self.action
        if not isinstance(action, dict):
            raise ValueError("Interactive 'action' must be an object")

        if self.type == "product":
            if self.header is not None:
                raise ValueError("Single product messages do not support a header")
            self._validate_catalog_id(action.get("catalog_id"))
            retailer_id = self._validate_retailer_id(action.get("product_retailer_id"))
            self.action = {
                "catalog_id": str(action["catalog_id"]).strip(),
                "product_retailer_id": retailer_id,
            }

        elif self.type == "product_list":
            if self.header is None or self.header.type != "text":
                raise ValueError("Multi-product messages require a text header")
            if self.body is None:
                raise ValueError("Multi-product messages require a body")
            self._validate_catalog_id(action.get("catalog_id"))
            sections = action.get("sections")
            if not isinstance(sections, list) or not sections:
                raise ValueError("Multi-product action requires at least one section")
            normalized_sections = []
            total_products = 0
            for section in sections:
                if not isinstance(section, dict):
                    raise ValueError("Multi-product sections must be objects")
                title = section.get("title")
                if title is not None:
                    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 24:
                        raise ValueError("Multi-product section titles must be 1-24 characters")
                    title = title.strip()
                elif len(sections) > 1:
                    raise ValueError("Multi-product sections require titles when there is more than one section")
                product_items = section.get("product_items")
                if not isinstance(product_items, list) or not product_items:
                    raise ValueError("Each multi-product section requires at least one product item")
                normalized_items = [
                    {"product_retailer_id": self._validate_retailer_id(item.get("product_retailer_id"))}
                    if isinstance(item, dict) else self._invalid_product_item()
                    for item in product_items
                ]
                total_products += len(normalized_items)
                normalized_section = {"product_items": normalized_items}
                if title is not None:
                    normalized_section["title"] = title
                normalized_sections.append(normalized_section)
            if total_products > 30:
                raise ValueError("Multi-product messages support at most 30 products total")
            self.action = {
                "catalog_id": str(action["catalog_id"]).strip(),
                "sections": normalized_sections,
            }

        elif self.type == "catalog_message":
            if self.header is not None:
                raise ValueError("Full catalog messages do not support a header")
            if self.body is None:
                raise ValueError("Full catalog messages require a body")
            if action.get("name") != "catalog_message":
                raise ValueError("Full catalog action requires name 'catalog_message'")
            parameters = action.get("parameters")
            if parameters is not None:
                if not isinstance(parameters, dict):
                    raise ValueError("Full catalog action parameters must be an object")
                thumbnail_id = parameters.get("thumbnail_product_retailer_id")
                if thumbnail_id is not None:
                    parameters = {
                        "thumbnail_product_retailer_id": self._validate_retailer_id(thumbnail_id)
                    }
                else:
                    parameters = {}
            self.action = {"name": "catalog_message"}
            if parameters:
                self.action["parameters"] = parameters

        elif self.type == "flow":
            if self.header is not None or self.footer is not None:
                raise ValueError("WhatsApp Flow messages do not support interactive headers or footers")
            if self.body is None:
                raise ValueError("WhatsApp Flow messages require a body")
            if action.get("name") != "flow":
                raise ValueError("WhatsApp Flow action requires name 'flow'")
            parameters = action.get("parameters")
            if not isinstance(parameters, dict):
                raise ValueError("WhatsApp Flow action requires an object 'parameters'")
            version = str(parameters.get("flow_message_version") or "").strip()
            if version != "3":
                raise ValueError("WhatsApp Flow flow_message_version must be '3'")
            flow_id = parameters.get("flow_id")
            flow_name = parameters.get("flow_name")
            if bool(flow_id) == bool(flow_name):
                raise ValueError("WhatsApp Flow requires exactly one of flow_id or flow_name")
            if flow_id is not None and not str(flow_id).strip().isdigit():
                raise ValueError("WhatsApp Flow flow_id must contain only digits")
            if flow_name is not None and (not isinstance(flow_name, str) or not flow_name.strip() or len(flow_name.strip()) > 512):
                raise ValueError("WhatsApp Flow flow_name must be 1-512 characters")
            cta = parameters.get("flow_cta")
            if not isinstance(cta, str) or not cta.strip() or len(cta.strip()) > 20:
                raise ValueError("WhatsApp Flow flow_cta must be 1-20 characters")
            normalized = {
                "flow_message_version": "3",
                "flow_cta": cta.strip(),
            }
            normalized["flow_id" if flow_id is not None else "flow_name"] = str(flow_id if flow_id is not None else flow_name).strip()
            if parameters.get("flow_token") is not None:
                token = parameters["flow_token"]
                if not isinstance(token, str) or not token.strip() or len(token) > 1024:
                    raise ValueError("WhatsApp Flow flow_token must be a non-empty string up to 1024 characters")
                normalized["flow_token"] = token
            flow_action = parameters.get("flow_action")
            if flow_action is not None:
                if flow_action not in ("navigate", "data_exchange"):
                    raise ValueError("WhatsApp Flow flow_action must be 'navigate' or 'data_exchange'")
                normalized["flow_action"] = flow_action
            payload = parameters.get("flow_action_payload")
            if payload is not None:
                if not isinstance(payload, dict):
                    raise ValueError("WhatsApp Flow flow_action_payload must be an object")
                if flow_action == "navigate" and (not isinstance(payload.get("screen"), str) or not payload["screen"].strip()):
                    raise ValueError("WhatsApp Flow navigate action requires a screen in flow_action_payload")
                if "data" in payload and not isinstance(payload["data"], dict):
                    raise ValueError("WhatsApp Flow flow_action_payload.data must be an object")
                normalized_payload = {}
                if payload.get("screen") is not None:
                    normalized_payload["screen"] = payload["screen"].strip()
                if payload.get("data") is not None:
                    normalized_payload["data"] = payload["data"]
                normalized["flow_action_payload"] = normalized_payload
            self.action = {"name": "flow", "parameters": normalized}

        elif self.type in ("button", "list", "cta_url") and self.body is None:
            raise ValueError(f"Interactive {self.type} messages require a body")

        if self.type == "button":
            buttons = action.get("buttons")
            if not isinstance(buttons, list) or not (1 <= len(buttons) <= 3):
                raise ValueError("Interactive button message requires between 1 and 3 reply buttons")
            parsed_buttons = [WhatsAppReplyButton(**button) for button in buttons]
            button_titles = [button.reply["title"] for button in parsed_buttons]
            if len(button_titles) != len(set(button_titles)):
                raise ValueError("Interactive reply button titles must be unique")
            # Emit the validated representation instead of the unvalidated input
            # dictionaries so normalized values and supported fields reach Meta.
            self.action = {"buttons": [button.model_dump() for button in parsed_buttons]}

        elif self.type == "list":
            button_label = action.get("button")
            button_label = str(button_label).strip() if button_label is not None else ""
            if not button_label or len(button_label) > 20:
                raise ValueError("Interactive list action requires a 'button' label (1-20 characters)")
            sections = action.get("sections")
            if not isinstance(sections, list) or not (1 <= len(sections) <= 10):
                raise ValueError("Interactive list action requires between 1 and 10 sections")
            total_rows = 0
            parsed_sections = []
            row_ids = []
            for sec in sections:
                parsed_sec = WhatsAppListSection(**sec)
                total_rows += len(parsed_sec.rows)
                row_ids.extend(row.id for row in parsed_sec.rows)
                parsed_sections.append(parsed_sec)
            if total_rows > 10:
                raise ValueError(f"Interactive list exceeds maximum 10 total rows across all sections (got {total_rows})")
            if len(row_ids) != len(set(row_ids)):
                raise ValueError("Interactive list row IDs must be unique")
            if self.header is not None and self.header.type != "text":
                raise ValueError("Interactive list messages support only a text header")
            self.action = {
                "button": button_label,
                "sections": [section.model_dump(exclude_none=True) for section in parsed_sections],
            }

        elif self.type == "cta_url":
            if action.get("name") != "cta_url":
                raise ValueError("Interactive cta_url action must have 'name': 'cta_url'")
            params = action.get("parameters", {})
            if not isinstance(params, dict):
                raise ValueError("cta_url action requires an object 'parameters'")
            display_text = params.get("display_text")
            url = params.get("url")
            if not isinstance(display_text, str) or not display_text.strip() or len(display_text.strip()) > 20:
                raise ValueError("cta_url requires 'display_text' (1-20 chars)")
            if not isinstance(url, str) or not url or any(character.isspace() for character in url):
                raise ValueError("cta_url requires a valid absolute HTTP or HTTPS URL")
            try:
                parsed_url = urlsplit(url)
                valid_url = (
                    parsed_url.scheme.lower() in ("http", "https")
                    and bool(parsed_url.hostname)
                    and parsed_url.username is None
                    and parsed_url.password is None
                )
                # Accessing .port also validates malformed port syntax.
                _ = parsed_url.port
            except ValueError:
                valid_url = False
            if not valid_url:
                raise ValueError("cta_url requires a valid absolute HTTP or HTTPS URL")
            self.action = {
                "name": "cta_url",
                "parameters": {
                    "display_text": display_text.strip(),
                    "url": url,
                },
            }

        return self

    @staticmethod
    def _validate_catalog_id(value):
        if not isinstance(value, (str, int)) or not re.fullmatch(r"\d+", str(value).strip()):
            raise ValueError("Product messages require a numeric catalog_id")

    @staticmethod
    def _validate_retailer_id(value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Product messages require a non-empty product_retailer_id")
        return value.strip()

    @staticmethod
    def _invalid_product_item():
        raise ValueError("Multi-product product_items must contain objects")


# ---------------------------------------------------------------------------
# 7. TEMPLATE MESSAGES (Meta Approved)
# ---------------------------------------------------------------------------
class WhatsAppTemplateParameter(BaseModel):
    type: Literal["text", "currency", "date_time", "image", "document", "video", "payload", "action"] = "text"
    text: Optional[str] = None
    currency: Optional[Dict[str, Any]] = None
    date_time: Optional[Dict[str, Any]] = None
    image: Optional[WhatsAppMediaItem] = None
    document: Optional[WhatsAppMediaItem] = None
    video: Optional[WhatsAppMediaItem] = None
    payload: Optional[str] = None
    action: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_flow_action_parameter(self):
        if self.type == "action":
            if not isinstance(self.action, dict):
                raise ValueError("Flow template action parameter requires an action object")
            token = self.action.get("flow_token")
            if token is not None and (not isinstance(token, str) or not token.strip() or len(token) > 1024):
                raise ValueError("Flow template flow_token must be a non-empty string up to 1024 characters")
            data = self.action.get("flow_action_data")
            if data is not None and (not isinstance(data, dict) or not data):
                raise ValueError("Flow template flow_action_data must be a non-empty object")
            if set(self.action) - {"flow_token", "flow_action_data"}:
                raise ValueError("Flow template action contains unsupported fields")
        return self


class WhatsAppTemplateComponent(BaseModel):
    type: Literal["header", "body", "button"] = "body"
    sub_type: Optional[Literal["quick_reply", "url", "catalog", "flow"]] = None
    index: Optional[int] = None
    parameters: List[WhatsAppTemplateParameter] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_flow_template_button(self):
        if self.sub_type == "flow":
            if self.type != "button" or self.index is None or self.index < 0:
                raise ValueError("Flow template components require a button type and non-negative button index")
            if len(self.parameters) > 1 or (self.parameters and self.parameters[0].type != "action"):
                raise ValueError("Flow template button accepts at most one action parameter")
        return self


class WhatsAppTemplateMessage(BaseModel):
    name: str = Field(..., min_length=1, max_length=512, description="Meta approved template name")
    language: Union[str, Dict[str, str]] = Field(..., description="Language code e.g. 'en', 'en_US' or {'code': 'en_US'}")
    components: List[WhatsAppTemplateComponent] = Field(default_factory=list, description="Dynamic variable components")

    @field_validator("language")
    @classmethod
    def normalize_language(cls, v: Union[str, Dict[str, str]]) -> Dict[str, str]:
        if isinstance(v, str):
            code = v.strip()
            if not code:
                raise ValueError("Template language code cannot be empty")
            return {"code": code}
        if isinstance(v, dict):
            code = v.get("code")
            if not code or not str(code).strip():
                raise ValueError("Template language dict must contain a non-empty 'code'")
            return {"code": str(code).strip()}
        raise ValueError("Invalid template language format")


# ---------------------------------------------------------------------------
# 8. CONTACTS MESSAGE
# ---------------------------------------------------------------------------
class WhatsAppContactName(BaseModel):
    formatted_name: str = Field(..., min_length=1, max_length=128)
    first_name: Optional[str] = Field(None, max_length=64)
    last_name: Optional[str] = Field(None, max_length=64)


class WhatsAppContactPhone(BaseModel):
    phone: str = Field(..., min_length=1, max_length=32)
    type: Optional[str] = "CELL"
    wa_id: Optional[str] = None


class WhatsAppContactCard(BaseModel):
    name: WhatsAppContactName
    phones: Optional[List[WhatsAppContactPhone]] = None
    emails: Optional[List[Dict[str, str]]] = None


# ---------------------------------------------------------------------------
# 9. DISCRIMINATED WHATSAPP PAYLOAD NORMALIZER
# ---------------------------------------------------------------------------
class WhatsAppPayloadValidator:
    """Validates arbitrary input payloads and transforms into standard Meta Graph API payload."""

    SUPPORTED_TYPES = {
        "text", "image", "video", "audio", "document",
        "location", "interactive", "template", "contacts"
    }

    @classmethod
    def validate_and_format(
        cls,
        *args,
        message: Optional[Dict[str, Any]] = None,
        recipient: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
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

        if not recipient and isinstance(data, dict):
            recipient = data.get("to") or data.get("recipient")

        if not recipient:
            raise ValueError("Recipient phone number is required for WhatsApp message")

        if not isinstance(data, dict):
            raise ValueError("WhatsApp message data must be a dictionary")

        clean_to = normalize_wa_phone(str(recipient))

        # Detect message type: explicit type field or inferred
        msg_type = data.get("type")

        if not msg_type:
            # Infer type from keys
            media_url_types = [
                media_type
                for media_type in ("image", "video", "audio", "document")
                if data.get(f"{media_type}_url")
            ]
            if len(media_url_types) > 1:
                raise ValueError("Provide only one type-specific WhatsApp media URL alias")

            if "template" in data or "template_name" in data:
                msg_type = "template"
            elif "interactive" in data:
                msg_type = "interactive"
            elif "location" in data:
                msg_type = "location"
            elif "image" in data:
                msg_type = "image"
            elif "video" in data:
                msg_type = "video"
            elif "audio" in data:
                msg_type = "audio"
            elif "document" in data:
                msg_type = "document"
            elif media_url_types:
                # These aliases identify the media type unambiguously. Keep the
                # generic media_url alias dependent on an explicit type below.
                msg_type = media_url_types[0]
            elif "contacts" in data:
                msg_type = "contacts"
            elif "text" in data or "message" in data or "body" in data:
                msg_type = "text"
            else:
                raise ValueError("Could not determine WhatsApp message type. Provide 'type' or valid type object.")

        msg_type = str(msg_type).lower().strip()
        if msg_type not in cls.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported WhatsApp message type '{msg_type}'. "
                f"Supported types: {sorted(list(cls.SUPPORTED_TYPES))}"
            )

        meta_payload: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_to,
            "type": msg_type
        }

        # 1. TEXT
        if msg_type == "text":
            text_val = data.get("text")
            if isinstance(text_val, dict):
                model = WhatsAppTextMessage(**text_val)
            elif isinstance(text_val, str):
                model = WhatsAppTextMessage(body=text_val, preview_url=bool(data.get("preview_url", False)))
            else:
                body = data.get("message") or data.get("body")
                if not body:
                    raise ValueError("WhatsApp text message requires 'text' or 'message'")
                model = WhatsAppTextMessage(body=str(body), preview_url=bool(data.get("preview_url", False)))
            meta_payload["text"] = model.model_dump()

        # 2. MEDIA (image, video, audio, document)
        elif msg_type in ("image", "video", "audio", "document"):
            media_val = data.get(msg_type)
            if isinstance(media_val, dict):
                model = WhatsAppMediaItem(**media_val)
            elif isinstance(media_val, str):
                model = WhatsAppMediaItem(link=media_val, caption=data.get("caption"), filename=data.get("filename"))
            else:
                link = (
                    data.get(f"{msg_type}_url")
                    or data.get("media_url")
                    or data.get("link")
                )
                media_id = data.get("media_id") or data.get("id")
                model = WhatsAppMediaItem(
                    id=media_id,
                    link=link,
                    caption=data.get("caption"),
                    filename=data.get("filename")
                )
            # Remove None values for Meta compatibility
            meta_payload[msg_type] = {k: v for k, v in model.model_dump().items() if v is not None}

        # 3. LOCATION
        elif msg_type == "location":
            loc_val = data.get("location") or data
            model = WhatsAppLocationMessage(**loc_val)
            meta_payload["location"] = {k: v for k, v in model.model_dump().items() if v is not None}

        # 4. INTERACTIVE
        elif msg_type == "interactive":
            interactive_val = data.get("interactive") or data
            model = WhatsAppInteractiveMessage(**interactive_val)
            meta_payload["interactive"] = model.model_dump(exclude_none=True)

        # 5. TEMPLATE
        elif msg_type == "template":
            tmpl_val = data.get("template") or {
                "name": data.get("template_name"),
                "language": data.get("language", "en"),
                "components": data.get("components", [])
            }
            model = WhatsAppTemplateMessage(**tmpl_val)
            meta_payload["template"] = model.model_dump(exclude_none=True)

        # 6. CONTACTS
        elif msg_type == "contacts":
            contacts_val = data.get("contacts", [])
            if not isinstance(contacts_val, list) or not contacts_val:
                raise ValueError("WhatsApp contacts message requires a non-empty list of contact objects")
            parsed_contacts = [WhatsAppContactCard(**c).model_dump(exclude_none=True) for c in contacts_val]
            meta_payload["contacts"] = parsed_contacts

        return meta_payload
