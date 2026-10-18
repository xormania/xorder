"""Disposable HTTPS repository used by the certificate trust fixture."""
import functools
import http.server
import ssl
import sys
from pathlib import Path

root = Path(sys.argv[1])
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root)))
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.minimum_version = ssl.TLSVersion.TLSv1_2
context.load_cert_chain(root / "server.crt", root / "server.key")
server.socket = context.wrap_socket(server.socket, server_side=True)
(root / "port").write_text(str(server.server_port))
server.serve_forever()
