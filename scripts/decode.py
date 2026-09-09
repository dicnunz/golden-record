"""Recover raster planes from the digitized analog signal; no reference images."""
from pathlib import Path
import json,hashlib
import cv2
import numpy as np
from scipy.io import wavfile
from scipy.optimize import curve_fit
from scipy.signal import resample_poly,butter,sosfiltfilt,find_peaks
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
def extract(s,rate,measured_clock=None):
 # Engraved preamble: a short oscillatory burst, followed by vertical scans.
 band=sosfiltfilt(butter(3,[1500,5000],fs=rate,btype='bandpass',output='sos'),s)
 block=rate//100;n=len(s)//block;env=np.sqrt((band[:n*block].reshape(n,block)**2).mean(1))
 marks,_=find_peaks(env,height=.035,prominence=.025,distance=420)
 # The cover specifies ~8 ms; the observed synchronization has two alternating intervals.
 resets,_=find_peaks(-s,distance=int(rate*.0077),prominence=.07)
 frames=[];rejected=[]
 for marker in marks:
  end=marker
  while end+1<len(env) and env[end+1]>.55*env[marker]:end+=1
  start=(end+1)*block;j=np.searchsorted(resets,start)
  if j>=len(resets):continue
  if resets[j]+512*rate*.0086+60>=len(s):
   rejected.append(float(start/rate));continue
  # Fit a frame-wide clock before local phase correction. This prevents a dark
  # picture feature from dragging a free-running sync tracker into the image.
  k=np.arange(512)
  if measured_clock is None:
   measured_clock=float(np.polyfit(k[10:-10],resets[j:j+512][10:-10],1)[0])
  clock=measured_clock;origin=float(resets[j])
  for iteration in range(5):
   predicted=origin+k*clock
   width=60 if iteration==0 else (24 if iteration==1 else 10)
   observed=np.array([int(t)-width+int(np.argmin(s[int(t)-width:int(t)+width+1])) for t in predicted])
   error=observed-predicted;center=np.median(error)
   keep=np.abs(error-center)<max(3,2*np.median(np.abs(error-center)))
   clock,origin=np.polyfit(k[keep],observed[keep],1)
  predicted=origin+k*clock
  p=np.array([int(t)-24+int(np.argmin(s[int(t)-24:int(t)+25])) for t in predicted])
  p=np.asarray(p)
  if len(p)!=512:
   rejected.append(float(start/rate));continue
  period=float(np.median(np.diff(p)))
  indices=p[:,None]+np.linspace(0,period,400,endpoint=False)[None,:]
  z=np.interp(indices,np.arange(len(s)),s).T
  frames.append((p,z,period))
 return frames,rejected,measured_clock

def main():
 out=ROOT/'output';out.mkdir(exist_ok=True);rate,source=wavfile.read(ROOT/'data/master.wav',mmap=True)
 manifest=[];rejections={};pedestal=None;preview=[];display_height=None;circle_measurement=None;measured_clock=None;recovery_tau=None
 for channel in range(source.shape[1]):
  s=resample_poly(source[:,channel],1,8).astype('float64');sr=rate//8
  frames,bad,measured_clock=extract(s,sr,measured_clock);rejections[str(channel)]=bad
  for i,(p,z,period) in enumerate(frames):
   raw=z.copy()
   if recovery_tau is None:
    blank=np.median(raw[:,np.r_[20:65,460:500]],axis=1)
    # A first-order inverse AC-coupling model, fitted only to blank calibration columns.
    fit,_=curve_fit(lambda x,a,t,b:a*np.exp(-x/t)+b,np.arange(320),blank[:320],p0=[-.14,80,.02],bounds=([-.5,10,-.2],[0,500,.2]))
    recovery_tau=float(fit[1])
   z=z+np.cumsum(z,axis=0)/recovery_tau
   z-=z[:3].mean(0)
   if pedestal is None:
    # Blank outer columns of the cover's calibration circle estimate recording pedestal.
    pedestal=np.median(z[:,np.r_[20:65,460:500]],axis=1)
   z-=pedestal[:,None]
   # Reset and flyback occupy the bottom of the measured raster. Retain originals separately.
   active=z[:320];lo,hi=np.percentile(active,[1,99]);img=np.uint8(np.clip((active-lo)/(hi-lo),0,1)*255)
   if display_height is None:
    yy,xx=np.where((img>220)&(np.indices(img.shape)[1]>70)&(np.indices(img.shape)[1]<430))
    # The engraved circle provides the aspect-ratio constraint, independently of photographs.
    ellipse=cv2.fitEllipse(np.stack([xx,yy],1).astype('float32'))
    mask=np.zeros(img.shape,dtype=np.uint8);cv2.ellipse(mask,ellipse,255,1)
    ey,ex=np.where(mask>0);display_height=int(round(img.shape[0]*(ex.max()-ex.min())/(ey.max()-ey.min())))
    circle_measurement={'ellipse_center':ellipse[0],'ellipse_axes':ellipse[1],'ellipse_angle':ellipse[2],'display_height':display_height}
   name=f'ch{channel}-{i:03d}.png';Image.fromarray(img).resize((512,display_height),Image.Resampling.LANCZOS).save(out/name)
   if channel==0 and i<20:preview.append(Image.open(out/name))
   manifest.append({'file':name,'channel':channel,'signal_start_s':float(p[0]/sr),'signal_stop_s':float((p[-1]+period)/sr),'lines':512,'median_line_ms':period/sr*1000,'max_line_interval_ms':float(np.max(np.diff(p))/sr*1000),'contrast_percentiles':[float(lo),float(hi)],'fitted_line_period_ms':float(np.polyfit(np.arange(512),p,1)[0]/sr*1000),'resets_sha256':hashlib.sha256(p.astype('<i8').tobytes()).hexdigest()})
   if channel==0 and i==0:
    np.savez_compressed(out/'calibration.npz',raw_raster=raw,corrected_raster=z,resets=p,rate=sr,pedestal=pedestal,inverse_ac_tau=recovery_tau)
  print('channel',channel,'planes',len(frames),'rejected',len(bad),flush=True)
 (out/'manifest.json').write_text(json.dumps({'source_sha256':sha(ROOT/'data/master.wav'),'sample_rate':int(rate),'source_channels':source.shape[1],'calibration_circle':circle_measurement,'inverse_ac_time_constant_samples':recovery_tau,'planes':manifest,'rejected_preambles':rejections,'scope':'Grayscale raster planes, not a claimed assembly of all 116 photographs or their RGB channels.'},indent=2))
 from render_demo import contact_sheet
 contact_sheet()

def math_ceil(x):return int(np.ceil(x))
if __name__=='__main__':main()
