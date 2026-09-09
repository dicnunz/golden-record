"""Check signal provenance, a known synthetic raster, real calibration, and movie integrity."""
from pathlib import Path
import json,hashlib,subprocess,tempfile
import numpy as np
from PIL import Image
import cv2
from scipy.io import wavfile
from scipy.signal import resample_poly
from decode import extract,sha
ROOT=Path(__file__).resolve().parents[1]
def synthetic_control():
 rate=48000;period=400;columns=512
 yy,xx=np.indices((period,columns));known=((xx-256)**2+(yy-160)**2<100**2).astype(float)
 signal=np.zeros(6*rate);time=np.arange(4800)/rate;signal[24000:28800]=.2*np.sin(2*np.pi*2500*time)
 start=30000
 for col in range(columns):
  line=np.zeros(period);line[:8]=-.25;line[12:320]=.1*known[12:320,col];line[350:380]=.15
  signal[start+col*period:start+(col+1)*period]=line
 signal+=np.random.default_rng(732).normal(0,.0001,len(signal))
 frames,bad,clock=extract(signal,rate)
 assert len(frames)==1,(len(frames),bad)
 p,z,_=frames[0];assert abs(clock-period)<.1
 # Match the recovered shape to the independently generated disk, allowing a
 # small synchronization-pulse phase offset; no fixture image enters real decoding.
 best=max(np.corrcoef(z[20:300].ravel(),np.roll(known,shift,axis=0)[20:300].ravel())[0,1] for shift in range(-8,9))
 assert best>.97,best
 return float(best)
def verify_planes(source, source_rate, manifest, calibration, first_signal):
    """Recompute all saved image pixels from the waveform, never from PNGs."""
    clock=None
    digests={}
    sr=source_rate//8
    for channel in range(source.shape[1]):
        signal=first_signal if channel==0 else resample_poly(source[:,channel],1,8).astype('float64')
        frames,rejected,clock=extract(signal,sr,clock)
        records=[p for p in manifest['planes'] if p['channel']==channel]
        assert len(frames)==len(records)==78
        assert rejected==manifest['rejected_preambles'][str(channel)]
        for (resets,raw,period),record in zip(frames,records):
            assert hashlib.sha256(resets.astype('<i8').tobytes()).hexdigest()==record['resets_sha256']
            np.testing.assert_allclose([resets[0]/sr,(resets[-1]+period)/sr],
                                       [record['signal_start_s'],record['signal_stop_s']],rtol=0,atol=1e-12)
            corrected=raw+np.cumsum(raw,axis=0)/float(calibration['inverse_ac_tau'])
            corrected-=corrected[:3].mean(0)
            corrected-=calibration['pedestal'][:,None]
            lo,hi=np.percentile(corrected[:320],[1,99])
            np.testing.assert_allclose([lo,hi],record['contrast_percentiles'],rtol=1e-10,atol=1e-12)
            pixels=np.uint8(np.clip((corrected[:320]-lo)/(hi-lo),0,1)*255)
            expected=np.asarray(Image.fromarray(pixels).resize((512,manifest['calibration_circle']['display_height']),Image.Resampling.LANCZOS))
            path=ROOT/'output'/record['file']
            np.testing.assert_array_equal(expected,np.asarray(Image.open(path)),err_msg=record['file'])
            digests[record['file']]=sha(path)
        del frames
        print(f'Verified channel {channel}: all {len(records)} PNGs match source-derived pixels',flush=True)
    return digests


