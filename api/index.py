"""Vercel adapter: preserve public paths across the serverless catch-all rewrite."""
from urllib.parse import parse_qsl, urlencode, urlsplit
from app.server import Handler

ROUTE_PARAMETER = '__stratevo_path'


class handler(Handler):
    def restore_route(self):
        target = urlsplit(self.path)
        # Only interpret the routing envelope at the function entrypoint. Never
        # trust client-supplied forwarding headers or change direct app routes.
        if target.path not in ('/api/index', '/api/index.py'):
            return True
        pairs = parse_qsl(target.query, keep_blank_values=True)
        routes = [value for key, value in pairs if key == ROUTE_PARAMETER]
        if not routes:
            return True
        if len(routes) != 1:
            self.send(400, {'error': 'Invalid routing envelope.'})
            return False
        route = routes[0]
        if (not route.startswith('/') or route.startswith('//')
                or any(c in route for c in ('?', '#', '\\'))
                or any(ord(c) < 32 or ord(c) == 127 for c in route)):
            self.send(400, {'error': 'Invalid routing envelope.'})
            return False
        query = urlencode([(key, value) for key, value in pairs if key != ROUTE_PARAMETER])
        self.path = route + ('?' + query if query else '')
        return True

    def do_GET(self):
        if self.restore_route():
            super().do_GET()

    def do_POST(self):
        if self.restore_route():
            super().do_POST()
