import sys
sys.path.insert(0, "backend")
import socket
from app.modules.templates.compiler import compile_email_template

dns_calls = []
orig = socket.getaddrinfo
def tracked(*args, **kwargs):
    dns_calls.append(args[0])
    raise AssertionError(f"DNS attempted: {args[0]}")
socket.getaddrinfo = tracked

evasive_payloads = [
    '<style>@import "http://evil-1.test/a.css";</style><p>Hi</p>',
    '<style>@\\69 mport url("http://evil-2.test/a.css");</style><p>Hi</p>',
    '<style>@\\000069 mport url("http://evil-3.test/a.css");</style><p>Hi</p>',
    '<style>@/*comment*/import url("http://evil-4.test/a.css");</style><p>Hi</p>',
    '<style>@\nimport url("http://evil-5.test/a.css");</style><p>Hi</p>',
    '<style>@\timport url("http://evil-6.test/a.css");</style><p>Hi</p>',
    '<style>@import url("http://evil-7.test/a.css")</style><p>Hi</p>',
    '<style>@IMPORT url("http://evil-8.test/a.css");</style><p>Hi</p>',
    '<link rel="stylesheet" href="http://evil-9.test/a.css"><p>Hi</p>',
    '<link rel = "stylesheet" href = "http://evil-10.test/a.css" ><p>Hi</p>',
    '<link\nrel="stylesheet"\nhref="http://evil-11.test/a.css"><p>Hi</p>',
    '<link href="http://evil-12.test/a.css" rel="stylesheet"><p>Hi</p>',
]

for i, p in enumerate(evasive_payloads):
    dns_calls.clear()
    try:
        compile_email_template(p, "")
        print(f"Payload {i}: compiled without DNS! Calls: {dns_calls}")
    except Exception as e:
        print(f"Payload {i}: EXCEPTION: {e}")
