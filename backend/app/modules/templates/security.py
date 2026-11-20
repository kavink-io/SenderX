"""
SenderX Template Security Module
Save-time validation, AST inspection, sandboxed Jinja2 execution, and safe variable injection.
"""

import re
import html
import time
import jinja2
from jinja2 import nodes, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment, SecurityError
from typing import Any, Dict, List, Optional, Set, Tuple


# ==============================================================================
# 1. HTML / CSS SANITIZER & SECURITY INSPECTOR
# ==============================================================================

PROHIBITED_TAGS = {
    "script", "iframe", "object", "embed", "form", "input",
    "link", "base", "applet", "frame", "frameset"
}

PROHIBITED_ATTR_PREFIXES = ("on",)  # onclick, onerror, onload, onmouseover, etc.
DANGEROUS_PROTOCOLS = ("javascript:", "vbscript:", "data:")

CSS_DANGEROUS_PATTERNS = [
    (re.compile(r"expression\s*\(", re.IGNORECASE), "CSS expression() execution"),
    (re.compile(r"behavior\s*:", re.IGNORECASE), "CSS behavior: HTC component"),
    (re.compile(r"-moz-binding\s*:", re.IGNORECASE), "CSS -moz-binding XML execution"),
    (re.compile(r"@import\b", re.IGNORECASE), "CSS @import external stylesheet"),
    (re.compile(r"url\s*\(\s*['\"]?(?!https:\/\/)[^'\")]+['\"]?\s*\)", re.IGNORECASE), "CSS url() pointing to non-https resource")
]


class TemplateSecurityError(ValueError):
    """Raised when template content contains security violations."""
    def __init__(self, findings: List[str]):
        self.findings = findings
        super().__init__(f"Template security validation failed: {'; '.join(findings)}")


