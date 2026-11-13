"""
SenderX Template Service
Business logic for template management, sandboxed Jinja2 rendering,
variable validation, versioning, preview generation, and message engine integration.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

import jinja2
from jinja2.sandbox import SandboxedEnvironment, SecurityError

from app.modules.templates.models import (
    TemplateCreateModel,
    TemplateUpdateModel,
    TemplatePreviewModel
)
from app.modules.templates.repository import TemplateRepository


class TemplateService:

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def get_sandboxed_env(cls, autoescape: bool = True) -> SandboxedEnvironment:
        """Create a secure SandboxedEnvironment preventing SSTI and arbitrary Python code execution."""
        return SandboxedEnvironment(
            autoescape=autoescape,
            trim_blocks=True,
            lstrip_blocks=True
        )

    @classmethod
    def render_sandboxed(
        cls,
        template_text: str,
        variables: Optional[Dict[str, Any]] = None,
        autoescape: bool = True
    ) -> str:
        """
        Safely render a template string using a sandboxed Jinja2 environment.
        Raises ValueError on security violations or syntax errors.
        """
        if not template_text:
            return ""

        context = variables or {}

        try:
            env = cls.get_sandboxed_env(autoescape=autoescape)
            tmpl = env.from_string(template_text)
            return tmpl.render(**context)

        except SecurityError as err:
            raise ValueError(f"Unsafe template expression detected: {str(err)}")

        except jinja2.exceptions.TemplateSyntaxError as err:
            raise ValueError(f"Template syntax error at line {err.lineno}: {err.message}")

        except Exception as err:
            raise ValueError(f"Template rendering error: {str(err)}")

    @classmethod
    def validate_template_syntax(
        cls,
        subject: Optional[str] = None,
        html_body: Optional[str] = None,
        plain_text_body: Optional[str] = None
    ):
        """
        Pre-compile template strings and inspect AST to catch syntax errors
        and SSTI / code execution attempts early.
        """
        env = cls.get_sandboxed_env(autoescape=False)
        from jinja2 import nodes

        for name, text in [("subject", subject), ("html_body", html_body), ("plain_text_body", plain_text_body)]:
            if text:
                try:
                    ast = env.parse(text)
                except jinja2.exceptions.TemplateSyntaxError as err:
                    raise ValueError(f"Syntax error in {name} at line {err.lineno}: {err.message}")
                except Exception as err:
                    raise ValueError(f"Template parsing error in {name}: {str(err)}")

                # AST inspection for private/dunder attribute navigation (SSTI exploits)
                for getattr_node in ast.find_all(nodes.Getattr):
                    if getattr_node.attr.startswith("_"):
                        raise ValueError(f"Unsafe expression in {name}: access to private/dunder attribute '{getattr_node.attr}' is forbidden")

                # Block access to forbidden names
                forbidden_names = {"__builtins__", "__import__", "eval", "exec", "compile", "open"}
                for name_node in ast.find_all(nodes.Name):
                    if name_node.name.startswith("_") or name_node.name in forbidden_names:
                        raise ValueError(f"Unsafe expression in {name}: access to '{name_node.name}' is forbidden")

                try:
                    env.from_string(text)
                except SecurityError as err:
                    raise ValueError(f"Unsafe expression in {name}: {str(err)}")
                except jinja2.exceptions.TemplateSyntaxError as err:
                    raise ValueError(f"Syntax error in {name} at line {err.lineno}: {err.message}")

    # --------------------------------------------------
    # CRUD OPERATIONS
    # --------------------------------------------------

    @classmethod
    def create_template(
        cls,
        data: Dict[str, Any],
        organization_id: Optional[str],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new template in DRAFT status."""
        try:
            validated = TemplateCreateModel(**data)
        except Exception as err:
            return {"success": False, "status_code": 400, "message": str(err)}

        # Syntax check
        try:
            cls.validate_template_syntax(
                subject=validated.subject,
                html_body=validated.html_body,
                plain_text_body=validated.plain_text_body
            )
        except ValueError as err:
            return {"success": False, "status_code": 400, "message": str(err)}

        channel = (validated.channel or "email").lower().strip()
        subject = validated.subject or ""

        # Channel-aware requirements
        if channel == "email":
            if not subject.strip():
                return {"success": False, "status_code": 400, "message": "Email template requires a non-empty subject"}
            if not validated.html_body and not validated.plain_text_body:
                return {"success": False, "status_code": 400, "message": "Email template requires an HTML or plain-text body"}
        elif channel == "sms":
            if not validated.plain_text_body and not validated.html_body:
                return {"success": False, "status_code": 400, "message": "SMS template requires message content in plain_text_body"}
            if not subject.strip():
                subject = validated.name

        # Check name uniqueness within tenant
        existing = TemplateRepository.find_by_name(validated.name, organization_id=organization_id)
        if existing:
            return {
                "success": False,
                "status_code": 409,
                "message": f"Template with name '{validated.name}' already exists in this organization"
            }

        now = cls._now()
        template_id = f"tmpl-{uuid.uuid4().hex[:12]}"

        variables_dicts = [v.model_dump() for v in validated.variables] if validated.variables else []

        doc = {
            "template_id": template_id,
            "organization_id": organization_id,
            "name": validated.name,
            "description": validated.description or "",
            "category": validated.category or "general",
            "channel": channel,
            "subject": subject,
            "html_body": validated.html_body or "",
            "plain_text_body": validated.plain_text_body or "",
            "variables": variables_dicts,
            "header": validated.header or "",
            "footer": validated.footer or "",
            "version": 1,
            "status": "DRAFT",
            "created_by": user_id or "system",
            "updated_by": user_id or "system",
            "created_at": now,
            "updated_at": now
        }

        created = TemplateRepository.create(doc)
        return {
            "success": True,
            "status_code": 201,
            "message": "Template created successfully",
            "data": created
        }

    @classmethod
    def get_template(
        cls,
        template_id: str,
        organization_id: Optional[str]
    ) -> Dict[str, Any]:
        """Retrieve a single template by ID scoped to the organization."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}
        return {"success": True, "status_code": 200, "data": template}

    @classmethod
    def list_templates(
        cls,
        organization_id: Optional[str],
        page: int = 1,
        limit: int = 50,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """List templates for an organization with pagination and filters."""
        result = TemplateRepository.find_all(
            organization_id=organization_id,
            page=page,
            limit=limit,
            status=status,
            category=category,
            search=search
        )
        return {"success": True, "status_code": 200, **result}

    @classmethod
    def update_template(
        cls,
        template_id: str,
        data: Dict[str, Any],
        organization_id: Optional[str],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a template. If template is currently ACTIVE and content changes,
        a historical version snapshot is preserved and the version number is incremented.
        """
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}

        try:
            validated = TemplateUpdateModel(**data)
        except Exception as err:
            return {"success": False, "status_code": 400, "message": str(err)}

        # Syntax check on updated fields
        try:
            cls.validate_template_syntax(
                subject=validated.subject,
                html_body=validated.html_body,
                plain_text_body=validated.plain_text_body
            )
        except ValueError as err:
            return {"success": False, "status_code": 400, "message": str(err)}

        # Name collision check if name is being changed
        if validated.name and validated.name != template["name"]:
            existing = TemplateRepository.find_by_name(validated.name, organization_id=organization_id)
            if existing and existing["template_id"] != template_id:
                return {
                    "success": False,
                    "status_code": 409,
                    "message": f"Template with name '{validated.name}' already exists"
                }

        now = cls._now()
        current_version = template.get("version", 1)
        is_active = template.get("status") == "ACTIVE"

        update_fields: Dict[str, Any] = {"updated_at": now, "updated_by": user_id or "system"}

        # Collect changed fields
        content_changed = False
        content_keys = ["subject", "html_body", "plain_text_body", "variables", "header", "footer"]

        for k in ["name", "description", "category"] + content_keys:
            val = getattr(validated, k, None)
            if val is not None:
                if k == "variables":
                    val_dicts = [v.model_dump() for v in val]
                    if val_dicts != template.get("variables", []):
                        content_changed = True
                        update_fields[k] = val_dicts
                else:
                    if val != template.get(k):
                        if k in content_keys:
                            content_changed = True
                        update_fields[k] = val

        # Versioning: If ACTIVE and content changed, archive current version and bump version number
        if is_active and content_changed:
            version_snapshot = {
                "template_id": template_id,
                "organization_id": organization_id,
                "version": current_version,
                "name": template["name"],
                "subject": template["subject"],
                "html_body": template.get("html_body", ""),
                "plain_text_body": template.get("plain_text_body", ""),
                "variables": template.get("variables", []),
                "header": template.get("header", ""),
                "footer": template.get("footer", ""),
                "archived_at": now,
                "archived_by": user_id or "system",
                "created_at": template.get("created_at")
            }
            TemplateRepository.save_version(version_snapshot)
            update_fields["version"] = current_version + 1

        TemplateRepository.update(template_id, update_fields, organization_id=organization_id)
        updated_doc = TemplateRepository.find_by_id(template_id, organization_id=organization_id)

        return {
            "success": True,
            "status_code": 200,
            "message": "Template updated successfully",
            "version_incremented": is_active and content_changed,
            "data": updated_doc
        }

    @classmethod
    def publish_template(
        cls,
        template_id: str,
        organization_id: Optional[str],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transition template status to ACTIVE."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}

        channel = template.get("channel", "email")
        if channel == "sms":
            if not template.get("plain_text_body") and not template.get("html_body"):
                return {"success": False, "status_code": 400, "message": "SMS template must have message content before publishing"}
        else:
            if not template.get("subject"):
                return {"success": False, "status_code": 400, "message": "Template must have a subject before publishing"}
            if not template.get("html_body") and not template.get("plain_text_body"):
                return {"success": False, "status_code": 400, "message": "Template must have an HTML or plain-text body before publishing"}

        now = cls._now()
        TemplateRepository.update(
            template_id,
            {"status": "ACTIVE", "updated_at": now, "updated_by": user_id or "system"},
            organization_id=organization_id
        )

        updated_doc = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        return {
            "success": True,
            "status_code": 200,
            "message": "Template published and active for message delivery",
            "data": updated_doc
        }

    @classmethod
    def archive_template(
        cls,
        template_id: str,
        organization_id: Optional[str],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transition template status to ARCHIVED."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}

        now = cls._now()
        TemplateRepository.update(
            template_id,
            {"status": "ARCHIVED", "updated_at": now, "updated_by": user_id or "system"},
            organization_id=organization_id
        )

        updated_doc = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        return {
            "success": True,
            "status_code": 200,
            "message": "Template archived successfully",
            "data": updated_doc
        }

    @classmethod
    def duplicate_template(
        cls,
        template_id: str,
        organization_id: Optional[str],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Clone an existing template into a new DRAFT template."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}

        now = cls._now()
        new_template_id = f"tmpl-{uuid.uuid4().hex[:12]}"
        base_name = f"Copy of {template['name']}"
        new_name = base_name

        # Avoid name collision
        counter = 1
        while TemplateRepository.find_by_name(new_name, organization_id=organization_id):
            new_name = f"{base_name} ({counter})"
            counter += 1

        new_doc = {
            "template_id": new_template_id,
            "organization_id": organization_id,
            "name": new_name,
            "description": template.get("description", ""),
            "category": template.get("category", "general"),
            "subject": template.get("subject", ""),
            "html_body": template.get("html_body", ""),
            "plain_text_body": template.get("plain_text_body", ""),
            "variables": template.get("variables", []),
            "header": template.get("header", ""),
            "footer": template.get("footer", ""),
            "version": 1,
            "status": "DRAFT",
            "created_by": user_id or "system",
            "updated_by": user_id or "system",
            "created_at": now,
            "updated_at": now
        }

        created = TemplateRepository.create(new_doc)
        return {
            "success": True,
            "status_code": 201,
            "message": "Template duplicated successfully",
            "data": created
        }

    @classmethod
    def delete_template(
        cls,
        template_id: str,
        organization_id: Optional[str]
    ) -> Dict[str, Any]:
        """Permanently delete a template."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}

        deleted = TemplateRepository.delete(template_id, organization_id=organization_id)
        return {
            "success": deleted,
            "status_code": 200 if deleted else 500,
            "message": "Template deleted successfully" if deleted else "Could not delete template"
        }

    # --------------------------------------------------
    # PREVIEW & VARIABLE VALIDATION
    # --------------------------------------------------

    @classmethod
    def preview_template(
        cls,
        template_id: str,
        sample_data: Optional[Dict[str, Any]],
        organization_id: Optional[str]
    ) -> Dict[str, Any]:
        """Render live preview of HTML and plain-text body with sample data."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}

        data = sample_data or {}

        # Merge sample values from variable definitions if not provided in sample_data
        defined_vars = template.get("variables", [])
        merged_context: Dict[str, Any] = {}
        missing_required = []

        for v in defined_vars:
            name = v["name"]
            if name in data:
                merged_context[name] = data[name]
            elif v.get("sample_value") is not None:
                merged_context[name] = v["sample_value"]
            elif v.get("default") is not None:
                merged_context[name] = v["default"]
            elif v.get("required", True):
                missing_required.append(name)
                merged_context[name] = f"[{name}]"  # Placeholder in preview

        # Also include any extra keys in sample_data
        for k, val in data.items():
            if k not in merged_context:
                merged_context[k] = val

        try:
            rendered_subject = cls.render_sandboxed(template.get("subject", ""), merged_context, autoescape=False)

            # Combine header + html_body + footer
            full_html = ""
            if template.get("header"):
                full_html += template["header"] + "\n"
            full_html += template.get("html_body", "")
            if template.get("footer"):
                full_html += "\n" + template["footer"]

            rendered_html = cls.render_sandboxed(full_html, merged_context, autoescape=True)

            # Combine header + plain_text_body + footer
            full_text = ""
            if template.get("header"):
                full_text += template["header"] + "\n\n"
            full_text += template.get("plain_text_body", "")
            if template.get("footer"):
                full_text += "\n\n" + template["footer"]

            rendered_text = cls.render_sandboxed(full_text, merged_context, autoescape=False)

            return {
                "success": True,
                "status_code": 200,
                "data": {
                    "template_id": template_id,
                    "version": template.get("version", 1),
                    "rendered_subject": rendered_subject,
                    "rendered_html": rendered_html,
                    "rendered_plain_text": rendered_text,
                    "missing_variables": missing_required,
                    "context_used": merged_context
                }
            }

        except ValueError as err:
            return {"success": False, "status_code": 400, "message": str(err)}

    # --------------------------------------------------
    # VERSION HISTORY RETRIEVAL
    # --------------------------------------------------

    @classmethod
    def get_versions(cls, template_id: str, organization_id: Optional[str]) -> Dict[str, Any]:
        """List historical versions along with the current live version."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}

        history = TemplateRepository.find_versions(template_id, organization_id=organization_id)

        # Include current version summary
        current_summary = {
            "version": template.get("version", 1),
            "status": template.get("status"),
            "updated_at": template.get("updated_at"),
            "updated_by": template.get("updated_by"),
            "is_current": True
        }

        return {
            "success": True,
            "status_code": 200,
            "template_id": template_id,
            "current_version": template.get("version", 1),
            "total_versions": len(history) + 1,
            "versions": [current_summary] + [
                {**h, "is_current": False} for h in history
            ]
        }

    @classmethod
    def get_version(cls, template_id: str, version: int, organization_id: Optional[str]) -> Dict[str, Any]:
        """Retrieve a specific historical snapshot or current version."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {"success": False, "status_code": 404, "message": "Template not found"}

        # If requested version is the current live version
        if template.get("version") == int(version):
            return {"success": True, "status_code": 200, "data": template, "is_current": True}

        snapshot = TemplateRepository.find_version(template_id, int(version), organization_id=organization_id)
        if not snapshot:
            return {"success": False, "status_code": 404, "message": f"Version {version} not found for this template"}

        return {"success": True, "status_code": 200, "data": snapshot, "is_current": False}

    # --------------------------------------------------
    # MESSAGE ENGINE INTEGRATION
    # --------------------------------------------------

    @classmethod
    def resolve_and_render_for_message(
        cls,
        template_id: str,
        template_vars: Dict[str, Any],
        organization_id: str,
        template_version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Resolve template within the organization, verify it is ACTIVE,
        validate required variables, render subject and body with sandboxed Jinja2,
        and return rendered content with metadata snapshot.
        """
        # 1. Tenant-scoped retrieval
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template:
            return {
                "success": False,
                "message": f"Template '{template_id}' not found or belongs to another organization"
            }

        # 2. Status verification
        if template.get("status") != "ACTIVE":
            return {
                "success": False,
                "message": f"Template '{template_id}' is not in ACTIVE status (current: {template.get('status')})"
            }

        target_version = template.get("version", 1)
        target_subject = template.get("subject", "")
        target_html = template.get("html_body", "")
        target_text = template.get("plain_text_body", "")
        target_header = template.get("header", "")
        target_footer = template.get("footer", "")
        defined_vars = template.get("variables", [])

        # If a specific historical version is requested
        if template_version is not None and int(template_version) != target_version:
            historical = TemplateRepository.find_version(template_id, int(template_version), organization_id=organization_id)
            if not historical:
                return {
                    "success": False,
                    "message": f"Requested template version {template_version} not found"
                }
            target_version = int(template_version)
            target_subject = historical.get("subject", "")
            target_html = historical.get("html_body", "")
            target_text = historical.get("plain_text_body", "")
            target_header = historical.get("header", "")
            target_footer = historical.get("footer", "")
            defined_vars = historical.get("variables", [])

        # 3. Validate required variables
        provided_vars = dict(template_vars or {})
        missing_vars = []

        for v in defined_vars:
            name = v["name"]
            if name not in provided_vars:
                if v.get("default") is not None:
                    provided_vars[name] = v["default"]
                elif v.get("required", True):
                    missing_vars.append(name)

        if missing_vars:
            return {
                "success": False,
                "message": f"Missing required template variables: {', '.join(sorted(missing_vars))}"
            }

        # 4. Sandboxed rendering
        try:
            rendered_subject = cls.render_sandboxed(target_subject, provided_vars, autoescape=False)

            full_html = ""
            if target_header:
                full_html += target_header + "\n"
            full_html += target_html
            if target_footer:
                full_html += "\n" + target_footer

            rendered_html = cls.render_sandboxed(full_html, provided_vars, autoescape=True)

            full_text = ""
            if target_header:
                full_text += target_header + "\n\n"
            full_text += target_text
            if target_footer:
                full_text += "\n\n" + target_footer

            rendered_text = cls.render_sandboxed(full_text, provided_vars, autoescape=False)

            return {
                "success": True,
                "data": {
                    "template_id": template_id,
                    "version": target_version,
                    "subject": rendered_subject,
                    "html_body": rendered_html,
                    "plain_text_body": rendered_text
                }
            }

        except ValueError as err:
            return {
                "success": False,
                "message": f"Template rendering failed: {str(err)}"
            }
