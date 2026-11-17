"""Bounded diagnostics; never print credentials or raw API responses."""
import json,os,re
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError,URLError

BASE='https://generativelanguage.googleapis.com/v1beta/'

def call(path,key,payload=None):
    req=Request(BASE+path,data=None if payload is None else json.dumps(payload).encode(),headers={'x-goog-api-key':key,'Content-Type':'application/json'})
    try:
        with urlopen(req,timeout=35) as r: return r.status,json.loads(r.read(2000000))
    except HTTPError as e:
        try: body=json.loads(e.read(100000))
        except Exception: body={}
        return e.code,body
    except (URLError,TimeoutError): return 0,{}

def diagnostic(status,data):
    names={0:'NETWORK_ERROR',400:'REQUEST_REJECTED',401:'AUTHENTICATION_FAILED',403:'ACCESS_DENIED',404:'NOT_FOUND',429:'RATE_OR_QUOTA_LIMIT',503:'SERVICE_UNAVAILABLE'}
    info={'http':status,'result':names.get(status,'API_ERROR')}
    error=data.get('error',{})
    if re.fullmatch('[A-Z_]+',str(error.get('status',''))):info['api_status']=error['status']
    # Quota names distinguish per-minute from per-day constraints without printing project data.
    quotas=[]
    for detail in error.get('details',[]):
        for violation in detail.get('violations',[]):
            name=violation.get('quotaId','')
            if re.fullmatch('[A-Za-z0-9_./-]{1,180}',name):quotas.append(name)
        delay=detail.get('retryDelay')
        if isinstance(delay,str) and re.fullmatch(r'[0-9.]+s',delay):info['retry_delay']=delay
    if quotas:info['quota_names']=quotas
    return info

def main():
    key=os.environ.get('GEMINI_API_KEY','')
    if not key:raise SystemExit('Missing GEMINI_API_KEY secret')
    models=[];token='';complete=False
    for _ in range(5):
        query={'pageSize':100}
        if token:query['pageToken']=token
        status,data=call('models?'+urlencode(query),key)
        if status!=200:
            print('MODEL_LIST',json.dumps(diagnostic(status,data)));return
        for model in data.get('models',[]):
            name=model.get('name','').removeprefix('models/')
            if re.fullmatch(r'[A-Za-z0-9._-]+',name) and 'generateContent' in model.get('supportedGenerationMethods',[]):
                models.append(name)
        token=data.get('nextPageToken','')
        if not token:complete=True;break
    print('LIST_COMPLETE',complete)
    print('GENERATE_CONTENT_MODELS',json.dumps(models))
    primary=os.environ.get('GEMINI_MODEL','')
    candidates=[]
    if re.fullmatch(r'[A-Za-z0-9._-]+',primary):candidates.append(primary)
    for name in sorted(models,reverse=True):
        if name.startswith('gemini-') and 'flash' in name and not any(x in name for x in ('image','tts','audio','live','robot','computer')) and name not in candidates:
            candidates.append(name)
    passed=[]
    for name in candidates[:4]:
        payload={'contents':[{'parts':[{'text':'Return only the JSON object {"ok":true}.'}]}],
                 'generationConfig':{'maxOutputTokens':1024,'responseMimeType':'application/json'}}
        status,data=call('models/'+name+':generateContent',key,payload)
        if status!=200:
            print('PROBE',name,json.dumps(diagnostic(status,data)));continue
        cs=data.get('candidates',[])
        text=''.join(x.get('text','') for x in (cs[0].get('content',{}).get('parts',[]) if cs else []) if not x.get('thought'))
        try:valid=bool(cs and cs[0].get('finishReason')=='STOP' and json.loads(text)=={'ok':True})
        except Exception:valid=False
        print('PROBE',name,'JSON_OK' if valid else 'RESPONSE_NOT_VALID_JSON')
        if valid:passed.append(name)
    print('WORKING_MODELS_THIS_CHECK',json.dumps(passed))
    print('A passed small probe does not guarantee daily quota or long-report reliability. No settings changed.')

if __name__=='__main__':main()
