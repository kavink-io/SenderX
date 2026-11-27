"""
SenderX Template Service
Business logic for template management, sandboxed Jinja2 rendering,
variable validation, versioning, preview generation, compiler pipeline, and message engine integration.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import uuid

import jinja2

from app.modules.templates.models import (
    TemplateCreateModel,
    TemplateUpdateModel,
    TemplatePreviewModel,
    TemplateValidateModel
)
from app.modules.templates.repository import TemplateRepository
from app.modules.templates.security import (
    TemplateSecurityInspector,
    TemplateSandboxRunner,
    detect_template_variables,
    validate_declared_variables,
    sanitize_variable_value
)
from app.modules.templates.compiler import (
    compile_email_template,
    html_to_plain_text,
    STARTER_TEMPLATE_HTML,
    STARTER_TEMPLATE_CSS,
    STARTER_TEMPLATE_VARIABLES,
    EmailCompatibilityInspector
)
from app.modules.users.audit_repository import SecurityAuditRepository as AuditRepository


class TemplateService:

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def get_sandboxed_env(cls, autoescape: bool = True):
        from app.modules.templates.security import SenderXSandboxedEnvironment
        return SenderXSandboxedEnvironment(autoescape=autoescape)

    @classmethod
    def render_sandboxed(
        cls,
        template_text: str,
        variables: Optional[Dict[str, Any]] = None,
        autoescape: bool = True
    ) -> str:
        """Render template string using hardened SandboxedEnvironment."""
        return TemplateSandboxRunner.render(
            template_text=template_text,
            context=variables or {},
            autoescape=autoescape
        )

    @classmethod
    def validate_template_syntax(
        cls,
        subject: Optional[str] = None,
        html_body: Optional[str] = None,
        plain_text_body: Optional[str] = None
    ):
        """Validate Jinja AST for forbidden syntax, private attributes, imports."""
        for name, text in [("subject", subject), ("html_body", html_body), ("plain_text_body", plain_text_body)]:
            if text:
                TemplateSandboxRunner.inspect_ast(text, name=name)

    # --------------------------------------------------------------------------
    # SAVE-TIME VALIDATE ENDPOINT (5.6.3 & 5.6.6)
    # --------------------------------------------------------------------------

    @classmethod
    def validate_template(
        cls,
        data: Dict[str, Any],
        organization_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Validate template content without persisting:
        1. Checks HTML & CSS for security violations (<script>, on*, javascript:, expression(), etc.)
        2. Inspects Jinja AST for private attribute navigation or dangerous directives.
        3. Extracts all {{ variable }} tokens and compares against declared variables.
        4. Runs Gmail/Outlook compatibility checks.
        """
        html_source = data.get("html_body") or data.get("html") or data.get("html_content") or ""
        css_source = data.get("css") or data.get("css_content") or ""
        subject_source = data.get("subject") or ""
        declared_vars = data.get("variables") or []

        # 1. Security findings
        security_findings = []
        security_findings.extend(TemplateSecurityInspector.inspect_html(html_source))
        security_findings.extend(TemplateSecurityInspector.inspect_css(css_source))

        # 2. Syntax & AST inspection
        syntax_errors = []
        try:
            cls.validate_template_syntax(subject=subject_source, html_body=html_source)
        except ValueError as err:
            syntax_errors.append(str(err))

        # 3. Detect variables across subject, html, and css
        detected_vars = set()
        detected_vars.update(detect_template_variables(subject_source))
        detected_vars.update(detect_template_variables(html_source))
        detected_vars.update(detect_template_variables(css_source))

        # 4. Undeclared variables
        undeclared = validate_declared_variables(detected_vars, declared_vars)

        # 5. Compatibility warnings
        compat_warnings = EmailCompatibilityInspector.inspect(html_source, css_source)

        is_valid = len(security_findings) == 0 and len(syntax_errors) == 0 and len(undeclared) == 0
        all_errors = [*security_findings, *syntax_errors, *[f"Undeclared variable '{v}'" for v in undeclared]]

        return {
            "success": True,
            "status_code": 200,
            "data": {
                "valid": is_valid,
                "isValid": is_valid,
                "errors": all_errors,
                "warnings": compat_warnings,
                "security_findings": security_findings,
                "syntax_errors": syntax_errors,
                "compatibility_warnings": compat_warnings,
                "detected_variables": sorted(list(detected_vars)),
                "undeclared_variables": undeclared,
                "declared_count": len(declared_vars)
            }
        }

    # --------------------------------------------------------------------------
    # CRUD OPERATIONS
    # --------------------------------------------------------------------------

    @classmethod
    def create_template(
        cls,
        data: Dict[str, Any],
        organization_id: Optional[str],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new template in DRAFT status with compiled HTML and security enforcement."""
        try:
            validated = TemplateCreateModel(**data)
        except Exception as err:
            return {"success": False, "status_code": 400, "message": str(err)}

        # 1. Security scan
        sec_findings = []
        sec_findings.extend(TemplateSecurityInspector.inspect_html(validated.html_body or ""))
        sec_findings.extend(TemplateSecurityInspector.inspect_css(validated.css or ""))
        if sec_findings:
            return {
                "success": False,
                "status_code": 422,
                "message": f"Template security check failed: {'; '.join(sec_findings)}",
                "security_findings": sec_findings
            }

        # 2. Syntax & AST check
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

        # 3. Undeclared variables check
        detected_vars = set()
        detected_vars.update(detect_template_variables(subject))
        detected_vars.update(detect_template_variables(validated.html_body or ""))
        detected_vars.update(detect_template_variables(validated.css or ""))

        variables_dicts = [v.model_dump() for v in validated.variables] if validated.variables else []
        undeclared = validate_declared_variables(detected_vars, variables_dicts)
        if undeclared:
            return {
                "success": False,
                "status_code": 422,
                "message": f"Undeclared variable(s) found in template: {', '.join(undeclared)}. Please declare all variables in the Variables panel.",
                "undeclared_variables": undeclared
            }

        # 4. Check case-insensitive name uniqueness within tenant (ignoring deleted/archived)
        existing = TemplateRepository.find_by_name(
            validated.name,
            organization_id=organization_id,
            exclude_archived_or_deleted=True
        )
        if existing:
            return {
                "success": False,
                "status_code": 409,
                "message": f"Template with name '{validated.name}' already exists in this organization"
            }

        # 5. Run compiler pipeline: inlining, plain-text generation, compatibility warnings
        compilation = compile_email_template(
            html_source=validated.html_body or "",
            css_source=validated.css or ""
        )

        plain_text = validated.plain_text_body.strip() if validated.plain_text_body else compilation["plain_text"]

        now = cls._now()
        template_id = f"tmpl-{uuid.uuid4().hex[:12]}"
        target_status = validated.status or "DRAFT"

        doc = {
            "template_id": template_id,
            "organization_id": organization_id,
            "name": validated.name,
            "name_lower": validated.name.strip().lower(),
            "description": validated.description or "",
            "category": validated.category or "general",
            "channel": channel,
            "subject": subject,
            "html_body": validated.html_body or "",
            "css": validated.css or "",
            "compiled_html": compilation["compiled_html"],
            "plain_text_body": plain_text,
            "variables": variables_dicts,
            "strict_variables": bool(validated.strict_variables),
            "compatibility_warnings": compilation["warnings"],
            "header": validated.header or "",
            "footer": validated.footer or "",
            "version": 1,
            "status": target_status,
            "created_by": user_id or "system",
            "updated_by": user_id or "system",
            "created_at": now,
            "updated_at": now
        }

        if target_status in ("PUBLISHED", "ACTIVE"):
            doc["published_at"] = now
            doc["published_by"] = user_id or "system"

        created = TemplateRepository.create(doc)

        # Audit log
        AuditRepository.log_event(
            organization_id=organization_id or "PLATFORM",
            event_type="EMAIL_TEMPLATE_CREATED",
            actor_id=user_id,
            target_id=template_id,
            target_type="EMAIL_TEMPLATE",
            target_name=validated.name,
            action_label="Created Email Template",
            summary=f"Created email template '{validated.name}' ({target_status} v1)"
        )

        if target_status in ("PUBLISHED", "ACTIVE"):
            AuditRepository.log_event(
                organization_id=organization_id or "PLATFORM",
                event_type="EMAIL_TEMPLATE_PUBLISHED",
                actor_id=user_id,
                target_id=template_id,
                target_type="EMAIL_TEMPLATE",
                target_name=validated.name,
                action_label="Published Email Template",
                summary=f"Published email template '{validated.name}' (v1)"
            )

        return {
            "success": True,
            "status_code": 201,
            "message": "Template published successfully" if target_status in ("PUBLISHED", "ACTIVE") else "Template created successfully",
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
        if not template or template.get("status") == "DELETED":
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
        return {
            "success": True,
            "status_code": 200,
            **result,
            "data": {
                "items": result["items"],
                "total": result["pagination"]["total"],
                "pagination": result["pagination"]
            }
        }

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
        if not template or template.get("status") == "DELETED":
            return {"success": False, "status_code": 404, "message": "Template not found"}

        try:
            validated = TemplateUpdateModel(**data)
        except Exception as err:
            return {"success": False, "status_code": 400, "message": str(err)}

        # 1. Security scan on updated HTML/CSS
        sec_findings = []
        if validated.html_body is not None:
            sec_findings.extend(TemplateSecurityInspector.inspect_html(validated.html_body))
        if validated.css is not None:
            sec_findings.extend(TemplateSecurityInspector.inspect_css(validated.css))
        if sec_findings:
            return {
                "success": False,
                "status_code": 422,
                "message": f"Template security check failed: {'; '.join(sec_findings)}",
                "security_findings": sec_findings
            }

        # 2. Syntax check on updated fields
        try:
            cls.validate_template_syntax(
                subject=validated.subject,
                html_body=validated.html_body,
                plain_text_body=validated.plain_text_body
            )
        except ValueError as err:
            return {"success": False, "status_code": 400, "message": str(err)}

        # 3. Name collision check if name is being changed
        if validated.name and validated.name.strip().lower() != template.get("name_lower", template["name"].lower()):
            existing = TemplateRepository.find_by_name(
                validated.name,
                organization_id=organization_id,
                exclude_archived_or_deleted=True
            )
            if existing and existing["template_id"] != template_id:
                return {
                    "success": False,
                    "status_code": 409,
                    "message": f"Template with name '{validated.name}' already exists in this organization"
                }

        # Determine effective content for compilation & variable checks
        effective_subject = validated.subject if validated.subject is not None else template.get("subject", "")
        effective_html = validated.html_body if validated.html_body is not None else template.get("html_body", "")
        effective_css = validated.css if validated.css is not None else template.get("css", "")

        effective_vars = [v.model_dump() for v in validated.variables] if validated.variables is not None else template.get("variables", [])

        # 4. Undeclared variables check
        detected_vars = set()
        detected_vars.update(detect_template_variables(effective_subject))
        detected_vars.update(detect_template_variables(effective_html))
        detected_vars.update(detect_template_variables(effective_css))

        undeclared = validate_declared_variables(detected_vars, effective_vars)
        if undeclared:
            return {
                "success": False,
                "status_code": 422,
                "message": f"Undeclared variable(s) found in template: {', '.join(undeclared)}. Please declare all variables in the Variables panel.",
                "undeclared_variables": undeclared
            }

        # 5. Run compiler pipeline
        compilation = compile_email_template(
            html_source=effective_html,
            css_source=effective_css
        )

        now = cls._now()
        current_version = template.get("version", 1)
        is_active = template.get("status") in ("ACTIVE", "PUBLISHED")
        requested_status = validated.status
        effective_channel = (validated.channel or template.get("channel") or "email").lower().strip()
        effective_plain = validated.plain_text_body if validated.plain_text_body is not None else template.get("plain_text_body", "")

        if requested_status in ("PUBLISHED", "ACTIVE"):
            if effective_channel == "sms":
                if not effective_plain and not effective_html:
                    return {"success": False, "status_code": 400, "message": "SMS template must have message content before publishing"}
            else:
                if not str(effective_subject or "").strip():
                    return {"success": False, "status_code": 400, "message": "Email template requires a non-empty subject before publishing"}
                if not str(effective_html or "").strip() and not str(effective_plain or "").strip():
                    return {"success": False, "status_code": 400, "message": "Email template requires an HTML or plain-text body before publishing"}

        update_fields: Dict[str, Any] = {
            "updated_at": now,
            "updated_by": user_id or "system",
            "compiled_html": compilation["compiled_html"],
            "compatibility_warnings": compilation["warnings"]
        }

        if requested_status is not None:
            if requested_status != template.get("status"):
                update_fields["status"] = requested_status
            if requested_status in ("PUBLISHED", "ACTIVE"):
                update_fields["published_at"] = now
                update_fields["published_by"] = user_id or "system"

        # Collect changed fields
        content_changed = False
        content_keys = ["subject", "html_body", "css", "plain_text_body", "variables", "strict_variables", "header", "footer"]

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

        if validated.plain_text_body is None and (validated.html_body is not None or validated.css is not None):
            update_fields["plain_text_body"] = compilation["plain_text"]

        # Versioning: If ACTIVE and content changed, archive current version and bump version number
        if is_active and content_changed:
            version_snapshot = {
                "template_id": template_id,
                "organization_id": organization_id,
                "version": current_version,
                "name": template["name"],
                "subject": template["subject"],
                "html_body": template.get("html_body", ""),
                "css": template.get("css", ""),
                "compiled_html": template.get("compiled_html", ""),
                "plain_text_body": template.get("plain_text_body", ""),
                "variables": template.get("variables", []),
                "strict_variables": template.get("strict_variables", False),
                "compatibility_warnings": template.get("compatibility_warnings", []),
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

        # Audit log
        new_v = updated_doc.get("version", current_version)
        AuditRepository.log_event(
            organization_id=organization_id or "PLATFORM",
            event_type="EMAIL_TEMPLATE_UPDATED",
            actor_id=user_id,
            target_id=template_id,
            target_type="EMAIL_TEMPLATE",
            target_name=updated_doc.get("name"),
            action_label="Updated Email Template",
            summary=f"Updated email template '{updated_doc.get('name')}' (v{new_v})"
        )

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
        user_id: Optional[str] = None,
        target_status: str = "ACTIVE"
    ) -> Dict[str, Any]:
        """Validate, compile, and transition template status to PUBLISHED or ACTIVE."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template or template.get("status") == "DELETED":
            return {"success": False, "status_code": 404, "message": "Template not found"}

        norm_target = str(target_status or "ACTIVE").strip().upper()
        if norm_target not in ("ACTIVE", "PUBLISHED"):
            norm_target = "ACTIVE"

        subject = template.get("subject", "")
        html_body = template.get("html_body", "")
        css = template.get("css", "")
        plain_text = template.get("plain_text_body", "")

        # Security scan before publishing
        sec_findings = []
        sec_findings.extend(TemplateSecurityInspector.inspect_html(html_body or ""))
        sec_findings.extend(TemplateSecurityInspector.inspect_css(css or ""))
        if sec_findings:
            return {
                "success": False,
                "status_code": 422,
                "message": f"Template security check failed: {'; '.join(sec_findings)}",
                "security_findings": sec_findings
            }

        # Syntax & AST check before publishing
        try:
            cls.validate_template_syntax(subject=subject, html_body=html_body, plain_text_body=plain_text)
        except ValueError as err:
            return {"success": False, "status_code": 400, "message": str(err)}

        # Undeclared variables check before publishing
        detected_vars = set()
        detected_vars.update(detect_template_variables(subject or ""))
        detected_vars.update(detect_template_variables(html_body or ""))
        detected_vars.update(detect_template_variables(css or ""))
        undeclared = validate_declared_variables(detected_vars, template.get("variables", []))
        if undeclared:
            return {
                "success": False,
                "status_code": 422,
                "message": f"Undeclared variable(s) found in template: {', '.join(undeclared)}. Please declare all variables in the Variables panel.",
                "undeclared_variables": undeclared
            }

        channel = template.get("channel", "email")
        if channel == "sms":
            if not plain_text and not html_body:
                return {"success": False, "status_code": 400, "message": "SMS template must have message content before publishing"}
        else:
            if not str(subject or "").strip():
                return {"success": False, "status_code": 400, "message": "Template must have a subject before publishing"}
            if not str(html_body or "").strip() and not str(plain_text or "").strip():
                return {"success": False, "status_code": 400, "message": "Template must have an HTML or plain-text body before publishing"}

        # Compile before publishing
        compilation = compile_email_template(
            html_source=html_body or "",
            css_source=css or ""
        )

        now = cls._now()
        update_data = {
            "status": norm_target,
            "published_at": now,
            "published_by": user_id or "system",
            "compiled_html": compilation["compiled_html"],
            "plain_text_body": plain_text or compilation["plain_text"],
            "compatibility_warnings": compilation["warnings"],
            "updated_at": now,
            "updated_by": user_id or "system"
        }

        TemplateRepository.update(
            template_id,
            update_data,
            organization_id=organization_id
        )

        updated_doc = TemplateRepository.find_by_id(template_id, organization_id=organization_id)

        AuditRepository.log_event(
            organization_id=organization_id or "PLATFORM",
            event_type="EMAIL_TEMPLATE_PUBLISHED",
            actor_id=user_id,
            target_id=template_id,
            target_type="EMAIL_TEMPLATE",
            target_name=template.get("name"),
            action_label="Published Email Template",
            summary=f"Published email template '{template.get('name')}' (v{template.get('version', 1)})"
        )

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
        if not template or template.get("status") == "DELETED":
            return {"success": False, "status_code": 404, "message": "Template not found"}

        now = cls._now()
        TemplateRepository.update(
            template_id,
            {"status": "ARCHIVED", "updated_at": now, "updated_by": user_id or "system"},
            organization_id=organization_id
        )

        updated_doc = TemplateRepository.find_by_id(template_id, organization_id=organization_id)

        AuditRepository.log_event(
            organization_id=organization_id or "PLATFORM",
            event_type="EMAIL_TEMPLATE_ARCHIVED",
            actor_id=user_id,
            target_id=template_id,
            target_type="EMAIL_TEMPLATE",
            target_name=template.get("name"),
            action_label="Archived Email Template",
            summary=f"Archived email template '{template.get('name')}'"
        )

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
        if not template or template.get("status") == "DELETED":
            return {"success": False, "status_code": 404, "message": "Template not found"}

        now = cls._now()
        new_template_id = f"tmpl-{uuid.uuid4().hex[:12]}"
        base_name = f"Copy of {template['name']}"
        new_name = base_name

        # Avoid name collision
        counter = 1
        while TemplateRepository.find_by_name(new_name, organization_id=organization_id, exclude_archived_or_deleted=True):
            new_name = f"{base_name} ({counter})"
            counter += 1

        new_doc = {
            "template_id": new_template_id,
            "organization_id": organization_id,
            "name": new_name,
            "name_lower": new_name.strip().lower(),
            "description": template.get("description", ""),
            "category": template.get("category", "general"),
            "channel": template.get("channel", "email"),
            "subject": template.get("subject", ""),
            "html_body": template.get("html_body", ""),
            "css": template.get("css", ""),
            "compiled_html": template.get("compiled_html", ""),
            "plain_text_body": template.get("plain_text_body", ""),
            "variables": template.get("variables", []),
            "strict_variables": template.get("strict_variables", False),
            "compatibility_warnings": template.get("compatibility_warnings", []),
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

        AuditRepository.log_event(
            organization_id=organization_id or "PLATFORM",
            event_type="EMAIL_TEMPLATE_DUPLICATED",
            actor_id=user_id,
            target_id=new_template_id,
            target_type="EMAIL_TEMPLATE",
            target_name=new_name,
            action_label="Duplicated Email Template",
            summary=f"Duplicated email template '{template['name']}' to '{new_name}'"
        )

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
        organization_id: Optional[str],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Soft delete a template."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template or template.get("status") == "DELETED":
            return {"success": False, "status_code": 404, "message": "Template not found"}

        deleted = TemplateRepository.delete(template_id, organization_id=organization_id)

        AuditRepository.log_event(
            organization_id=organization_id or "PLATFORM",
            event_type="EMAIL_TEMPLATE_DELETED",
            actor_id=user_id,
            target_id=template_id,
            target_type="EMAIL_TEMPLATE",
            target_name=template.get("name"),
            action_label="Deleted Email Template",
            summary=f"Deleted email template '{template.get('name')}'"
        )

        return {
            "success": deleted,
            "status_code": 200 if deleted else 500,
            "message": "Template deleted successfully" if deleted else "Could not delete template"
        }

    # --------------------------------------------------------------------------
    # LIVE PREVIEW (5.6.1 & 5.6.6)
    # --------------------------------------------------------------------------

    @classmethod
    def preview_template(
        cls,
        template_id: Optional[str] = None,
        sample_data: Optional[Dict[str, Any]] = None,
        organization_id: Optional[str] = None,
        html_body: Optional[str] = None,
        css: Optional[str] = None,
        subject: Optional[str] = None,
        variables: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Render live preview of HTML and plain-text body with sample data.
        Can render an existing template by template_id OR an unsaved draft from studio parameters.
        """
        raw_sample = sample_data or {}
        defined_vars = []
        target_subject = ""
        target_html = ""
        target_css = ""
        target_version = 1

        if template_id:
            template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
            if not template or template.get("status") == "DELETED":
                return {"success": False, "status_code": 404, "message": "Template not found"}
            target_subject = template.get("subject", "")
            target_html = template.get("html_body", "")
            target_css = template.get("css", "")
            defined_vars = template.get("variables", [])
            target_version = template.get("version", 1)
            target_header = template.get("header") or ""
            target_footer = template.get("footer") or ""
            target_plain = template.get("plain_text_body") or ""
        else:
            target_subject = subject or ""
            target_html = html_body or ""
            target_css = css or ""
            defined_vars = variables or []
            target_header = ""
            target_footer = ""
            target_plain = ""

            # Enforce security scanning on draft previews
            sec_findings = []
            if target_html:
                sec_findings.extend(TemplateSecurityInspector.inspect_html(target_html))
            if target_css:
                sec_findings.extend(TemplateSecurityInspector.inspect_css(target_css))
            if sec_findings:
                return {
                    "success": False,
                    "status_code": 400,
                    "message": "Template security validation failed: " + "; ".join(sec_findings),
                    "security_findings": sec_findings
                }

        # Merge sample values
        merged_context: Dict[str, Any] = {}
        missing_required = []

        for v in defined_vars:
            name = v["name"] if isinstance(v, dict) else v.name
            sample_val = v.get("sample_value") if isinstance(v, dict) else getattr(v, "sample_value", None)
            default_val = v.get("default") if isinstance(v, dict) else getattr(v, "default", None)
            is_req = v.get("required", True) if isinstance(v, dict) else getattr(v, "required", True)

            if name in raw_sample:
                merged_context[name] = raw_sample[name]
            elif sample_val is not None and sample_val != "":
                merged_context[name] = sample_val
            elif default_val is not None:
                merged_context[name] = default_val
            elif is_req:
                missing_required.append(name)
                merged_context[name] = f"[{name}]"  # Safe placeholder in preview mode

        # Extra keys in sample_data
        for k, val in raw_sample.items():
            if k not in merged_context:
                merged_context[k] = val

        # Inlining and compatibility warnings
        compilation = compile_email_template(target_html, target_css)

        # Include header and footer if present
        compiled_html_content = compilation["compiled_html"]
        plain_text_content = target_plain if target_plain else compilation["plain_text"]
        if target_header or target_footer:
            compiled_html_content = f"{target_header}\n{compiled_html_content}\n{target_footer}".strip()
            plain_text_content = f"{target_header}\n{plain_text_content}\n{target_footer}".strip()

        try:
            rendered_subject = cls.render_sandboxed(target_subject, merged_context, autoescape=False)
            rendered_html = cls.render_sandboxed(compiled_html_content, merged_context, autoescape=False)
            rendered_text = cls.render_sandboxed(plain_text_content, merged_context, autoescape=False)

            return {
                "success": True,
                "status_code": 200,
                "data": {
                    "template_id": template_id,
                    "version": target_version,
                    "rendered_subject": rendered_subject,
                    "rendered_html": rendered_html,
                    "rendered_plain_text": rendered_text,
                    "rendered_text": rendered_text,
                    "plain_text": rendered_text,
                    "warnings": compilation["warnings"],
                    "compatibility_warnings": compilation["warnings"],
                    "missing_variables": missing_required,
                    "context_used": merged_context
                }
            }

        except ValueError as err:
            return {"success": False, "status_code": 400, "message": str(err)}

    # --------------------------------------------------------------------------
    # STARTER LAYOUT (5.6.1)
    # --------------------------------------------------------------------------

    @classmethod
    def get_starter_layout(cls) -> Dict[str, Any]:
        """Return the pre-built responsive 600px transactional layout with standard variables."""
        return {
            "html": STARTER_TEMPLATE_HTML,
            "css": STARTER_TEMPLATE_CSS,
            "variables": STARTER_TEMPLATE_VARIABLES,
            "subject": "Welcome to {{ brand_name }}!"
        }

    # --------------------------------------------------------------------------
    # VERSION HISTORY RETRIEVAL
    # --------------------------------------------------------------------------

    @classmethod
    def get_versions(cls, template_id: str, organization_id: Optional[str]) -> Dict[str, Any]:
        """List historical versions along with the current live version."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template or template.get("status") == "DELETED":
            return {"success": False, "status_code": 404, "message": "Template not found"}

        history = TemplateRepository.find_versions(template_id, organization_id=organization_id)

        current_summary = {
            "version": template.get("version", 1),
            "status": template.get("status"),
            "updated_at": template.get("updated_at"),
            "updated_by": template.get("updated_by"),
            "is_current": True
        }

        version_list = [current_summary] + [
            {**h, "is_current": False} for h in history
        ]

        return {
            "success": True,
            "status_code": 200,
            "template_id": template_id,
            "current_version": template.get("version", 1),
            "total_versions": len(history) + 1,
            "data": version_list,
            "versions": version_list
        }

    @classmethod
    def get_version(cls, template_id: str, version: int, organization_id: Optional[str]) -> Dict[str, Any]:
        """Retrieve a specific historical snapshot or current version."""
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template or template.get("status") == "DELETED":
            return {"success": False, "status_code": 404, "message": "Template not found"}

        if template.get("version") == int(version):
            return {"success": True, "status_code": 200, "data": template, "is_current": True}

        snapshot = TemplateRepository.find_version(template_id, int(version), organization_id=organization_id)
        if not snapshot:
            return {"success": False, "status_code": 404, "message": f"Version {version} not found for this template"}

        return {"success": True, "status_code": 200, "data": snapshot, "is_current": False}

    # --------------------------------------------------------------------------
    # MESSAGE ENGINE INTEGRATION (5.6.4 & 5.6.5)
    # --------------------------------------------------------------------------

    @classmethod
    def resolve_and_render_for_message(
        cls,
        template_id: str,
        template_vars: Dict[str, Any],
        organization_id: str,
        template_version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Resolve template within organization, verify it is ACTIVE,
        validate required variables and types, check strict mode,
        and render subject and compiled body safely.
        """
        template = TemplateRepository.find_by_id(template_id, organization_id=organization_id)
        if not template or template.get("status") == "DELETED":
            return {
                "success": False,
                "status_code": 400,
                "message": f"Template '{template_id}' not found or belongs to another organization"
            }

        if template.get("status") not in ("ACTIVE", "PUBLISHED"):
            return {
                "success": False,
                "status_code": 400,
                "message": f"Template '{template_id}' is not in ACTIVE status (current: {template.get('status')})"
            }

        target_version = template.get("version", 1)
        target_subject = template.get("subject", "")
        target_html = template.get("compiled_html") or template.get("html_body", "")
        target_text = template.get("plain_text_body", "")
        defined_vars = template.get("variables", [])
        strict_mode = template.get("strict_variables", False)

        # Historical version if specified
        if template_version is not None and int(template_version) != target_version:
            historical = TemplateRepository.find_version(template_id, int(template_version), organization_id=organization_id)
            if not historical:
                return {
                    "success": False,
                    "status_code": 404,
                    "message": f"Requested template version {template_version} not found"
                }
            target_version = int(template_version)
            target_subject = historical.get("subject", "")
            target_html = historical.get("compiled_html") or historical.get("html_body", "")
            target_text = historical.get("plain_text_body", "")
            defined_vars = historical.get("variables", [])
            strict_mode = historical.get("strict_variables", False)

        provided_vars = dict(template_vars or {})
        defined_map = {v["name"]: v for v in defined_vars if isinstance(v, dict) and "name" in v}

        # 1. Strict mode: reject unknown keys
        if strict_mode:
            unknown_keys = set(provided_vars.keys()) - set(defined_map.keys())
            if unknown_keys:
                return {
                    "success": False,
                    "status_code": 422,
                    "message": f"Unknown template variable keys not allowed in strict mode: {', '.join(sorted(unknown_keys))}",
                    "unknown_keys": sorted(list(unknown_keys))
                }

        # 2. Check required variables and validate formats
        sanitized_context = {}
        missing_vars = []

        for name, v_def in defined_map.items():
            if name in provided_vars:
                raw_val = provided_vars[name]
                try:
                    sanitized_val = sanitize_variable_value(
                        name=name,
                        val=raw_val,
                        var_def=v_def,
                        is_subject=False
                    )
                    sanitized_context[name] = sanitized_val
                except ValueError as err:
                    return {
                        "success": False,
                        "status_code": 422,
                        "message": str(err)
                    }
            else:
                if v_def.get("default") is not None:
                    sanitized_context[name] = v_def["default"]
                elif v_def.get("required", True):
                    missing_vars.append(name)

        if missing_vars:
            return {
                "success": False,
                "status_code": 400,
                "message": f"Missing required template variables: {', '.join(sorted(missing_vars))}",
                "missing_variables": sorted(missing_vars)
            }

        # Copy any remaining permitted extra variables
        for k, v in provided_vars.items():
            if k not in sanitized_context:
                sanitized_context[k] = sanitize_variable_value(name=k, val=v, var_def={})

        # 3. Check subject for newline injection
        try:
            rendered_subject = cls.render_sandboxed(target_subject, sanitized_context, autoescape=False)
            if "\r" in rendered_subject or "\n" in rendered_subject:
                return {
                    "success": False,
                    "status_code": 422,
                    "message": "Rendered subject line contains illegal newline characters (header injection blocked)"
                }
        except ValueError as err:
            return {"success": False, "status_code": 422, "message": f"Subject rendering error: {str(err)}"}

        # 4. Sandboxed rendering of HTML and plain text
        try:
            rendered_html = cls.render_sandboxed(target_html, sanitized_context, autoescape=True)
            rendered_text = cls.render_sandboxed(target_text, sanitized_context, autoescape=False)

            return {
                "success": True,
                "status_code": 200,
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
                "status_code": 422,
                "message": f"Template rendering failed: {str(err)}"
            }
