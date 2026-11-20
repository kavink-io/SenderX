"""
SenderX Template Security Module
Save-time validation, AST inspection, CSS allowlisting & value validation,
sandboxed Jinja2 execution, and safe variable injection.
"""

import re
import html
import time
import jinja2
from jinja2 import nodes, StrictUndefined, pass_environment
from jinja2.sandbox import SandboxedEnvironment, SecurityError
from typing import Any, Dict, List, Optional, Set, Tuple

import bleach
from bleach.css_sanitizer import CSSSanitizer


# ==============================================================================
# 1. HTML / CSS SANITIZER & SECURITY INSPECTOR
# ==============================================================================

PROHIBITED_TAGS = {
    "script", "iframe", "object", "embed", "form", "input",
    "link", "base", "applet", "frame", "frameset"
}

PROHIBITED_ATTR_PREFIXES = ("on",)  # onclick, onerror, onload, onmouseover, etc.
DANGEROUS_PROTOCOLS = ("javascript:", "vbscript:", "data:")

# Explicit CSS property allowlist strictly needed for email layouts
ALLOWED_CSS_PROPERTIES = frozenset([
    # Box model & Spacing
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "width", "min-width", "max-width",
    "height", "min-height", "max-height",
    "box-sizing", "display", "overflow", "opacity",
    # Typography
    "font", "font-family", "font-size", "font-weight", "font-style",
    "line-height", "letter-spacing",
    "text-align", "text-decoration", "text-transform", "text-indent",
    "word-break", "word-wrap",
    # Colors & Backgrounds
    "color", "background-color", "background",
    # Borders & Table styling
    "border", "border-width", "border-style", "border-color", "border-radius",
    "border-top", "border-right", "border-bottom", "border-left",
    "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
    "border-top-style", "border-right-style", "border-bottom-style", "border-left-style",
    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width",
    "border-collapse", "border-spacing", "table-layout", "vertical-align",
    "outline",
    # Email client resets & Outlook compatibility
    "-webkit-text-size-adjust", "-ms-text-size-adjust",
    "mso-table-lspace", "mso-table-rspace", "mso-line-height-rule"
])

SAFE_COLOR_NAMES = frozenset([
    "transparent", "inherit", "initial", "currentcolor",
    "black", "white", "red", "green", "blue", "yellow", "orange", "purple",
    "cyan", "magenta", "gray", "grey", "silver", "maroon", "navy", "olive",
    "teal", "aqua", "fuchsia", "lime", "gold", "pink", "brown",
    "coral", "indigo", "violet", "khaki", "plum", "salmon", "tan", "turquoise",
    "beige", "azure", "ivory", "lavender", "linen", "snow", "wheat", "crimson"
])

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_COLOR_RE = re.compile(r"^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}(?:\s*,\s*(?:0|1|0?\.\d+)\s*)?\)$", re.IGNORECASE)
HSL_COLOR_RE = re.compile(r"^hsla?\(\s*\d{1,3}\s*,\s*[\d.]+%?\s*,\s*[\d.]+%?(?:\s*,\s*(?:0|1|0?\.\d+)\s*)?\)$", re.IGNORECASE)

CSS_DANGEROUS_PATTERNS = [
    (re.compile(r"expression\s*\(", re.IGNORECASE), "CSS expression() execution"),
    (re.compile(r"behavior\s*:", re.IGNORECASE), "CSS behavior: HTC component"),
    (re.compile(r"-moz-binding\s*:", re.IGNORECASE), "CSS -moz-binding XML execution"),
    (re.compile(r"@import\b", re.IGNORECASE), "CSS @import external stylesheet"),
    (re.compile(r"url\s*\(\s*['\"]?(?!https:\/\/)[^'\")]+['\"]?\s*\)", re.IGNORECASE), "CSS url() pointing to non-https resource")
]


def is_safe_css_color(color_str: str) -> bool:
    """Validate CSS color value against supported safe formats."""
    clean = color_str.strip().lower()
    if clean in SAFE_COLOR_NAMES:
        return True
    if HEX_COLOR_RE.match(clean):
        return True
    if RGB_COLOR_RE.match(clean):
        return True
    if HSL_COLOR_RE.match(clean):
        return True
    return False