class TemplateSecurityInspector:
    """
    Save-time defense-in-depth scanner for email templates and incoming rich HTML.
    Rejects dangerous tags, script injections, event handlers, and protocol exploits.
    """

    @classmethod
    def inspect_html(cls, html_content: str) -> List[str]:
        """
        Inspect HTML source for forbidden tags, event attributes, and dangerous protocols.
        Returns a list of human-readable findings.
        """
        if not html_content:
            return []

        findings = []

        # 1. Prohibited tags
        tag_pattern = re.compile(r"<\s*([a-zA-Z0-9_\-]+)", re.IGNORECASE)
        for match in tag_pattern.finditer(html_content):
            tag_name = match.group(1).lower()
            if tag_name in PROHIBITED_TAGS:
                findings.append(f"Forbidden HTML tag '<{tag_name}>' detected")

        # Prohibited meta http-equiv (e.g. refresh, set-cookie)
        meta_http_equiv_pattern = re.compile(r"<\s*meta\b[^>]*\bhttp-equiv\s*=", re.IGNORECASE)
        if meta_http_equiv_pattern.search(html_content):
            findings.append("Forbidden HTML tag '<meta http-equiv>' detected")

        # 2. Event handler attributes (on*)
        event_attr_pattern = re.compile(r"\s+(on[a-zA-Z]+)\s*=", re.IGNORECASE)
        for match in event_attr_pattern.finditer(html_content):
            attr_name = match.group(1).lower()
            findings.append(f"Forbidden event handler attribute '{attr_name}' detected")

        # 3. Dangerous URL schemes in attributes (href, src, action, background, etc.)
        attr_val_pattern = re.compile(r"""\b(?:href|src|action|background|formaction)\s*=\s*['"]?([^'">\s]+)""", re.IGNORECASE)
        for match in attr_val_pattern.finditer(html_content):
            val = match.group(1).strip().lower()
            for proto in DANGEROUS_PROTOCOLS:
                if val.startswith(proto):
                    findings.append(f"Forbidden URL protocol '{proto}' detected in attribute: {val[:30]}")

        # 4. Inline style dangerous patterns
        style_attr_pattern = re.compile(r"""style\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
        for match in style_attr_pattern.finditer(html_content):
            style_content = match.group(1)
            findings.extend(cls.inspect_css(style_content, context="inline style"))

        return list(dict.fromkeys(findings))

    @classmethod
    def inspect_css(cls, css_content: str, context: str = "CSS stylesheet") -> List[str]:
        """
        Inspect CSS content for expressions, behaviors, imports, and non-https URLs.
        """
        if not css_content:
            return []

        findings = []
        for pattern, desc in CSS_DANGEROUS_PATTERNS:
            if pattern.search(css_content):
                findings.append(f"Forbidden pattern in {context}: {desc}")

        # Check for javascript: in CSS
        if "javascript:" in css_content.lower() or "vbscript:" in css_content.lower():
            findings.append(f"Forbidden script execution protocol in {context}")

        return list(dict.fromkeys(findings))

    @classmethod
    def sanitize_rich_html(cls, rich_html: str, max_size_bytes: int = 100 * 1024) -> str:
        """
        Sanitize allowed rich body content (e.g. body_html) using an allowlist approach.
        Removes dangerous tags while preserving safe formatting.
        """
        if not rich_html:
            return ""

        if len(rich_html.encode("utf-8")) > max_size_bytes:
            raise ValueError(f"Rich HTML content exceeds limit of {max_size_bytes // 1024} KB")

        import bleach
        allowed_tags = [
            "a", "abbr", "b", "blockquote", "br", "code", "div", "em", "h1", "h2",
            "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p", "pre",
            "span", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th",
            "thead", "tr", "u", "ul"
        ]
        allowed_attrs = {
            "*": ["style", "class", "title", "dir", "lang"],
            "a": ["href", "title", "target", "rel"],
            "img": ["src", "alt", "width", "height", "style"],
            "table": ["width", "border", "cellpadding", "cellspacing", "align", "bgcolor"],
            "td": ["align", "valign", "width", "height", "colspan", "rowspan", "bgcolor"],
            "th": ["align", "valign", "width", "height", "colspan", "rowspan", "bgcolor"]
        }
        allowed_protocols = ["http", "https", "mailto", "tel"]

        # Clean with bleach
        cleaned = bleach.clean(
            rich_html,
            tags=allowed_tags,
            attributes=allowed_attrs,
            protocols=allowed_protocols,
            strip=True
        )
        return cleaned


# ==============================================================================
# 2. SANDBOXED JINJA2 ENVIRONMENT
# ==============================================================================

MAX_RENDERED_OUTPUT_BYTES = 256 * 1024  # 256 KB
MAX_RENDER_SECONDS = 1.0


def safe_range(*args):
    """Capped range function preventing CPU/memory exhaustion."""
    if len(args) == 1:
        stop = int(args[0])
        if stop > 500:
            raise SecurityError("Range cannot exceed 500 items")
        return range(stop)
    elif len(args) == 2:
        start, stop = int(args[0]), int(args[1])
        if stop - start > 500:
            raise SecurityError("Range cannot exceed 500 items")
        return range(start, stop)
    elif len(args) == 3:
        start, stop, step = int(args[0]), int(args[1]), int(args[2])
        if step == 0:
            raise SecurityError("Range step cannot be 0")
        if abs((stop - start) // step) > 500:
            raise SecurityError("Range cannot exceed 500 items")
        return range(start, stop, step)
    return range(*args)


class SenderXSandboxedEnvironment(SandboxedEnvironment):
    """
    Hardened sandboxed Jinja2 environment enforcing StrictUndefined,
    blocking private attribute access, imports, includes, and extends.
    Intercepts binary operations to prevent resource exhaustion bombs.
    """
    intercepted_binops = frozenset(["*", "**", "+"])

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("autoescape", True)
        kwargs.setdefault("undefined", StrictUndefined)
        kwargs.setdefault("trim_blocks", True)
        kwargs.setdefault("lstrip_blocks", True)
        super().__init__(*args, **kwargs)
        self.globals["range"] = safe_range

    def call_binop(self, context, operator, left, right):
        if operator == "*":
            if isinstance(left, (str, list, tuple)) and isinstance(right, int):
                if len(left) * right > MAX_RENDERED_OUTPUT_BYTES:
                    raise SecurityError(
                        f"Multiplication output size ({len(left) * right // 1024} KB) exceeds maximum limit ({MAX_RENDERED_OUTPUT_BYTES // 1024} KB)"
                    )
            elif isinstance(right, (str, list, tuple)) and isinstance(left, int):
                if len(right) * left > MAX_RENDERED_OUTPUT_BYTES:
                    raise SecurityError(
                        f"Multiplication output size ({len(right) * left // 1024} KB) exceeds maximum limit ({MAX_RENDERED_OUTPUT_BYTES // 1024} KB)"
                    )
        elif operator == "**":
            if isinstance(right, (int, float)) and right > 100:
                raise SecurityError("Exponentiation power exceeds safe limit (max 100)")
        return super().call_binop(context, operator, left, right)

    def is_safe_attribute(self, obj, attr, value):
        """Block any attribute starting with underscore."""
        if isinstance(attr, str) and attr.startswith("_"):
            return False
        return super().is_safe_attribute(obj, attr, value)

    def is_safe_callable(self, obj):
        """Disallow executing raw callables unless explicitly whitelisted."""
        if callable(obj):
            # Allow basic filters / formatters only
            return super().is_safe_callable(obj)
        return True


class TemplateSandboxRunner:
    """Executes template rendering with AST inspection and size/time limits."""

    @classmethod
    def inspect_ast(cls, template_text: str, name: str = "template"):
        """
        Parse Jinja AST to catch dunder navigation, import/include/extends,
        macro recursion attempts, and nested loop bombs before execution.
        """
        if not template_text:
            return

        env = SenderXSandboxedEnvironment(autoescape=False)

        try:
            ast = env.parse(template_text)
        except jinja2.exceptions.TemplateSyntaxError as err:
            raise ValueError(f"Syntax error in {name} at line {err.lineno}: {err.message}")
        except Exception as err:
            raise ValueError(f"Template parsing error in {name}: {str(err)}")

        # Block private/dunder attribute navigation
        for getattr_node in ast.find_all(nodes.Getattr):
            if getattr_node.attr.startswith("_"):
                raise ValueError(f"Unsafe expression in {name}: access to private attribute '{getattr_node.attr}' is forbidden")

        # Block dangerous builtins / names
        forbidden_names = {"__builtins__", "__import__", "eval", "exec", "compile", "open", "os", "sys", "subprocess"}
        for name_node in ast.find_all(nodes.Name):
            if name_node.name.startswith("_") or name_node.name in forbidden_names:
                raise ValueError(f"Unsafe expression in {name}: access to name '{name_node.name}' is forbidden")

        # Block {% import %}, {% include %}, {% extends %}
        for node_type in (nodes.Import, nodes.FromImport, nodes.Include, nodes.Extends):
            if list(ast.find_all(node_type)):
                raise ValueError(f"Unsafe directive in {name}: template inheritance, import, and include are forbidden")

        # Block {% macro %} recursion / definition bombs
        if list(ast.find_all(nodes.Macro)):
            raise ValueError(f"Unsafe directive in {name}: macro definitions are forbidden")

        # Block recursive loops and nested loop bombs (> 2 levels)
        def get_loop_depth(node):
            max_child = 0
            for child in node.iter_child_nodes():
                max_child = max(max_child, get_loop_depth(child))
            if isinstance(node, nodes.For):
                if getattr(node, "recursive", False):
                    raise ValueError(f"Unsafe directive in {name}: recursive loops are forbidden")
                return 1 + max_child
            return max_child

        depth = get_loop_depth(ast)
        if depth > 2:
            raise ValueError(f"Template complexity error in {name}: nested loops exceed maximum depth (max 2, found {depth})")

        # Check literal range bounds in AST
        for call_node in ast.find_all(nodes.Call):
            if getattr(call_node.node, "name", None) == "range":
                for arg in call_node.args:
                    if isinstance(arg, nodes.Const) and isinstance(arg.value, (int, float)) and arg.value > 500:
                        raise ValueError(f"Template complexity error in {name}: range({arg.value}) exceeds maximum 500 items")

    @classmethod
    def render(
        cls,
        template_text: str,
        context: Dict[str, Any],
        autoescape: bool = True
    ) -> str:
        """
        Render template string with strict limits on output size and execution time.
        Uses streaming chunk generation to abort immediately if limits are breached.
        """
        if not template_text:
            return ""

        cls.inspect_ast(template_text)

        env = SenderXSandboxedEnvironment(autoescape=autoescape)

        start_time = time.perf_counter()
        try:
            tmpl = env.from_string(template_text)
            chunks = []
            total_bytes = 0
            for chunk in tmpl.generate(**(context or {})):
                chunk_len = len(chunk.encode("utf-8"))
                total_bytes += chunk_len
                if total_bytes > MAX_RENDERED_OUTPUT_BYTES:
                    raise ValueError(
                        f"Rendered template output ({total_bytes // 1024} KB) exceeds maximum limit of {MAX_RENDERED_OUTPUT_BYTES // 1024} KB"
                    )
                if time.perf_counter() - start_time > MAX_RENDER_SECONDS:
                    raise ValueError(
                        f"Template rendering exceeded time limit ({MAX_RENDER_SECONDS}s)"
                    )
                chunks.append(chunk)
            rendered = "".join(chunks)
        except jinja2.exceptions.UndefinedError as err:
            raise ValueError(f"Missing required variable: {err.message}")
        except SecurityError as err:
            raise ValueError(f"Security error during template rendering: {str(err)}")
        except RecursionError:
            raise ValueError("Template rendering failed: recursion limit exceeded")
        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Template rendering failed: {str(err)}")

        elapsed = time.perf_counter() - start_time
        if elapsed > MAX_RENDER_SECONDS:
            raise ValueError(f"Template rendering exceeded time limit ({elapsed:.2f}s > {MAX_RENDER_SECONDS}s)")

        return rendered


# ==============================================================================
# 3. VARIABLE EXTRACTION & VALIDATION
# ==============================================================================

VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*\|[^\}]+)?\s*\}\}")
COLOR_HEX_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
URL_HTTPS_PATTERN = re.compile(r"^https:\/\/[^\s\/$.?#].[^\s]*$", re.IGNORECASE)


def detect_template_variables(text: str) -> Set[str]:
    """Extract variable names referenced via {{ variable }} syntax."""
    if not text:
        return set()
    found = set()
    for match in VAR_PATTERN.finditer(text):
        found.add(match.group(1))
    return found


def validate_declared_variables(
    detected: Set[str],
    declared_variables: List[Dict[str, Any]]
) -> List[str]:
    """
    Compare detected variables with declared variable definitions.
    Returns any variable names present in template text but missing from declared list.
    """
    declared_names = {v.get("name") for v in declared_variables if isinstance(v, dict) and v.get("name")}
    return sorted(list(detected - declared_names))


def sanitize_variable_value(
    name: str,
    val: Any,
    var_def: Optional[Dict[str, Any]] = None,
    is_subject: bool = False
) -> Any:
    """
    Validate and sanitize a single variable value according to its definition:
    - Enforce max_length (default 1000)
    - Enforce https URL format if type is 'url'
    - Enforce hex color format if type is 'color'
    - Sanitize rich content if type is 'rich'
    - Strip control characters and block header injection CR/LF
    """
    var_def = var_def or {}
    var_type = var_def.get("type", "text")
    max_len = int(var_def.get("max_length") or 1000)

    if val is None:
        return ""

    if not isinstance(val, str):
        # Convert numbers/booleans to string
        val_str = str(val)
    else:
        val_str = val

    # 1. Header injection check (CR/LF in subject or header fields)
    if is_subject or var_def.get("is_header"):
        if "\r" in val_str or "\n" in val_str:
            raise ValueError(f"Variable '{name}' contains illegal newline characters (header injection blocked)")

    # 2. Control characters check (ASCII 0-31 except standard tab \t and newline \n)
    cleaned_chars = []
    for ch in val_str:
        cp = ord(ch)
        if cp < 32 and ch not in ("\t", "\n", "\r"):
            continue
        cleaned_chars.append(ch)
    val_str = "".join(cleaned_chars)

    # 3. Length validation
    if len(val_str) > max_len:
        raise ValueError(f"Variable '{name}' exceeds maximum allowed length of {max_len} characters")

    # 4. Type-specific validation
    if var_type == "url":
        clean_url = val_str.strip()
        if not URL_HTTPS_PATTERN.match(clean_url):
            raise ValueError(f"Variable '{name}' must be an absolute https:// URL")
        return clean_url

    elif var_type == "color":
        clean_color = val_str.strip()
        if not COLOR_HEX_PATTERN.match(clean_color):
            raise ValueError(f"Variable '{name}' must be a valid hex color (#RGB or #RRGGBB)")
        return clean_color

    elif var_type == "rich":
        # Rich content is passed through allowlist sanitizer
        return TemplateSecurityInspector.sanitize_rich_html(val_str)

    return val_str
