"""
SenderX Email Template Compiler & Compatibility Pipeline
Inlines CSS using premailer, preserves @media queries for mobile responsiveness,
inspects Gmail/Outlook compatibility, generates plain text, and provides starter layout.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from premailer import Premailer, transform


# ==============================================================================
# 1. STARTER TRANSACTIONAL LAYOUT (Responsive, Table-based, 600px max-width)
# ==============================================================================

STARTER_TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ subject }}</title>
</head>
<body class="email-body">
  <!-- Hidden Preheader -->
  <div class="preheader" style="display:none;font-size:1px;color:#333333;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
    {{ preheader }}
  </div>

  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" class="outer-table">
    <tr>
      <td align="center">
        <!-- Main 600px Container Table -->
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" class="container-table" style="max-width: 600px; width: 100%;">
          <!-- Header / Brand -->
          <tr>
            <td align="center" class="header-cell">
              {% if logo_url %}
              <img src="{{ logo_url }}" alt="{{ brand_name }}" width="140" style="display:block; border:0; outline:none; max-width:140px;" />
              {% else %}
              <h2 class="brand-text" style="color: {{ brand_color }}; margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">{{ brand_name }}</h2>
              {% endif %}
            </td>
          </tr>

          <!-- Content Body -->
          <tr>
            <td class="content-cell">
              <h1 class="main-heading" style="color: #1e293b; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 24px; font-weight: 700; margin: 0 0 16px 0;">
                {{ heading }}
              </h1>
              <p class="greeting" style="color: #334155; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 16px; line-height: 24px; margin: 0 0 12px 0;">
                Hello {{ recipient_name }},
              </p>
              <div class="body-text" style="color: #475569; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; line-height: 24px; margin: 0 0 24px 0;">
                {{ body_lines }}
              </div>

              <!-- Call to Action Button -->
              {% if cta_url and cta_text %}
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="btn-table" style="margin: 24px 0;">
                <tr>
                  <td align="center" bgcolor="{{ brand_color }}" style="border-radius: 6px;">
                    <a href="{{ cta_url }}" target="_blank" class="cta-button" style="background-color: {{ brand_color }}; color: #ffffff; display: inline-block; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 15px; font-weight: 600; padding: 12px 28px; text-decoration: none; border-radius: 6px;">
                      {{ cta_text }}
                    </a>
                  </td>
                </tr>
              </table>
              {% endif %}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td align="center" class="footer-cell">
              <p class="footer-text" style="color: #94a3b8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 12px; line-height: 18px; margin: 0;">
                {{ footer_text }}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

STARTER_TEMPLATE_CSS = """/* Email Client Default Resets */
body.email-body {
  margin: 0;
  padding: 0;
  background-color: #f1f5f9;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  -webkit-text-size-adjust: 100%;
  -ms-text-size-adjust: 100%;
}

.outer-table {
  background-color: #f1f5f9;
  padding: 30px 15px;
}

