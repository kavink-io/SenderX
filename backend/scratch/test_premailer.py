import premailer
import re

html = '<img src="{{ logo_url }}"><a href="{{ cta_url }}">Click</a>'
p = premailer.Premailer(
    html,
    preserve_handlebar_syntax=True,
    allow_network=False,
    allow_loading_external_files=False,
    keep_style_tags=True,
    strip_important=False
)
out = p.transform()
print("Out with preserve_handlebar_syntax:", out)

# Let's also check regex unescape if needed:
# Replace %7B%7B / %20 inside {{ ... }}
# If premailer still left %20 or %7B%7B:
def fix_jinja_urls(html_str):
    # Fix {{%20var%20}} -> {{ var }}
    # Fix %7B%7Bvar%7D%7D -> {{ var }}
    def _unquote_jinja(m):
        content = m.group(1)
        content = content.replace("%20", " ")
        return f"{{{{ {content.strip()} }}}}"
    
    res = re.sub(r"\{\{([^\}]+)\}\}", _unquote_jinja, html_str)
    res = re.sub(r"%7B%7B([^\%]+)%7D%7D", _unquote_jinja, res)
    return res

print("Fixed:", fix_jinja_urls(out))
