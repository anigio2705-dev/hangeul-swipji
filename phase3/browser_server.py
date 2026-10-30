"""Test harness only: filesystem controlled clock. No HTTP clock-changing API."""
import argparse
import os
import ssl
from pathlib import Path
import server

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--clock-file',required=True);p.add_argument('--port',type=int,required=True)
    p.add_argument('--tls-cert');p.add_argument('--tls-key');args=p.parse_args()
    clock=Path(args.clock_file)
    if not clock.is_file():raise SystemExit('Dedicated test clock file required')
    server.time.time=lambda:float(clock.read_text())
    if args.tls_cert:
        import staging_server as staging
        settings=staging.Settings.from_env(os.environ)
        staging.prepare_database(settings)
        app=server.ThreadingHTTPServer(('127.0.0.1',args.port),staging.StagingHandler)
        app.staging=settings;app.secure_cookies=True
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(args.tls_cert,args.tls_key)
        app.socket=tls.wrap_socket(app.socket,server_side=True)
    else:
        server.init_db()
        app=server.ThreadingHTTPServer(('127.0.0.1',args.port),server.Handler)
    app.failures={}
    print('BROWSER TEST HARNESS ONLY',flush=True)
    app.serve_forever()
