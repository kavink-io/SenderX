import socket
import cssutils._fetch
import cssutils.util

# Neutralize fetcher
cssutils._fetch._defaultFetcher = lambda url: None
cssutils.util._defaultFetcher = lambda url: None

dns_calls = []
orig = socket.getaddrinfo
def tracked(*args, **kwargs):
    dns_calls.append(args[0])
    raise AssertionError(f"DNS attempted: {args[0]}")
socket.getaddrinfo = tracked

from premailer import Premailer
p = Premailer('<style>@\\69 mport url("http://evil-bypass.test/a.css");</style><p>Hello</p>', allow_network=False)
res = p.transform()
print("Result transformed successfully! DNS calls count:", len(dns_calls))
