"""R5 offline HTML launcher. Binds loopback only; never serves key files."""
import base64
import json
import secrets
import threading
import webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from CSM_Shuffler import ContinuousShuffleMachine, SUITS, RANKS, CSM_RELEASE

PATHS = (Path(r'C:\Poker_Game\A_Tools\Card'), Path(r'D:\Poker_Game - 銴�ˊ\A_Tools\Card'))

def choose_root(candidates=PATHS):
    for path in candidates:
        if path.is_dir():
            return path
    import tkinter as tk
    from tkinter import filedialog
    window = tk.Tk(); window.withdraw()
    try:
        value = filedialog.askdirectory(title='�豢� A_Tools/Card 鞈��憭�')
    finally:
        window.destroy()
    return Path(value) if value else None

def serve(root):
    token = secrets.token_urlsafe(32)
    html = Path(__file__).with_name('CSM_Manager.html').read_bytes()
    state = root/'A_Logs/Json/CSM_State.enc'
    key = root/'A_Logs/Keys/CSM_State.key'
    guard = threading.Lock()
    machine = None
    cache = {'stamp':None, 'snapshot':None, 'logs':[], 'logstamp':None}
    pictures = {}
    for suit in SUITS:
        for rank in RANKS:
            path = root/'Poker1'/f'{suit}{rank}.png'
            if path.is_file():
                pictures[suit+rank] = 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode('ascii')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code, data, kind='application/json; charset=utf-8'):
            try:
                self.send_response(code)
                self.send_header('Content-Type',kind)
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # The browser closed, refreshed, or superseded this polling
                # request before the response finished. No CSM operation failed.
                return

        def do_GET(self):
            nonlocal machine
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                self.send(403,b'{}'); return
            url = urlparse(self.path)
            if url.path == '/':
                self.send(200,html,'text/html; charset=utf-8'); return
            supplied = self.headers.get('X-CSM-Token','')
            if not secrets.compare_digest(supplied, token):
                self.send(403,b'{}'); return
            if url.path == '/api/images':
                self.send(200,json.dumps(pictures).encode()); return
            if url.path != '/api/state':
                self.send(404,b'{}'); return
            result = {}
            with guard:
                try:
                    if not state.is_file() or not key.is_file():
                        raise RuntimeError('�曆��啁��𧢲��硋��堆�'+str(root))
                    if machine is None:
                        machine = ContinuousShuffleMachine(state,key)
                    # Must run even when file metadata is unchanged: timed
                    # overflow mixing is work, not merely a cached read.
                    cache['snapshot'] = machine.maintenance_snapshot()
                    result['snapshot'] = cache['snapshot']
                except Exception as exc:
                    result['error'] = str(exc)
                # Error logs remain accessible when state cannot be read.
                try:
                    from collections import deque
                    log = state.with_name('CSM_Error.jsonl')
                    if log.exists():
                        info = log.stat(); stamp = (info.st_mtime_ns,info.st_size)
                        if stamp != cache['logstamp']:
                            records = []
                            with log.open(encoding='utf-8',errors='replace') as handle:
                                for line in deque(handle,maxlen=500):
                                    try:
                                        r=json.loads(line)
                                        if isinstance(r,dict): records.append(r)
                                    except ValueError:
                                        pass
                            cache.update(logs=records,logstamp=stamp)
                    result['logs'] = cache['logs']
                except OSError as exc:
                    result['log_error'] = str(exc)
            result['root'] = str(root)
            result['version'] = CSM_RELEASE
            self.send(200,json.dumps(result,ensure_ascii=False).encode('utf-8'))

    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads = True
    address = f'http://127.0.0.1:{server.server_port}/#'+token
    webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    selected = choose_root()
    if selected:
        serve(selected)