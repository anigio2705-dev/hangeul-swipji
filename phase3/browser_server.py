"""Test harness only: filesystem controlled clock. No HTTP clock-changing API."""
import argparse
from pathlib import Path
import server

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--clock-file',required=True);p.add_argument('--port',type=int,required=True);args=p.parse_args()
    clock=Path(args.clock_file)
    if not clock.is_file():raise SystemExit('Dedicated test clock file required')
    server.time.time=lambda:float(clock.read_text())
    server.init_db()
    app=server.ThreadingHTTPServer(('127.0.0.1',args.port),server.Handler);app.failures={}
    print('BROWSER TEST HARNESS ONLY',flush=True)
    app.serve_forever()
