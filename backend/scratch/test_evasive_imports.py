import socket
from premailer import Premailer

dns_calls = []
orig_getaddrinfo = socket.getaddrinfo

def tracked_getaddrinfo(*args, **kwargs):
    dns_calls.append(args[0])
    raise AssertionError(f"DNS call attempted to: {args[0]}")

socket.getaddrinfo = tracked_getaddrinfo

html_tests = [
    '<style>@/*comment*/import url("http://evil-comment.test/a.css");</style><p>Hi</p>',
    '<style>@\nimport url("http://evil-newline.test/a.css");</style><p>Hi</p>',
    '<style>@\timport url("http://evil-tab.test/a.css");</style><p>Hi</p>',
    '<style>@\\69 mport url("http://evil-escape.test/a.css");</style><p>Hi</p>',
    '<style>@import "http://evil-no-url.test/a.css"</style><p>Hi</p>',
    '<link rel="stylesheet" href="http://evil-link.test/a.css"><p>Hi</p>',
    '<link rel="stylesheet"\n href="http://evil-link2.test/a.css"><p>Hi</p>',
]

for i, h in enumerate(html_tests):
    dns_calls.clear()
    try:
        p = Premailer(h, allow_network=False, allow_loading_external_files=False)
        p.transform()
        print(f"Test {i}: Premailer completed. DNS calls: {dns_calls}")
    except Exception as e:
        print(f"Test {i}: Premailer EXCEPTION: {e}")
