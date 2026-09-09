"""A signal-driven reveal film. Every displayed picture is decoder output."""
from pathlib import Path
import json,math,subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.io import wavfile
from scipy.signal import resample_poly
ROOT=Path(__file__).resolve().parents[1]
BG=(8,12,17);FG=(233,232,219);DIM=(139,157,166);GOLD=(222,190,120)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';MONO='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
def F(n,mono=False):return ImageFont.truetype(MONO if mono else FONT,n)
def ease(t):return .5-.5*math.cos(math.pi*np.clip(t,0,1))
def main():
 demo=ROOT/'demo';demo.mkdir(exist_ok=True)
 m=json.loads((ROOT/'output/manifest.json').read_text());planes={p['file']:p for p in m['planes']}
 chosen=['ch0-001.png','ch0-002.png','ch0-019.png','ch0-021.png','ch0-033.png','ch0-050.png','ch1-024.png','ch1-036.png']
 ims={p:Image.open(ROOT/'output'/p).convert('RGB') for p in ['ch0-000.png']+chosen}
 cover=Image.open(ROOT/'data/cover.jpg').convert('RGB').resize((670,670),Image.Resampling.LANCZOS)
 rate,source=wavfile.read(ROOT/'data/master.wav',mmap=True)
 W,H,FPS,DUR=1920,1080,30,64
 audio=np.zeros(DUR*48000,np.float32)
 schedule=[(10.,'ch0-000.png')]+[(20.+i*4.5,p) for i,p in enumerate(chosen)]
 for t,p in schedule:
  q=planes[p];clip=source[int(q['signal_start_s']*rate):int(q['signal_stop_s']*rate),q['channel']]
  a=resample_poly(clip,1,8).astype(np.float32);a*=.14/max(.001,float(np.max(np.abs(a))))
  fade=min(2400,len(a)//2);a[:fade]*=np.linspace(0,1,fade);a[-fade:]*=np.linspace(1,0,fade)
  off=int(t*48000);audio[off:off+len(a)]=a
 wavfile.write(demo/'signal-audio.wav',48000,audio)
 # A real line from the calibration waveform, plotted with its measured time axis.
 c=planes['ch0-000.png'];start=int(c['signal_start_s']*rate);wave=resample_poly(source[start:start+int(.00833*rate),0],1,8)
 signal=(wave-wave.mean())/(max(abs(wave-wave.mean()))+1e-12)
 proc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','30','-i','-','-i',str(demo/'signal-audio.wav'),'-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart','-shortest',str(demo/'sagan.mp4')],stdin=subprocess.PIPE)
 for n in range(DUR*FPS):
  t=n/FPS;im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
  d.text((72,42),'S A G A N',font=F(26),fill=FG);d.text((1320,46),'VOYAGER / SIGNAL RECOVERY',font=F(20,True),fill=DIM);d.line((72,96,1848,96),fill=(43,53,59))
  if t<4:
   a=ease(t/.8);d.text((105,300),'A picture, before pixels.',font=F(91),fill=tuple(int(x*a) for x in FG));d.text((112,475),'Decode the message engraved for another civilization.',font=F(31),fill=DIM)
   d.text((112,740),'ANALOG VOLTAGE   →   512 VERTICAL SCANS   →   AN IMAGE',font=F(24,True),fill=GOLD)
  elif t<10:
   im.paste(cover,(100,180));d=ImageDraw.Draw(im);d.text((850,192),'The decoder is on the cover.',font=F(47),fill=FG)
   d.text((850,296),'Read the raster instruction.',font=F(29),fill=DIM)
   d.text((850,354),'512 lines. About 8 ms per scan.',font=F(28),fill=GOLD)
   d.text((850,408),'Use the first circle to set the aspect ratio.',font=F(27),fill=DIM)
   pts=[(850+j/(len(signal)-1)*920,650-float(v)*85) for j,v in enumerate(signal)];d.line(pts,fill=GOLD,width=2)
   d.text((850,794),'ONE MEASURED SCAN / 48 kHz WORKING SIGNAL',font=F(20,True),fill=DIM)
  elif t<20:
   pic=ims['ch0-000.png'].resize((1040,round(1040*ims['ch0-000.png'].height/512)),Image.Resampling.LANCZOS)
   x,y=100,185;fraction=np.clip((t-10)/(c['signal_stop_s']-c['signal_start_s']),0,1);cut=int(pic.width*fraction)
   im.paste(pic.crop((0,0,cut,pic.height)),(x,y));d=ImageDraw.Draw(im)
   if fraction<1:d.line((x+cut,y,x+cut,y+pic.height),fill=GOLD,width=2)
   d.text((1240,230),'FIRST CONTACT',font=F(23,True),fill=GOLD)
   d.text((1240,312),'A circle.',font=F(65),fill=FG)
   d.text((1240,418),f'{min(512,int(512*fraction)):03d} / 512 scans',font=F(27,True),fill=DIM)
   for j,line in enumerate(['Signal-derived timing.','Circle-derived aspect.','No reference photograph.']):d.text((1240,555+j*52),line,font=F(26),fill=FG)
   d.text((100,944),'The reset clock and recording pedestal are estimated from this signal.',font=F(25),fill=DIM)
   if n==510:im.save(demo/'poster.png')
  elif t<56:
   index=min(7,int((t-20)/4.5));name=chosen[index];p=planes[name];local=t-(20+index*4.5)
   pic=ims[name];scale=1+.017*ease(local/4.5);w=int(1130*scale);h=round(w*pic.height/pic.width);pic=pic.resize((w,h),Image.Resampling.LANCZOS)
   # Only a presentation-scale camera move; source pixels are unretouched.
   x=100-int((w-1130)/2);y=175-int((h-1130*ims[name].height/512)/2);im.paste(pic,(x,y));d=ImageDraw.Draw(im)
   d.text((1310,205),'RECOVERED PLANE',font=F(23,True),fill=GOLD);d.text((1310,265),f'{index+1:02d} / 08',font=F(61),fill=FG)
   d.text((1310,397),f'CHANNEL {p["channel"]+1}',font=F(24,True),fill=DIM);d.text((1310,449),name.removesuffix('.png'),font=F(27,True),fill=FG)
   d.text((1310,555),f'{p["signal_start_s"]:.3f} s',font=F(29,True),fill=FG)
   d.text((1310,606),'source offset',font=F(22),fill=DIM)
   d.text((1310,715),'Analog artifacts retained.',font=F(24),fill=DIM)
   d.text((100,950),'Decoded voltage, displayed as grayscale. Signal audio plays at reduced gain.',font=F(24),fill=DIM)
  else:
   d.text((100,185),'From sound to sight.',font=F(77),fill=FG)
   for j,(large,small) in enumerate([(str(len(planes)),'RASTER PLANES'),('512','SCANS PER PLANE'),(str(m['source_channels']),'SIGNAL CHANNELS')]):
    x=110+j*600;d.text((x,385),large,font=F(91),fill=GOLD);d.text((x,512),small,font=F(23,True),fill=DIM)
   d.line((110,630,1810,630),fill=(43,53,59))
   for j,line in enumerate(['Independently written decoder. Public stereo preservation copy.','All recovered planes and calibration evidence are included.','Color assembly and restoration are not claimed.']):d.text((110,695+j*57),line,font=F(28),fill=FG if j<2 else DIM)
  d.text((72,1030),'1977 MESSAGE / REPRODUCIBLE RECOVERY',font=F(18,True),fill=DIM);d.line((0,1077,int(W*(n+1)/(DUR*FPS)),1077),fill=GOLD,width=3)
  proc.stdin.write(im.tobytes())
  if n%300==0:print('frame',n,flush=True)
 proc.stdin.close();assert proc.wait()==0
if __name__=='__main__':main()
