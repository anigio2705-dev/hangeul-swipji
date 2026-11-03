"""Optional isolated Supabase Auth verification. Never targets the existing project."""
import json
import os
import re
import uuid
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

PRODUCTION_REF='itljmzmhpviasopdmdfs'
class AuthError(Exception): pass
class NotConfigured(AuthError): pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise AuthError('인증 API 리디렉션 거부')
def settings():
    ref=os.environ.get('HS_SUPABASE_TEST_PROJECT_REF','')
    key=os.environ.get('HS_SUPABASE_TEST_PUBLISHABLE_KEY','')
    if not ref or not key: raise NotConfigured('별도 Supabase 테스트 프로젝트가 설정되지 않았습니다')
    if not re.fullmatch('[a-z]{20}',ref) or ref==PRODUCTION_REF: raise AuthError('운영 프로젝트 또는 잘못된 프로젝트를 거부했습니다')
    if not re.fullmatch('sb_publishable_[A-Za-z0-9_-]{10,}',key): raise AuthError('공개 테스트 프로젝트 키만 허용합니다')
    if os.environ.get('HS_SUPABASE_TEST_ONLY')!='yes': raise AuthError('테스트 전용 프로젝트 명시가 필요합니다')
    return 'https://'+ref+'.supabase.co',key,ref

def configured():
    try: settings();return True
    except AuthError:return False

def transport(request):
    try:
        with build_opener(NoRedirect).open(request,timeout=10) as response:return response.read(65537)
    except (HTTPError,URLError,TimeoutError,OSError):raise AuthError('Supabase 테스트 인증을 확인하지 못했습니다') from None

def verify_user(token,request_fn=None):
    url,key,ref=settings()
    if not isinstance(token,str) or not 40<=len(token)<=16000 or re.search(r'\s',token):raise AuthError('유효한 테스트 세션 토큰이 필요합니다')
    raw=(request_fn or transport)(Request(url+'/auth/v1/user',headers={'apikey':key,'Authorization':'Bearer '+token}))
    if not isinstance(raw,bytes) or len(raw)>65536:raise AuthError('인증 응답 크기 오류')
    try:
        u=json.loads(raw)
        if not isinstance(u,dict):raise ValueError()
        subject=str(uuid.UUID(u.get('id','')))
        email=u.get('email','')
        if u.get('is_anonymous') is not False or not u.get('email_confirmed_at') or not isinstance(email,str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError()
        if u.get('aud')!='authenticated' or u.get('role')!='authenticated':raise ValueError()
    except (ValueError,TypeError,AttributeError):raise AuthError('확인된 비익명 테스트 사용자만 연결할 수 있습니다') from None
    # user_metadata and app_metadata roles are deliberately ignored, not trusted for local admin.
    return {'subject':subject,'email':email.lower(),'projectRef':ref}