def validate_css_property(prop_name: str, prop_value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a single CSS property name and its value:
    - Name must be in ALLOWED_CSS_PROPERTIES allowlist
    - Value must not contain dangerous expressions, protocols, scripts, imports, or control chars
    - Colors must match safe formats (hex, rgb, hsl, safe named color)
    """
    prop = prop_name.strip().lower()
    val = prop_value.strip()

    if not prop or not val:
        return False, "Empty property or value"

    if prop not in ALLOWED_CSS_PROPERTIES:
        return False, f"Disallowed CSS property '{prop}'"

    # Reject control characters (0x00 - 0x1F except space and tab)
    for ch in val:
        if ord(ch) < 32 and ch not in (" ", "\t"):
            return False, f"Illegal control character in CSS property '{prop}'"

    val_lower = val.lower()

    # Reject CSS expressions, behavior, -moz-binding, @import
    if re.search(r"expression\s*\(", val_lower):
        return False, f"CSS expression() forbidden in property '{prop}'"
    if "behavior" in val_lower or "-moz-binding" in val_lower:
        return False, f"CSS behavior / binding forbidden in property '{prop}'"
    if "@import" in val_lower:
        return False, f"CSS @import forbidden in property '{prop}'"
    if "javascript:" in val_lower or "vbscript:" in val_lower:
        return False, f"Script execution protocol forbidden in property '{prop}'"
    if "data:" in val_lower:
        return False, f"Data URL forbidden in property '{prop}'"
    if "var(" in val_lower:
        return False, f"CSS custom property var() forbidden in property '{prop}'"
    if "\\" in val:
        return False, f"Backslash escape sequences forbidden in property '{prop}'"

    # URL references: must be https:// only
    if "url(" in val_lower:
        url_match = re.search(r"url\s*\(\s*['\"]?([^'\")]+)['\"]?\s*\)", val_lower)
        if not url_match or not url_match.group(1).startswith("https://"):
            return False, f"Unapproved or non-https URL reference in property '{prop}'"

    # Color validation for explicit color properties
    if prop in ("color", "background-color", "border-color", "border-top-color",
                "border-right-color", "border-bottom-color", "border-left-color"):
        tokens = [t.strip().rstrip(";") for t in val.split() if t.strip()]
        for tok in tokens:
            if tok.lower() in ("!important", "!important;"):
                continue
            if not is_safe_css_color(tok):
                return False, f"Invalid or unsafe CSS color '{tok}' in property '{prop}'"

    return True, None


def sanitize_inline_css(style_str: str) -> str:
    """
    Parse inline CSS style attribute, validate all declarations,
    and return only safe, allowed property-value pairs.
    """
    if not style_str:
        return ""

    safe_declarations = []
    # Split on semicolon, taking care of basic properties
    for decl in style_str.split(";"):
        decl = decl.strip()
        if not decl or ":" not in decl:
            continue
        parts = decl.split(":", 1)
        prop = parts[0].strip()
        val = parts[1].strip()

        is_valid, _ = validate_css_property(prop, val)
        if is_valid:
            safe_declarations.append(f"{prop}: {val}")

    return "; ".join(safe_declarations)


def sanitize_html_css_boundary(html_text: str) -> str:
    """
    Final boundary sanitizer: enforces that only allowed CSS properties survive in inline style attributes,
    and strips any dangerous protocols in attributes.
    """
    if not html_text:
        return ""

    def _clean_style_match(m):
        raw_style = m.group(2)
        sanitized = sanitize_inline_css(raw_style)
        return f'style="{sanitized}"' if sanitized else ""

    cleaned = re.sub(r'style=(["\'])(.*?)\1', _clean_style_match, html_text, flags=re.DOTALL)

    for proto in ("javascript:", "vbscript:", "data:"):
        cleaned = re.sub(
            rf"""\b(href|src|action|background|formaction)\s*=\s*(["\'])\s*{proto}[^"']*\2""",
            "",
            cleaned,
            flags=re.IGNORECASE
        )

    return cleaned


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

        # 4. Inline style inspection
        style_attr_pattern = re.compile(r"""style\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
        for match in style_attr_pattern.finditer(html_content):
            style_content = match.group(1)
            findings.extend(cls.inspect_css(style_content, context="inline style"))

        return list(dict.fromkeys(findings))

    @classmethod
    def inspect_css(cls, css_content: str, context: str = "CSS stylesheet") -> List[str]:
        """
        Inspect CSS content for expressions, behaviors, imports, and non-https URLs,
        as well as property allowlist violations.
        """
        if not css_content:
            return []

        findings = []
        for pattern, desc in CSS_DANGEROUS_PATTERNS:
            if pattern.search(css_content):
                findings.append(f"Forbidden pattern in {context}: {desc}")

        # Check for script execution protocols in CSS
        if "javascript:" in css_content.lower() or "vbscript:" in css_content.lower():
            findings.append(f"Forbidden script execution protocol in {context}")

        # Inspect individual declarations
        clean_css = re.sub(r"/\*.*?\*/", "", css_content, flags=re.DOTALL)
        # Match declarations: property: value
        decl_pattern = re.compile(r"([a-zA-Z0-9_\-]+)\s*:\s*([^;\}]+)")
        for match in decl_pattern.finditer(clean_css):
            prop = match.group(1).strip().lower()
            val = match.group(2).strip()
            # If in @media rule or container, ignore media query condition syntax
            if prop.startswith("@") or "screen" in prop:
                continue
            is_valid, reason = validate_css_property(prop, val)
            if not is_valid and reason:
                findings.append(f"{reason} in {context}")

        return list(dict.fromkeys(findings))

    @classmethod
    def sanitize_rich_html(cls, rich_html: str, max_size_bytes: int = 100 * 1024) -> str:
        """
        Sanitize allowed rich body content (e.g. body_html) using an allowlist approach.
        Removes dangerous tags while preserving safe formatting. Uses bleach with
        tinycss2 CSSSanitizer and safe inline CSS post-sanitization.
        """
        if not rich_html:
            return ""

        if len(rich_html.encode("utf-8")) > max_size_bytes:
            raise ValueError(f"Rich HTML content exceeds limit of {max_size_bytes // 1024} KB")

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

        # Configure Bleach CSSSanitizer with allowed properties
        css_sanitizer = CSSSanitizer(allowed_css_properties=list(ALLOWED_CSS_PROPERTIES))

        cleaned = bleach.clean(
            rich_html,
            tags=allowed_tags,
            attributes=allowed_attrs,
            protocols=allowed_protocols,
            css_sanitizer=css_sanitizer,
            strip=True
        )

        # Secondary deep value sanitization for style attributes (removes expressions/invalid colors)
        def _clean_style_match(m):
            raw_style = m.group(1)
            sanitized_style = sanitize_inline_css(raw_style)
            return f'style="{sanitized_style}"' if sanitized_style else ""

        cleaned = re.sub(r'style="([^"]*)"', _clean_style_match, cleaned)
        return cleaned


# ==============================================================================
# 2. SANDBOXED JINJA2 ENVIRONMENT & RESOURCE CONTROLS
# ==============================================================================

MAX_TEMPLATE_SOURCE_BYTES = 64 * 1024   # 64 KB
MAX_RENDERED_OUTPUT_BYTES = 256 * 1024  # 256 KB
MAX_RENDER_SECONDS = 1.0
MAX_CONTEXT_VARIABLES = 100
MAX_CONTEXT_DEPTH = 5


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


# Bounded Jinja filter implementations
def safe_center(val, width=80):
    if int(width) > 1000:
        raise SecurityError("Filter width exceeds safe limit (max 1000)")
    return jinja2.filters.do_center(val, width)


def safe_indent(s, width=4, first=False, blank=False):
    if int(width) > 200:
        raise SecurityError("Filter indent width exceeds safe limit (max 200)")
    return jinja2.filters.do_indent(s, width, first, blank)


@pass_environment
def safe_wordwrap(*args, **kwargs):
    if len(args) > 0 and hasattr(args[0], "newline_sequence"):
        env_arg = args[0]
        s = args[1] if len(args) > 1 else kwargs.pop("s", "")
        width = args[2] if len(args) > 2 else kwargs.pop("width", 79)
        rest = args[3:]
    else:
        env_arg = jinja2.Environment()
        s = args[0] if len(args) > 0 else kwargs.pop("s", "")
        width = args[1] if len(args) > 1 else kwargs.pop("width", 79)
        rest = args[2:]

    if int(width) > 1000:
        raise SecurityError("Filter wordwrap width exceeds safe limit (max 1000)")
    return jinja2.filters.do_wordwrap(env_arg, s, width=width, *rest, **kwargs)


class SenderXSandboxedEnvironment(SandboxedEnvironment):
    """
    Hardened sandboxed Jinja2 environment enforcing StrictUndefined,
    blocking private attribute access, imports, includes, and extends.
    Intercepts binary operations to prevent resource exhaustion bombs.
    """
    intercepted_binops = frozenset(["*", "**", "+", "-"])

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("autoescape", True)
        kwargs.setdefault("undefined", StrictUndefined)
        kwargs.setdefault("trim_blocks", True)
        kwargs.setdefault("lstrip_blocks", True)
        super().__init__(*args, **kwargs)
        self.globals["range"] = safe_range
        # Register bounded filters
        self.filters["center"] = safe_center
        self.filters["indent"] = safe_indent
        self.filters["wordwrap"] = safe_wordwrap

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
            elif isinstance(left, int) and isinstance(right, int):
                if abs(left) > 10**12 or abs(right) > 10**12:
                    raise SecurityError("Numeric multiplication operand exceeds safe limit")
        elif operator == "**":
            if isinstance(right, (int, float)) and (right >= 50 or (isinstance(left, (int, float)) and left > 10**6)):
                raise SecurityError("Exponentiation power exceeds safe limit (max 50)")
        elif operator in ("+", "-"):
            if isinstance(left, int) and isinstance(right, int):
                if abs(left) > 10**14 or abs(right) > 10**14:
                    raise SecurityError("Numeric operand exceeds safe integer limit")
        return super().call_binop(context, operator, left, right)

    def is_safe_attribute(self, obj, attr, value):
        """Block any attribute starting with underscore."""
        if isinstance(attr, str) and attr.startswith("_"):
            return False
        return super().is_safe_attribute(obj, attr, value)

    def is_safe_callable(self, obj):
        """Disallow executing raw callables unless explicitly whitelisted."""
        if callable(obj):
            return super().is_safe_callable(obj)
        return True


def validate_context_structure(context: Dict[str, Any], max_vars: int = MAX_CONTEXT_VARIABLES, max_depth: int = MAX_CONTEXT_DEPTH):
    """Enforce limits on total variable count, collection sizes, and nesting depth."""
    if not isinstance(context, dict):
        raise ValueError("Context must be a dictionary")

    if len(context) > max_vars:
        raise ValueError(f"Template context variable count ({len(context)}) exceeds maximum allowed limit ({max_vars})")

    def _check_depth(val: Any, current_depth: int):
        if current_depth > max_depth:
            raise ValueError(f"Context nesting depth exceeds maximum allowed depth of {max_depth}")
        if isinstance(val, dict):
            for v in val.values():
                _check_depth(v, current_depth + 1)
        elif isinstance(val, (list, tuple)):
            if len(val) > 1000:
                raise ValueError(f"Collection length ({len(val)}) exceeds maximum limit of 1000 items")
            for item in val:
                _check_depth(item, current_depth + 1)

    for val in context.values():
        _check_depth(val, 1)


class TemplateSandboxRunner:
    """Executes template rendering with AST inspection, size, depth, and time limits."""

    @classmethod
    def inspect_ast(cls, template_text: str, name: str = "template"):
        """
        Parse Jinja AST to catch dunder navigation, import/include/extends,
        macro recursion attempts, huge filter arguments, and nested loop bombs before execution.
        """
        if not template_text:
            return

        if len(template_text.encode("utf-8")) > MAX_TEMPLATE_SOURCE_BYTES:
            raise ValueError(
                f"Template source size ({len(template_text.encode('utf-8')) // 1024} KB) exceeds maximum limit of {MAX_TEMPLATE_SOURCE_BYTES // 1024} KB"
            )

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

        # Check filter calls with enormous numeric arguments
        for filter_node in ast.find_all(nodes.Filter):
            if filter_node.name in ("center", "indent", "wordwrap"):
                for arg in filter_node.args:
                    if isinstance(arg, nodes.Const) and isinstance(arg.value, (int, float)) and arg.value > 1000:
                        raise ValueError(f"Filter argument error in {name}: '{filter_node.name}({arg.value})' exceeds safe limit (max 1000)")

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

        # Validate input context variable count and nesting depth
        if context:
            validate_context_structure(context)

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
        if not HEX_COLOR_RE.match(clean_color):
            raise ValueError(f"Variable '{name}' must be a valid hex color (#RGB or #RRGGBB)")
        return clean_color

    elif var_type == "rich":
        return TemplateSecurityInspector.sanitize_rich_html(val_str)

    return val_str
