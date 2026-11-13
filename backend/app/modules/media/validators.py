"""
SenderX Media Validation Engine
Provides:
- Exact magic byte file signature verification for images, videos, audio, and documents
- Detection of file signature mismatches (preventing spoofed extensions/MIME types)
- Strict filename sanitization and path traversal prevention
- Per-file and total request size validation
- Channel-specific size and format validation (Email, WhatsApp, SMS/MMS, Microsoft Teams)
- Malware scanning interface (never falsely claims active scanning without a configured scanner)
"""

from abc import ABC, abstractmethod
import io
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import re
import socket
from typing import Any, Dict, List, Optional, Set, Tuple
import zipfile


# ---------------------------------------------------------------------------
# 1. SUPPORTED MIME TYPES & EXTENSIONS
# ---------------------------------------------------------------------------

SUPPORTED_MEDIA_TYPES: Dict[str, Dict[str, Any]] = {
    # Images
    "image/jpeg": {"category": "image", "extensions": {".jpg", ".jpeg"}},
    "image/png": {"category": "image", "extensions": {".png"}},
    "image/webp": {"category": "image", "extensions": {".webp"}},
    "image/gif": {"category": "image", "extensions": {".gif"}},

    # Videos
    "video/mp4": {"category": "video", "extensions": {".mp4", ".m4v"}},
    "video/3gpp": {"category": "video", "extensions": {".3gp"}},
    "video/webm": {"category": "video", "extensions": {".webm"}},

    # Audio
    "audio/mpeg": {"category": "audio", "extensions": {".mp3"}},
    "audio/mp3": {"category": "audio", "extensions": {".mp3"}},
    "audio/aac": {"category": "audio", "extensions": {".aac"}},
    "audio/ogg": {"category": "audio", "extensions": {".ogg", ".oga"}},
    "audio/wav": {"category": "audio", "extensions": {".wav"}},

    # Documents
    "application/pdf": {"category": "document", "extensions": {".pdf"}},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        "category": "document", "extensions": {".docx"}
    },
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
        "category": "document", "extensions": {".xlsx"}
    },
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
        "category": "document", "extensions": {".pptx"}
    },
    "text/plain": {"category": "document", "extensions": {".txt", ".text", ".log"}},
    "text/csv": {"category": "document", "extensions": {".csv"}},
    "application/zip": {"category": "document", "extensions": {".zip"}}
}


# ---------------------------------------------------------------------------
# 2. MAGIC BYTE SIGNATURE DETECTION
# ---------------------------------------------------------------------------

def detect_file_signature(header: bytes, filename: str = "") -> Optional[str]:
    """
    Detect the genuine MIME type of a file by inspecting its raw magic bytes.
    Returns the detected canonical MIME type or None if unknown/disallowed.
    """
    if not header or len(header) < 4:
        return None

    # 1. JPEG: 0xFF 0xD8 0xFF
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # 2. PNG: 0x89 'PNG\r\n\x1a\n'
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # 3. GIF: 'GIF87a' or 'GIF89a'
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return "image/gif"

    # 4. WebP / WAV: starts with 'RIFF'
    if header.startswith(b"RIFF") and len(header) >= 12:
        tag = header[8:12]
        if tag == b"WEBP":
            return "image/webp"
        if tag == b"WAVE":
            return "audio/wav"

    # 5. PDF: '%PDF-'
    if header.startswith(b"%PDF-"):
        return "application/pdf"

    # 6. MP4 / 3GP / ISO media: check 'ftyp' at offset 4
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"isom", b"iso2", b"mp41", b"mp42", b"dash", b"M4V ", b"MSNV", b"avc1", b"qt  "):
            return "video/mp4"
        if brand in (b"3gp4", b"3gp5", b"3gp6", b"3gp7", b"3g2a"):
            return "video/3gpp"
        # Generic MP4 container
        return "video/mp4"

    # 7. WebM / Matroska: 0x1A 0x45 0xDF 0xA3 (EBML header)
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"

    # 8. OGG: 'OggS'
    if header.startswith(b"OggS"):
        return "audio/ogg"

    # 9. MP3: 'ID3' or MPEG audio sync frame (0xFF 0xFB/F3/F2)
    if header.startswith(b"ID3"):
        return "audio/mpeg"
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0 and (header[1] & 0x18) != 0x08:
        return "audio/mpeg"

    # 10. AAC (ADTS frame header: 0xFFF)
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xF6) in (0xF0, 0xF2):
        return "audio/aac"

    # 11. ZIP / Microsoft Office OpenXML (.docx, .xlsx, .pptx): starts with 'PK\x03\x04'
    if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06"):
        ext = os.path.splitext(filename.lower())[1] if filename else ""
        if ext == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if ext == ".xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext == ".pptx":
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return "application/zip"

    # 12. Plain Text / CSV: ensure no null bytes or binary control characters
    ext = os.path.splitext(filename.lower())[1] if filename else ""
    if ext in (".txt", ".text", ".log", ".csv"):
        # Check first 512 bytes for binary characters
        sample = header[:512]
        if b"\x00" not in sample:
            try:
                sample.decode("utf-8")
                return "text/csv" if ext == ".csv" else "text/plain"
            except UnicodeDecodeError:
                pass

    return None


