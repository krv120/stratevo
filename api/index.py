"""Vercel Python function entrypoint; all persistence must use DATABASE_URL."""
import os
from app.server import Handler

class handler(Handler):
    def do_GET(self):
        if not os.environ.get('DATABASE_URL') and self.path.startswith('/api/'):
            return self.send(503, {'error':'Persistent database is not configured.'})
        super().do_GET()

    def do_POST(self):
        if not os.environ.get('DATABASE_URL'):
            return self.send(503, {'error':'Persistent database is not configured.'})
        super().do_POST()