def verify_audio(source, source_rate, manifest):
    records={p['file']:p for p in manifest['planes']}
    chosen=['ch0-001.png','ch0-002.png','ch0-019.png','ch0-021.png','ch0-033.png','ch0-050.png','ch1-024.png','ch1-036.png']
    schedule=[(10.,'ch0-000.png')]+[(20.+i*4.5,p) for i,p in enumerate(chosen)]
    expected=np.zeros(64*48000,np.float32)
    for time,name in schedule:
        p=records[name]
        clip=source[int(p['signal_start_s']*source_rate):int(p['signal_stop_s']*source_rate),p['channel']]
        audio=resample_poly(clip,1,8).astype(np.float32)
        gain=.14/max(.001,float(np.max(np.abs(audio))))
        assert gain<1, 'Reduced-gain caption must agree with actual signal gain'
        audio*=gain
        fade=min(2400,len(audio)//2)
        audio[:fade]*=np.linspace(0,1,fade);audio[-fade:]*=np.linspace(1,0,fade)
        offset=int(time*48000);expected[offset:offset+len(audio)]=audio
    rate,saved=wavfile.read(ROOT/'demo/signal-audio.wav')
    assert rate==48000
    np.testing.assert_array_equal(saved,expected)
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'audio.f32'
        subprocess.run(['ffmpeg','-v','error','-i',str(ROOT/'demo/sagan.mp4'),'-vn','-ac','1','-ar','48000','-f','f32le',str(path)],check=True)
        encoded=np.fromfile(path,dtype='<f4')
        assert abs(len(encoded)-len(expected))<2048
        n=min(len(encoded),len(expected))
        correlation=float(np.corrcoef(encoded[:n],expected[:n])[0,1])
        assert correlation>.98, correlation
    return correlation


def main():
 m=json.loads((ROOT/'output/manifest.json').read_text());pro=json.loads((ROOT/'data/provenance.json').read_text())
 assert sha(ROOT/'data/master.wav')==m['source_sha256']==pro['master']['sha256']
 assert sha(ROOT/'data/cover.jpg')==pro['cover']['sha256']=='eac79258cc229db4de1234afa4c8d64a158d287f8c6ee59e175535f0e86b5502'
 r,x=wavfile.read(ROOT/'data/master.wav',mmap=True);assert r==384000 and x.shape[1]==2 and np.isfinite(x).all()
 assert len(m['planes'])==156 and len(set(p['file'] for p in m['planes']))==156
 for p in m['planes']:
  assert p['lines']==512 and 8<p['fitted_line_period_ms']<8.6
  assert 0<p['signal_start_s']<p['signal_stop_s']<len(x)/r
  im=Image.open(ROOT/'output'/p['file']);assert im.size==(512,m['calibration_circle']['display_height']) and np.asarray(im).std()>3
 cal=np.load(ROOT/'output/calibration.npz');p=cal['resets'];raw=cal['raw_raster'];rate=int(cal['rate']);s=resample_poly(x[:,0],1,8).astype('float64')
 positions=p[:,None]+np.linspace(0,np.median(np.diff(p)),400,endpoint=False)[None,:]
 measured=np.interp(positions,np.arange(len(s)),s).T
 assert np.max(abs(measured-raw))<1e-7,'Calibration is not sourced from the WAV'
 corrected=raw+np.cumsum(raw,axis=0)/float(cal['inverse_ac_tau']);corrected-=corrected[:3].mean(0);corrected-=cal['pedestal'][:,None]
 assert np.allclose(corrected,cal['corrected_raster'],atol=1e-9)
 image=np.asarray(Image.open(ROOT/'output/ch0-000.png'));y,c=np.where((image>220)&(np.indices(image.shape)[1]>70)&(np.indices(image.shape)[1]<430));ellipse=cv2.fitEllipse(np.stack([c,y],1).astype('float32'));ratio=max(ellipse[1])/min(ellipse[1]);assert ratio<1.025,ratio
 control=synthetic_control()
 plane_digests=verify_planes(x,r,m,cal,s)
 movie=ROOT/'demo/sagan.mp4';assert movie.is_file()
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]));v=next(s for s in probe['streams'] if s['codec_type']=='video');assert (v['width'],v['height'])==(1920,1080) and abs(float(probe['format']['duration'])-64)<.2
 assert any(s['codec_type']=='audio' for s in probe['streams'])
 subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(movie),'-f','null','-'],check=True)
 audio_correlation=verify_audio(x,r,m)
 report={'source_audio_aac_correlation':audio_correlation,'source_sha256':m['source_sha256'],'planes':len(m['planes']),'circle_axis_ratio':float(ratio),'synthetic_raster_correlation':control,'calibration_source_max_error':float(np.max(abs(measured-raw))),'all_plane_source_pixels':'exact match for all 156 PNGs','plane_sha256':plane_digests,'video_full_decode':'passed','limits':'Calibration and synthetic control do not establish perfect recovery of every photographic plane.'}
 (ROOT/'output/verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
