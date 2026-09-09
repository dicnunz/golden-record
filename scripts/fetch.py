"""Fetch the uncompressed stereo preservation copy and NASA's engraved cover."""
from pathlib import Path
from urllib.request import urlopen,Request
from urllib.parse import urlencode
from html.parser import HTMLParser
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
FILE_ID='0B0Swx_1rwA6XX29wUGFwQlJNN00'
MASTER_SHA='05f8b49202133d399da3d84c19fee1df77e15056098ace452564a05a9a986b37'
COVER_SHA='eac79258cc229db4de1234afa4c8d64a158d287f8c6ee59e175535f0e86b5502'
COVER='https://science.nasa.gov/wp-content/uploads/2024/03/voyager-record-cover-446eb9.jpg'
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
class DownloadForm(HTMLParser):
 def __init__(self):super().__init__();self.action=None;self.values={}
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='form' and a.get('id')=='download-form':self.action=a.get('action')
  if tag=='input' and a.get('type')=='hidden':self.values[a['name']]=a.get('value','')
def main():
 data=ROOT/'data';data.mkdir(exist_ok=True);dest=data/'master.wav'
 if not dest.exists() or digest(dest)!=MASTER_SHA:
  print('Downloading 1.46 GB stereo WAV...',flush=True)
  response=urlopen(Request('https://drive.google.com/uc?export=download&id='+FILE_ID,headers={'User-Agent':'Mozilla/5.0'}),timeout=90)
  if 'text/html' in response.headers.get('Content-Type',''):
   form=DownloadForm();form.feed(response.read().decode());response.close()
   if not form.action or not form.action.startswith('https://drive.usercontent.google.com/'):
    raise RuntimeError('Public download form changed; inspect the source URL before proceeding.')
   response=urlopen(form.action+'?'+urlencode(form.values),timeout=120)
  partial=dest.with_suffix('.partial')
  with response,open(partial,'wb') as f:shutil.copyfileobj(response,f,1048576)
  if digest(partial)!=MASTER_SHA:raise RuntimeError('Source digest differs; partial download retained for inspection.')
  partial.replace(dest)
 if not (data/'cover.jpg').exists():
  with urlopen(COVER,timeout=60) as r:payload=r.read()
  if hashlib.sha256(payload).hexdigest()!=COVER_SHA:raise RuntimeError('Cover download digest differs.')
  (data/'cover.jpg').write_bytes(payload)
 if digest(data/'cover.jpg')!=COVER_SHA:raise RuntimeError('Existing cover digest differs.')
 (data/'provenance.json').write_text(json.dumps({'master':{'name':'384kHzStereo.wav','url':'https://drive.google.com/file/d/'+FILE_ID+'/view','sha256':digest(dest),'bytes':dest.stat().st_size,'provenance_limit':'Public community-shared preservation copy; not a NASA-hosted authenticated original disc capture.'},'cover':{'url':COVER,'sha256':digest(data/'cover.jpg')}},indent=2)+'\n')
 print('Verified source and engraved cover.')
if __name__=='__main__':main()
