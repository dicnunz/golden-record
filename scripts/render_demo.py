"""Render saved raster planes; timing follows the recorded signal."""
from pathlib import Path
import json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, DURATION = 1920, 1080, 30, 64
CHOSEN = ['ch0-001.png', 'ch0-002.png', 'ch0-019.png', 'ch0-021.png',
          'ch0-033.png', 'ch0-050.png', 'ch1-024.png', 'ch1-036.png']

def font(size):
    for path in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 '/System/Library/Fonts/Helvetica.ttc']:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError('Install DejaVu Sans')

def caption(draw, position, text, size=26, fill='black'):
    draw.text(position, text, font=font(size), fill=fill)

def make_audio(manifest):
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    rate, source = wavfile.read(ROOT/'data/master.wav', mmap=True)
    planes = {p['file']: p for p in manifest['planes']}
    audio = np.zeros(DURATION*48000, np.float32)
    schedule = [(10., 'ch0-000.png')] + [(20.+i*4.5, p) for i,p in enumerate(CHOSEN)]
    for t, name in schedule:
        p = planes[name]
        clip = source[int(p['signal_start_s']*rate):int(p['signal_stop_s']*rate), p['channel']]
        a = resample_poly(clip, 1, 8).astype(np.float32)
        a *= .14/max(.001, float(np.max(np.abs(a))))
        fade = min(2400, len(a)//2)
        a[:fade] *= np.linspace(0,1,fade); a[-fade:] *= np.linspace(1,0,fade)
        offset = int(t*48000); audio[offset:offset+len(a)] = a
    wavfile.write(ROOT/'demo/signal-audio.wav', 48000, audio)

def frame(t, manifest, images, raw):
    im = Image.new('RGB', (W,H), 'white'); d = ImageDraw.Draw(im)
    if t < 10:
        caption(d,(100,76),'Voyager Golden Record',36)
        # Cover sequence: recorded signal, vertical scan, complete raster.
        wave = raw[:,0].astype(float); wave -= wave.mean()
        wave /= max(abs(wave).max(),1e-12)
        pts=[(120+i/len(wave)*760,445-float(v)*190) for i,v in enumerate(wave)]
        d.line(pts,fill='black',width=3)
        d.line((120,710,880,710),fill='black',width=2)
        for x,label in [(120,'0'),(880,f"{manifest['planes'][0]['median_line_ms']:.2f} ms")]:
            d.line((x,700,x,720),fill='black',width=2);caption(d,(x-15,735),label,24)
        caption(d,(120,845),'Recorded signal',28)
        x0,y0,x1,y1=1110,225,1770,710
        for k in range(0,65):
            x=x0+k*(x1-x0)/64
            d.line((x,y0,x,y1),fill='#cccccc',width=1)
        for k in range(3):
            x=x0+k*38
            d.line((x,y0,x,y1),fill='black',width=3)
            d.polygon([(x-6,y1-12),(x+6,y1-12),(x,y1)],fill='black')
            caption(d,(x-5,y0-44),str(k+1),22)
        d.rectangle((x0,y0,x1,y1),outline='black',width=2)
        caption(d,(1110,845),'512 vertical lines',28)
        caption(d,(100,1005),'Cover instruction / measured calibration scan',22)
    elif t < 56:
        name = 'ch0-000.png' if t < 20 else CHOSEN[min(7,int((t-20)/4.5))]
        p=next(p for p in manifest['planes'] if p['file']==name)
        pic=images[name].resize((1280,858),Image.Resampling.LANCZOS)
        x,y=320,62
        if t < 20:
            c=manifest['planes'][0]
            fraction=float(np.clip((t-10)/(c['signal_stop_s']-c['signal_start_s']),0,1))
            cut=int(pic.width*fraction)
            # Unreceived portion stays black; no generated intermediate pixels.
            d.rectangle((x,y,x+1279,y+857),fill='black')
            im.paste(pic.crop((0,0,cut,pic.height)),(x,y))
        else:im.paste(pic,(x,y))
        d=ImageDraw.Draw(im)
        caption(d,(320,958),'Calibration' if t<20 else f"Channel {p['channel']+1} / {name[4:7]}",28)
        caption(d,(1210,958),f"{p['signal_start_s']:.3f} s",26)
        if t<20:caption(d,(320,1008),'512 vertical lines',22)
    else:
        for k,name in enumerate(CHOSEN):
            pic=images[name].resize((400,268),Image.Resampling.LANCZOS)
            x=100+(k%4)*440;y=170+(k//4)*390
            im.paste(pic,(x,y));caption(d,(x,y+286),name.removesuffix('.png'),23)
        caption(d,(100,76),'Recovered raster planes',36)
        caption(d,(100,1005),'8 of 156 planes / grayscale / analog artifacts retained',24)
    return im

def contact_sheet():
    names = [f'ch0-{i:03d}.png' for i in range(20)]
    im = Image.new('RGB', (1280,1300), 'white');d=ImageDraw.Draw(im)
    for i,name in enumerate(names):
        pic=Image.open(ROOT/'output'/name)
        pic=pic.resize((304,round(pic.height*304/pic.width)),Image.Resampling.LANCZOS)
        x=8+i%4*320;y=16+i//4*260
        im.paste(pic,(x,y));caption(d,(x,y+pic.height+10),name.removesuffix('.png'),18)
    im.save(ROOT/'output/contact.png')

def main():
    manifest=json.loads((ROOT/'output/manifest.json').read_text())
    images={name:Image.open(ROOT/'output'/name).convert('RGB') for name in ['ch0-000.png']+CHOSEN}
    raw=np.load(ROOT/'output/calibration.npz')['raw_raster']
    demo=ROOT/'demo';demo.mkdir(exist_ok=True)
    if not (demo/'signal-audio.wav').exists():make_audio(manifest)
    frame(17,manifest,images,raw).save(demo/'poster.png')
    contact_sheet()
    cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r',str(FPS),'-i','-',
         '-i',str(demo/'signal-audio.wav'),'-c:v','libx264','-threads','4','-crf','18','-preset','fast','-pix_fmt','yuv420p',
         '-c:a','aac','-b:a','192k','-movflags','+faststart','-shortest',str(demo/'sagan.mp4')]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    try:
        for n in range(FPS*DURATION):proc.stdin.write(frame(n/FPS,manifest,images,raw).tobytes())
    finally:proc.stdin.close()
    if proc.wait():raise RuntimeError('FFmpeg failed')
if __name__=='__main__':main()
