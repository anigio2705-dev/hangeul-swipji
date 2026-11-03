"""Work-only loopback launcher; unmodified Team11 server, private SQLite."""
import json,os,sys,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'phase3'))
import server
server.init_db()
http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.failures={}
class Fault(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/disconnect':self.connection.close();return
        status=int(self.path.strip('/'));data=b'{"error":"Work injected HTTP failure"}'
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
fault=ThreadingHTTPServer(('127.0.0.1',0),Fault)
threading.Thread(target=fault.serve_forever,daemon=True).start()
print(json.dumps({'pid':os.getpid(),'port':http.server_port,'fault_port':fault.server_port,'scope':'WORK_LOCAL_ONLY'}),flush=True)
http.serve_forever()