.container-table {
  background-color: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.header-cell {
  padding: 32px 30px 20px 30px;
  border-bottom: 1px solid #f1f5f9;
}

.content-cell {
  padding: 32px 30px;
}

.footer-cell {
  padding: 20px 30px 30px 30px;
  border-top: 1px solid #f1f5f9;
  background-color: #fafafa;
}

/* Responsive Media Queries (Preserved for Gmail / Apple Mail / iOS) */
@media only screen and (max-width: 600px) {
  .outer-table {
    padding: 10px 0 !important;
  }
  .container-table {
    border-radius: 0 !important;
    width: 100% !important;
  }
  .content-cell {
    padding: 24px 20px !important;
  }
  .cta-button {
    display: block !important;
    width: 100% !important;
    box-sizing: border-box !important;
  }
}
"""

STARTER_TEMPLATE_VARIABLES = [
    {"name": "subject", "type": "text", "required": True, "max_length": 250, "sample_value": "Welcome to Acme Corp!"},
    {"name": "preheader", "type": "text", "required": False, "max_length": 200, "sample_value": "Get started with your new account in 3 easy steps."},
    {"name": "brand_name", "type": "text", "required": True, "max_length": 80, "sample_value": "Acme Global"},
    {"name": "brand_color", "type": "color", "required": True, "max_length": 10, "sample_value": "#2563eb"},
    {"name": "logo_url", "type": "url", "required": False, "max_length": 500, "sample_value": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=140"},
    {"name": "recipient_name", "type": "text", "required": True, "max_length": 100, "sample_value": "Alex Taylor"},
    {"name": "heading", "type": "text", "required": True, "max_length": 150, "sample_value": "Welcome to Your New Workspace"},
    {"name": "body_lines", "type": "text", "required": True, "max_length": 2000, "sample_value": "We are excited to have you on board. Your team's communication hub is ready for dispatch."},
    {"name": "cta_text", "type": "text", "required": False, "max_length": 50, "sample_value": "Activate Your Account"},
    {"name": "cta_url", "type": "url", "required": False, "max_length": 500, "sample_value": "https://example.com/activate"},
    {"name": "footer_text", "type": "text", "required": False, "max_length": 300, "sample_value": "Acme Corp, 123 Innovation Way, Suite 400. You received this email because you signed up for an account."}
]


# ==============================================================================
# 2. EMAIL CLIENT COMPATIBILITY INSPECTOR (Gmail, Outlook, Yahoo)
# ==============================================================================

class EmailCompatibilityInspector:
    """
    Inspects template HTML and CSS for patterns known to break in major email clients
    such as Outlook desktop (Word rendering engine) and web clients (Gmail, Yahoo).
    Produces actionable warnings without blocking the author.
    """

    @classmethod
    def inspect(cls, html: str, css: str) -> List[str]:
        warnings = []
        combined_text = (html or "") + "\n" + (css or "")

        # 1. Flexbox / Grid layout checks
        if re.search(r"display\s*:\s*(?:flex|grid|inline-flex|inline-grid)\b", combined_text, re.IGNORECASE):
            warnings.append("Flexbox / Grid layout detected: Outlook and older email clients do not support flex or grid. Table-based layouts are strongly recommended.")

        # 2. CSS Positioning checks
        if re.search(r"position\s*:\s*(?:absolute|fixed|sticky)\b", combined_text, re.IGNORECASE):
            warnings.append("Positioning ('absolute', 'fixed', 'sticky') is not supported in Outlook and Gmail. Use table alignment and nested cells instead.")

        # 3. External stylesheets (<link rel="stylesheet">)
        if re.search(r"<link\s+[^>]*rel=[\"']?stylesheet[\"']?", html or "", re.IGNORECASE):
            warnings.append("External stylesheet (<link rel='stylesheet'>) detected: Major email clients strip external links. Place all styles in the CSS editor.")

        # 4. @import rules
        if re.search(r"@import\b", combined_text, re.IGNORECASE):
            warnings.append("@import rules detected: External fonts and styles imported via @import are ignored by Gmail and Outlook.")

        # 5. CSS variables (var(--...))
        if re.search(r"var\s*\(\s*--", combined_text, re.IGNORECASE):
            warnings.append("CSS custom properties (var(--variable)) are not supported in Outlook or Gmail. Use explicit hex codes and values.")

        # 6. Web fonts without fallbacks
        font_matches = re.finditer(r"font-family\s*:\s*([^;\}]+)", combined_text, re.IGNORECASE)
        for fm in font_matches:
            font_str = fm.group(1).lower()
            if any(f in font_str for f in ["roboto", "open sans", "lato", "montserrat", "poppins", "inter"]):
                if not any(fb in font_str for fb in ["sans-serif", "serif", "arial", "helvetica", "tahoma", "verdana"]):
                    warnings.append(f"Web font in '{fm.group(1).strip()}' is missing a web-safe fallback (e.g. Arial, Helvetica, sans-serif).")
                    break

        # 7. Background images without bgcolor fallback
        if re.search(r"background(?:-image)?\s*:\s*url\(", combined_text, re.IGNORECASE):
            if not re.search(r"(?:background-color|bgcolor)\s*:", combined_text, re.IGNORECASE) and 'bgcolor=' not in (html or "").lower():
                warnings.append("Background image detected without a fallback background-color. Outlook will render a blank background if images are disabled.")

        # 8. Structural checks: Table-based layout
        if html and "<table" not in html.lower():
            warnings.append("Table-less layout detected: Email clients (especially Microsoft Outlook) require <table> elements for reliable multi-column formatting.")

        # 9. Max-width 600px container recommendation
        if html and "600" not in html and "600px" not in combined_text:
            warnings.append("A max-width 600px container table is recommended to prevent horizontal overflow in desktop email readers.")

        # 10. Image accessibility & HTTPS checks
        img_tags = re.finditer(r"<img\s+([^>]+)>", html or "", re.IGNORECASE)
        for img in img_tags:
            attrs = img.group(1)
            if not re.search(r"\balt\s*=", attrs, re.IGNORECASE):
                warnings.append("One or more <img> tags are missing the 'alt' attribute, which harms accessibility and email deliverability.")
                break
            src_match = re.search(r"\bsrc\s*=\s*['\"]?([^'\">\s]+)", attrs, re.IGNORECASE)
            if src_match:
                src_val = src_match.group(1)
                if not src_val.startswith("https://") and not src_val.startswith("{{"):
                    warnings.append(f"Image source '{src_val[:40]}' is not an absolute https:// URL. Non-https images will trigger mixed-content warnings.")

        return list(dict.fromkeys(warnings))


# ==============================================================================
# 3. PLAIN-TEXT ALTERNATIVE GENERATOR
# ==============================================================================

def html_to_plain_text(html_content: str) -> str:
    """
    Convert an HTML email body into a clean, human-readable plain text alternative.
    Preserves links as 'Text (URL)', converts line breaks and headings to clean whitespace.
    """
    if not html_content:
        return ""

    text = html_content

    # Remove style and script blocks
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert links <a href="url">Text</a> -> Text (url)
    def _link_repl(match):
        attrs = match.group(1)
        label = match.group(2).strip()
        href_match = re.search(r"""href\s*=\s*['"]([^'"]+)['"]""", attrs, re.IGNORECASE)
        if href_match:
            url = href_match.group(1).strip()
            if label and label.lower() != url.lower():
                return f"{label} ({url})"
            return url
        return label

    text = re.sub(r"<a\s+([^>]+)>(.*?)</a>", _link_repl, text, flags=re.DOTALL | re.IGNORECASE)

    # Convert headings <h1..6> to block text with surrounding newlines
    text = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\n\1\n\n", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert paragraphs and list items to newlines
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\n\1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"\n* \1", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<tr[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Decode HTML entities
    import html
    text = html.unescape(text)

    # Collapse multiple blank lines into max 2
    lines = [line.strip() for line in text.splitlines()]
    result = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                result.append("")
                prev_empty = True
        else:
            result.append(line)
            prev_empty = False

    return "\n".join(result).strip()


# ==============================================================================
# 4. COMPILER ENGINE
# ==============================================================================

def compile_email_template(
    html_source: str,
    css_source: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compile email template by:
    1. Combining HTML source with CSS styles in <style> block.
    2. Inlining CSS properties into elements via premailer while preserving @media rules.
    3. Generating plain text alternative.
    4. Running compatibility scanner for Gmail / Outlook warnings.
    """
    raw_html = (html_source or "").strip()
    raw_css = (css_source or "").strip()

    # If CSS is provided, inject it into <head><style> before inlining
    merged_html = raw_html
    if raw_css:
        if "<head>" in merged_html:
            merged_html = merged_html.replace("<head>", f"<head>\n<style>\n{raw_css}\n</style>", 1)
        elif "<html>" in merged_html:
            merged_html = merged_html.replace("<html>", f"<html>\n<head>\n<style>\n{raw_css}\n</style>\n</head>", 1)
        else:
            merged_html = f"<style>\n{raw_css}\n</style>\n{merged_html}"

    # Inlining with premailer: preserve @media and responsive blocks with no network calls
    try:
        p = Premailer(
            merged_html,
            preserve_handlebar_syntax=True,
            allow_network=False,
            allow_loading_external_files=False,
            keep_style_tags=True,
            strip_important=False
        )
        compiled_html = p.transform()

        # Ensure Jinja expressions in URLs and attributes are restored intact (no %20 or %7B%7B)
        def _unquote_jinja(m):
            content = m.group(1).replace("%20", " ")
            return f"{{{{ {content.strip()} }}}}"

        compiled_html = re.sub(r"\{\{([^\}]+)\}\}", _unquote_jinja, compiled_html)
        compiled_html = re.sub(r"%7B%7B([^\%]+)%7D%7D", _unquote_jinja, compiled_html)
    except Exception as err:
        # Fallback if inliner throws on edge-case syntax
        compiled_html = merged_html

    # Generate plain text alternative
    plain_text = html_to_plain_text(raw_html)

    # Collect compatibility warnings
    warnings = EmailCompatibilityInspector.inspect(raw_html, raw_css)

    return {
        "compiled_html": compiled_html,
        "plain_text": plain_text,
        "warnings": warnings
    }

