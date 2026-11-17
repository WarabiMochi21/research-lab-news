import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen

def deliver(url,payload,image,report):
    boundary='ResearchLab'+uuid.uuid4().hex
    payload=dict(payload,attachments=[{'id':0,'filename':'poster.jpg'},{'id':1,'filename':'research-report.txt'}])
    parts=[]
    def add(name,data,mime,filename=None):
        header=f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
        if filename: header+=f'; filename="{filename}"'
        parts.extend([(header+f'\r\nContent-Type: {mime}\r\n\r\n').encode(),data,b'\r\n'])
    add('payload_json',json.dumps(payload).encode(),'application/json')
    add('files[0]',Path(image).read_bytes(),'image/jpeg','poster.jpg')
    add('files[1]',report.encode('utf-8'),'text/plain; charset=utf-8','research-report.txt')
    parts.append(f'--{boundary}--\r\n'.encode())
    parsed=urlsplit(url)
    query=dict(parse_qsl(parsed.query));query['wait']='true'
    url=urlunsplit(parsed._replace(query=urlencode(query)))
    req=Request(url,data=b''.join(parts),headers={'Content-Type':'multipart/form-data; boundary='+boundary,'User-Agent':'ResearchLabEditorial/2.0'})
    with urlopen(req,timeout=35) as response: receipt=json.loads(response.read(1000000))
    if not str(receipt.get('id','')).isdigit(): raise ValueError('Discord receipt missing')
    return str(receipt['id'])