def verify_file_signature(
    header_bytes: bytes,
    declared_mime: Optional[str] = None,
    filename: str = "",
    extra_allowed_mimes: Optional[Set[str]] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Validate that:
    1. File signature is recognized and belongs to allowed media types.
    2. File signature matches the declared MIME type and file extension (no spoofing).
    Returns: (is_valid, message, detected_mime)
    """
    detected = detect_file_signature(header_bytes, filename=filename)
    allowed_mimes = set(SUPPORTED_MEDIA_TYPES.keys())
    if extra_allowed_mimes:
        allowed_mimes.update(extra_allowed_mimes)

    ext = os.path.splitext(filename.lower())[1] if filename else ""

    # Known executable or script signatures that must ALWAYS be rejected
    dangerous_signatures = [
        (b"MZ", "Windows Executable/DLL"),
        (b"\x7fELF", "Linux ELF Binary"),
        (b"\xca\xfe\xba\xbe", "Java Class / Mach-O Binary"),
        (b"<?php", "PHP Script"),
        (b"<script", "Client Script HTML"),
    ]
    for sig, desc in dangerous_signatures:
        if header_bytes.startswith(sig):
            return False, f"Dangerous executable or script file detected ({desc})", None

    if detected is None:
        return False, f"Unrecognized or unsupported file signature for '{filename}'", None

    if detected not in allowed_mimes:
        return False, f"Detected MIME type '{detected}' is not permitted by system policy", detected

    # Verify extension matches detected format
    expected_extensions = SUPPORTED_MEDIA_TYPES.get(detected, {}).get("extensions", set())
    if ext and ext not in expected_extensions and detected != "application/zip":
        return (
            False,
            f"File extension '{ext}' does not match detected file format '{detected}'",
            detected
        )

    # Check declared MIME compatibility if provided by client
    if declared_mime:
        declared = declared_mime.lower().split(";")[0].strip()
        # Allow standard synonyms (e.g. audio/mp3 vs audio/mpeg)
        synonyms = {
            "audio/mp3": "audio/mpeg",
            "image/jpg": "image/jpeg",
            "application/x-zip-compressed": "application/zip"
        }
        normalized_declared = synonyms.get(declared, declared)
        normalized_detected = synonyms.get(detected, detected)

        if normalized_declared != normalized_detected and normalized_declared in allowed_mimes:
            # Special case: generic zip or generic octet-stream
            if not (normalized_declared in ("application/zip", "application/octet-stream") and "openxmlformats" in normalized_detected):
                return (
                    False,
                    f"File signature mismatch: declared MIME '{declared_mime}' does not match detected '{detected}'",
                    detected
                )

    return True, "Valid file signature", detected


# ---------------------------------------------------------------------------
# 3. FILENAME SANITIZATION & PATH TRAVERSAL PREVENTER
# ---------------------------------------------------------------------------

def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitize client-provided filename:
    - Strips directory traversal components (../, ..\\, etc.)
    - Removes null bytes and control characters
    - Strips leading dots (preventing hidden files)
    - Restricts characters to safe alphanumeric, dots, dashes, underscores
    - Limits total length while preserving extension
    """
    if not filename or not isinstance(filename, str):
        return f"media_{os.urandom(6).hex()}"

    # Strip null bytes and normalize slashes
    clean = filename.replace("\x00", "").replace("\\", "/")
    # Extract only the base name
    base = os.path.basename(clean)

    # Strip leading dots and spaces
    base = base.lstrip(". \t\r\n")

    # Replace forbidden characters
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    sanitized = re.sub(r"_+", "_", sanitized)

    # If empty or only underscores/dots, generate safe fallback
    if not sanitized or sanitized.replace("_", "").replace(".", "") == "":
        return f"media_{os.urandom(6).hex()}"

    # Enforce maximum length of 120 characters
    max_len = 120
    if len(sanitized) > max_len:
        name_part, ext_part = os.path.splitext(sanitized)
        ext_part = ext_part[:15]
        allowed_name_len = max(10, max_len - len(ext_part))
        sanitized = f"{name_part[:allowed_name_len]}{ext_part}"

    return sanitized


# ---------------------------------------------------------------------------
# 4. SIZE VALIDATION
# ---------------------------------------------------------------------------

def validate_file_size(size_bytes: int, max_file_size: int) -> Tuple[bool, Optional[str]]:
    if size_bytes <= 0:
        return False, "File is empty (0 bytes)"
    if size_bytes > max_file_size:
        return (
            False,
            f"File size ({size_bytes} bytes) exceeds maximum limit of {max_file_size} bytes ({max_file_size // (1024 * 1024)} MB)"
        )
    return True, None


def validate_request_size(total_bytes: int, max_request_size: int) -> Tuple[bool, Optional[str]]:
    if total_bytes > max_request_size:
        return (
            False,
            f"Total upload size ({total_bytes} bytes) exceeds maximum request limit of {max_request_size} bytes"
        )
    return True, None


# ---------------------------------------------------------------------------
# 5. CHANNEL & PROVIDER-SPECIFIC LIMITS & COMPATIBILITY
# ---------------------------------------------------------------------------

CHANNEL_MEDIA_LIMITS: Dict[str, Dict[str, Any]] = {
    "email": {
        "max_single_bytes": 10 * 1024 * 1024,  # 10 MB
        "max_total_bytes": 25 * 1024 * 1024,   # 25 MB
        "allowed_categories": {"image", "video", "audio", "document"}
    },
    "whatsapp": {
        "image_max_bytes": 5 * 1024 * 1024,    # 5 MB (jpeg, png)
        "video_max_bytes": 16 * 1024 * 1024,   # 16 MB (mp4, 3gp)
        "audio_max_bytes": 16 * 1024 * 1024,   # 16 MB (aac, mp3, ogg, amr)
        "document_max_bytes": 100 * 1024 * 1024, # 100 MB (pdf, office, txt, etc.)
        "sticker_max_bytes": 500 * 1024,       # 500 KB (webp)
        "allowed_categories": {"image", "video", "audio", "document"}
    },
    "sms": {
        "max_single_bytes": 5 * 1024 * 1024,   # 5 MB for MMS
        "allowed_categories": {"image", "audio", "document"},
        "supports_plain_sms_media": False
    },
    "microsoft_teams": {
        "max_single_bytes": 250 * 1024 * 1024, # 250 MB
        "allowed_categories": {"image", "video", "audio", "document"}
    },
    "teams": {
        "max_single_bytes": 250 * 1024 * 1024,
        "allowed_categories": {"image", "video", "audio", "document"}
    }
}

PROVIDER_MEDIA_LIMITS: Dict[str, Dict[str, Any]] = {
    "sendgrid": {
        "channel": "email",
        "max_single_bytes": 25 * 1024 * 1024,  # SendGrid allows up to 25 MB
        "max_total_bytes": 25 * 1024 * 1024,
        "allowed_categories": {"image", "video", "audio", "document"}
    },
    "ses": {
        "channel": "email",
        "max_single_bytes": 10 * 1024 * 1024,  # SES enforces 10 MB raw message ceiling
        "max_total_bytes": 10 * 1024 * 1024,
        "allowed_categories": {"image", "video", "audio", "document"}
    },
    "amazon_ses": {
        "channel": "email",
        "max_single_bytes": 10 * 1024 * 1024,
        "max_total_bytes": 10 * 1024 * 1024,
        "allowed_categories": {"image", "video", "audio", "document"}
    },
    "smtp": {
        "channel": "email",
        "max_single_bytes": 25 * 1024 * 1024,
        "max_total_bytes": 25 * 1024 * 1024,
        "allowed_categories": {"image", "video", "audio", "document"}
    },
    "twilio": {
        "channel": "sms",
        "mms_max_bytes": 5 * 1024 * 1024,  # 5 MB
        "allowed_mimes": {
            "image/jpeg", "image/png", "image/gif",
            "audio/mpeg", "audio/ogg", "text/vcard", "application/pdf"
        },
        "supported_country_prefixes": {"+1"}  # Twilio MMS primarily supports US and Canada (+1)
    },
    "meta": {
        "channel": "whatsapp",
        "image_max_bytes": 5 * 1024 * 1024,
        "video_max_bytes": 16 * 1024 * 1024,
        "audio_max_bytes": 16 * 1024 * 1024,
        "document_max_bytes": 100 * 1024 * 1024,
        "sticker_max_bytes": 500 * 1024
    },
    "teams": {
        "channel": "microsoft_teams",
        "inline_max_bytes": 4 * 1024 * 1024,
        "drive_session_max_bytes": 250 * 1024 * 1024
    }
}


def validate_provider_media_limits(
    channel: str,
    provider: Optional[str],
    media_record: Dict[str, Any],
    recipient: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Enforce provider-specific media constraints and destination compatibility.
    """
    channel = (channel or "").lower().strip()
    provider = (provider or "").lower().strip() if provider else None
    filename = media_record.get("filename", "unknown")
    mime_type = media_record.get("mime_type", "")
    size_bytes = int(media_record.get("size_bytes", 0))
    type_info = SUPPORTED_MEDIA_TYPES.get(mime_type, {"category": "other"})
    category = type_info.get("category")

    # Provider-specific checks
    if channel == "email" and provider in ("ses", "amazon_ses"):
        cfg = PROVIDER_MEDIA_LIMITS["ses"]
        if category not in cfg["allowed_categories"]:
            return False, f"Amazon SES does not support category '{category}' for '{filename}'"
        if size_bytes > cfg["max_single_bytes"]:
            return False, f"Amazon SES attachment '{filename}' ({size_bytes} bytes) exceeds 10 MB limit"
        return True, None

    if channel == "email" and provider == "sendgrid":
        cfg = PROVIDER_MEDIA_LIMITS["sendgrid"]
        if category not in cfg["allowed_categories"]:
            return False, f"SendGrid does not support category '{category}' for '{filename}'"
        if size_bytes > cfg["max_single_bytes"]:
            return False, f"SendGrid attachment '{filename}' ({size_bytes} bytes) exceeds 25 MB limit"
        return True, None

    if channel == "sms" and provider == "twilio":
        cfg = PROVIDER_MEDIA_LIMITS["twilio"]
        if size_bytes > cfg["mms_max_bytes"]:
            return False, f"Twilio MMS file '{filename}' ({size_bytes} bytes) exceeds 5 MB provider limit"
        if mime_type not in cfg["allowed_mimes"]:
            return False, f"Twilio MMS does not support MIME type '{mime_type}' for '{filename}'"
        if recipient:
            recip_clean = str(recipient).strip()
            # If not starting with +1 (or 1 without + for 11 digits), MMS is unsupported
            is_us_ca = recip_clean.startswith("+1") or (len(recip_clean) == 11 and recip_clean.startswith("1"))
            if not is_us_ca:
                return False, f"Twilio MMS is only supported for US and Canada (+1) phone numbers. Destination '{recipient}' does not support MMS."
        return True, None

    # Base channel validation
    chan_valid, chan_err = validate_media_for_channel(media_record, channel)
    if not chan_valid:
        return False, chan_err

    return True, None


def check_channel_compatibility(mime_type: str, size_bytes: int) -> Dict[str, bool]:
    """Calculate which channels support this media item based on MIME and size."""
    compatibility: Dict[str, bool] = {}
    type_info = SUPPORTED_MEDIA_TYPES.get(mime_type, {"category": "other"})
    category = type_info.get("category")

    # Email
    email_cfg = CHANNEL_MEDIA_LIMITS["email"]
    compatibility["email"] = (
        category in email_cfg["allowed_categories"] and
        size_bytes <= email_cfg["max_single_bytes"]
    )

    # WhatsApp
    wa_cfg = CHANNEL_MEDIA_LIMITS["whatsapp"]
    if category == "image":
        if mime_type == "image/webp":
            compatibility["whatsapp"] = size_bytes <= wa_cfg["sticker_max_bytes"]
        else:
            compatibility["whatsapp"] = size_bytes <= wa_cfg["image_max_bytes"]
    elif category == "video":
        compatibility["whatsapp"] = size_bytes <= wa_cfg["video_max_bytes"]
    elif category == "audio":
        compatibility["whatsapp"] = size_bytes <= wa_cfg["audio_max_bytes"]
    elif category == "document":
        compatibility["whatsapp"] = size_bytes <= wa_cfg["document_max_bytes"]
    else:
        compatibility["whatsapp"] = False

    # SMS / MMS
    sms_cfg = CHANNEL_MEDIA_LIMITS["sms"]
    compatibility["sms"] = (
        category in sms_cfg["allowed_categories"] and
        size_bytes <= sms_cfg["max_single_bytes"]
    )

    # Teams
    teams_cfg = CHANNEL_MEDIA_LIMITS["microsoft_teams"]
    compatibility["microsoft_teams"] = (
        category in teams_cfg["allowed_categories"] and
        size_bytes <= teams_cfg["max_single_bytes"]
    )
    compatibility["teams"] = compatibility["microsoft_teams"]

    return compatibility


def validate_media_for_channel(media_record: Dict[str, Any], channel: str) -> Tuple[bool, Optional[str]]:
    """
    Enforce channel-specific restrictions before message dispatch.
    Returns (is_valid, error_reason).
    """
    channel = (channel or "").lower().strip()
    if channel not in CHANNEL_MEDIA_LIMITS:
        return False, f"Unsupported channel '{channel}' for media dispatch"

    mime_type = media_record.get("mime_type", "")
    size_bytes = int(media_record.get("size_bytes", 0))
    filename = media_record.get("filename", "unknown")
    type_info = SUPPORTED_MEDIA_TYPES.get(mime_type, {"category": "other"})
    category = type_info.get("category")

    if channel == "email":
        cfg = CHANNEL_MEDIA_LIMITS["email"]
        if size_bytes > cfg["max_single_bytes"]:
            return False, f"Attachment '{filename}' ({size_bytes} bytes) exceeds Email single file limit of {cfg['max_single_bytes']} bytes (10 MB)"
        return True, None

    if channel == "whatsapp":
        cfg = CHANNEL_MEDIA_LIMITS["whatsapp"]
        if category == "image":
            if mime_type == "image/webp":
                if size_bytes > cfg["sticker_max_bytes"]:
                    return False, f"WhatsApp sticker '{filename}' ({size_bytes} bytes) exceeds 500 KB limit"
            elif size_bytes > cfg["image_max_bytes"]:
                return False, f"WhatsApp image '{filename}' ({size_bytes} bytes) exceeds 5 MB limit"
        elif category == "video":
            if size_bytes > cfg["video_max_bytes"]:
                return False, f"WhatsApp video '{filename}' ({size_bytes} bytes) exceeds 16 MB limit"
        elif category == "audio":
            if size_bytes > cfg["audio_max_bytes"]:
                return False, f"WhatsApp audio '{filename}' ({size_bytes} bytes) exceeds 16 MB limit"
        elif category == "document":
            if size_bytes > cfg["document_max_bytes"]:
                return False, f"WhatsApp document '{filename}' ({size_bytes} bytes) exceeds 100 MB limit"
        else:
            return False, f"WhatsApp does not support media category '{category}' for '{filename}'"
        return True, None

    if channel == "sms":
        cfg = CHANNEL_MEDIA_LIMITS["sms"]
        if size_bytes > cfg["max_single_bytes"]:
            return False, f"MMS media '{filename}' ({size_bytes} bytes) exceeds MMS limit of 5 MB"
        if category not in cfg["allowed_categories"]:
            return False, f"MMS does not support category '{category}' for '{filename}'"
        return True, None

    if channel in ("microsoft_teams", "teams"):
        cfg = CHANNEL_MEDIA_LIMITS["microsoft_teams"]
        if size_bytes > cfg["max_single_bytes"]:
            return False, f"Teams attachment '{filename}' ({size_bytes} bytes) exceeds 250 MB limit"
        return True, None

    return True, None


# ---------------------------------------------------------------------------
# 6. MALWARE SCANNER INTERFACE
# ---------------------------------------------------------------------------

@dataclass
class MalwareScanResult:
    is_clean: bool
    scan_status: str  # "CLEAN", "INFECTED", "NOT_CONFIGURED", "FAILED"
    scanner_name: str
    threat_name: Optional[str] = None
    details: Optional[str] = None
    scan_time: Optional[str] = None


class BaseMalwareScanner(ABC):
    @property
    @abstractmethod
    def scanner_name(self) -> str:
        pass

    @abstractmethod
    def scan(self, data: bytes, filename: str = "") -> MalwareScanResult:
        pass


class NoOpMalwareScanner(BaseMalwareScanner):
    """
    Default scanner when no real antimalware engine (e.g. ClamAV) is configured.
    Crucial: Sets scan_status="NOT_CONFIGURED" and never falsely claims the file was scanned.
    """
    @property
    def scanner_name(self) -> str:
        return "none"

    def scan(self, data: bytes, filename: str = "") -> MalwareScanResult:
        return MalwareScanResult(
            is_clean=True,
            scan_status="NOT_CONFIGURED",
            scanner_name=self.scanner_name,
            details="No malware scanner configured in environment",
            scan_time=datetime.now(timezone.utc).isoformat()
        )


class ClamAVMalwareScanner(BaseMalwareScanner):
    """
    Real ClamAV daemon malware scanner via clamd network socket.
    """
    def __init__(self, host: str = "localhost", port: int = 3310, timeout: int = 10):
        self.host = host
        self.port = port
        self.timeout = timeout

    @property
    def scanner_name(self) -> str:
        return "clamav"

    def scan(self, data: bytes, filename: str = "") -> MalwareScanResult:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                # ClamAV INSTREAM protocol: 'zINSTREAM\0' followed by chunks: <length><data> followed by 0-length chunk
                sock.sendall(b"zINSTREAM\0")
                chunk_size = 64 * 1024
                for offset in range(0, len(data), chunk_size):
                    chunk = data[offset:offset + chunk_size]
                    sock.sendall(len(chunk).to_bytes(4, byteorder="big") + chunk)
                sock.sendall((0).to_bytes(4, byteorder="big"))

                response = b""
                while True:
                    part = sock.recv(1024)
                    if not part:
                        break
                    response += part

            resp_str = response.decode("utf-8", errors="replace").strip()
            if "OK" in resp_str:
                return MalwareScanResult(
                    is_clean=True,
                    scan_status="CLEAN",
                    scanner_name=self.scanner_name,
                    details="File clean",
                    scan_time=now_iso
                )
            elif "FOUND" in resp_str:
                # Example: stream: Eicar-Signature FOUND
                threat = resp_str.replace("stream:", "").replace("FOUND", "").strip()
                return MalwareScanResult(
                    is_clean=False,
                    scan_status="INFECTED",
                    scanner_name=self.scanner_name,
                    threat_name=threat,
                    details=f"Malware detected: {threat}",
                    scan_time=now_iso
                )
            else:
                return MalwareScanResult(
                    is_clean=False,
                    scan_status="FAILED",
                    scanner_name=self.scanner_name,
                    details=f"Unexpected ClamAV response: {resp_str}",
                    scan_time=now_iso
                )
        except socket.timeout:
            return MalwareScanResult(
                is_clean=False,
                scan_status="FAILED",
                scanner_name=self.scanner_name,
                details="ClamAV scan connection timed out",
                scan_time=now_iso
            )
        except (ConnectionRefusedError, socket.gaierror) as exc:
            return MalwareScanResult(
                is_clean=False,
                scan_status="FAILED",
                scanner_name=self.scanner_name,
                details=f"ClamAV scanner unavailable: {exc}",
                scan_time=now_iso
            )
        except Exception as exc:
            return MalwareScanResult(
                is_clean=False,
                scan_status="FAILED",
                scanner_name=self.scanner_name,
                details=f"ClamAV scan connection failed: {exc}",
                scan_time=now_iso
            )


def get_malware_scanner(config: Optional[Dict[str, Any]] = None) -> BaseMalwareScanner:
    """
    Factory to retrieve active malware scanner.
    If CLAMAV_HOST is provided, returns ClamAVMalwareScanner.
    Otherwise returns NoOpMalwareScanner with status 'NOT_CONFIGURED'.
    """
    host = (config or {}).get("CLAMAV_HOST") or os.getenv("CLAMAV_HOST")
    if host:
        port = int((config or {}).get("CLAMAV_PORT") or os.getenv("CLAMAV_PORT", "3310"))
        return ClamAVMalwareScanner(host=host, port=port)
    return NoOpMalwareScanner()
