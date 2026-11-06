import http.server
import json
import os

# The version is stamped into the image at build time (see the Dockerfile),
# so /health always reports the image that is actually running.
VERSION = os.environ.get('APP_VERSION', 'dev')


class APIHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        status = 200
        if self.path == '/health':
            body = {'status': 'healthy', 'service': 'clearops-api', 'version': VERSION}
        elif self.path == '/data':
            body = {'records': int(os.environ.get('RECORD_COUNT', '42')), 'source': 'clearops-api', 'region': os.environ.get('REGION', 'local'), 'pod': os.environ.get('HOSTNAME', 'unknown')}
        else:
            status = 404  # was 200 in Module 10; an unknown path should say "not found"
            body = {'error': 'not found'}

        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


server = http.server.HTTPServer(('0.0.0.0', 8080), APIHandler)
print(f'ClearOps API {VERSION} running on port 8080')
server.serve_forever()
