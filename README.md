# Sagan

Recover pictures from a digitized Voyager Golden Record waveform using the engraved raster instructions, then watch the signal turn into an image.

[Watch the 64-second reveal](demo/sagan.mp4) · [All decoded planes](output/) · [Signal provenance](data/provenance.json)

![The calibration circle recovered from voltage](demo/poster.png)

The decoder extracts **156 grayscale raster planes**, 78 from each stereo channel. The first circle sets the display aspect ratio. No downloaded reference photograph, existing decoder implementation, image generator or hand-painted repair supplies the output pixels. Analog banding, timing errors and incomplete photographic detail remain visible.

## Run

Python 3.12, FFmpeg/ffprobe and DejaVu Sans fonts are required. The source WAV download is 1.46 GB; allow roughly 4 GB of free memory and several minutes for decoding and rendering on a CPU.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch.py
python scripts/decode.py
python scripts/render_demo.py
python scripts/verify.py
```

The fetcher checks the full SHA-256 digest and handles the public download confirmation form. It never silently accepts a changed source. The large waveform is downloaded rather than committed. Results, the calibration arrays, the movie and their provenance are included.

## The experiment

The [engraved cover](https://science.nasa.gov/mission/voyager/golden-record-cover/) supplies the essential reconstruction constraints: vertical scans, 512 lines, an approximately eight-millisecond scan, and a calibration circle. The [NASA image description](https://science.nasa.gov/mission/voyager/golden-record-contents/images/) confirms that the pictures are analog encoded.

The implementation estimates the acquisition parameters from the signal:

| Stage | Operation |
|---|---|
| Working signal | Polyphase downsampling from 384 kHz stereo to 48 kHz per channel |
| Frame detection | Find the short oscillatory preambles using 1.5–5 kHz band energy |
| Scan clock | Fit a clock to reset pulses in the first calibration frame, then refine each frame and each reset locally |
| Raster | Interpolate 400 samples along each of 512 vertical scans |
| Recording response | Fit an exponential to blank calibration columns; apply the corresponding first-order inverse AC-coupling model |
| Black level | Remove the initial reset level and a shared calibration-derived recording pedestal |
| Geometry | Fit the calibration ellipse and choose a common height that makes its axes equal |
| Display | Retain the first 320 samples, excluding the observed flyback; apply a per-plane 1st–99th-percentile grayscale stretch |

The measured inverse-response time constant is about 76 working samples. The fitted line periods are close to 8.33 ms. `output/manifest.json` records each plane's channel, exact source interval, scan timing and contrast limits. `output/calibration.npz` preserves the untouched sampled raster, fitted response, reset locations and corrected raster. The display height is 343 pixels for a 512-column image, derived from this recording's circle rather than assumed to be 4:3.

These are **raster planes**, not 156 distinct photographs. Color photographs can occupy several planes. The project does not claim a verified assembly of every photograph or its color channels. The eight-plane montage deliberately uses readable examples; every other recovered plane is available for inspection. Some retain severe analog artifacts. The shared response model is approximate, and the timing tracker can follow picture structure when synchronization is weak.

## Evidence

`verify.py` checks the source digest, every output's dimensions and timing, and the calibration's direct numerical correspondence to the waveform. It reruns scan extraction for both channels and requires exact pixel equality for every one of the 156 saved PNGs, recording their hashes in the verification report. It independently generates a known disk raster and analog-style synchronization signal, then measures recovery correlation above 0.97. It also measures the recovered circle's axis ratio and requires a complete error-free decode of the 1080p movie with its audio track. Exact source correspondence and synthetic controls do not establish photographic fidelity or restore missing detail.

Verification also reconstructs the edited soundtrack from the pinned waveform, compares its saved samples exactly, and checks correlation after AAC encoding. The reveal plays the circle in source time. Later scenes show already decoded planes with small presentation-scale camera moves. Their audio comes from the corresponding source interval at its original speed, reduced in gain and faded at edit boundaries. There is no invented spacecraft sound or generated visual content.

## Provenance and limits

The input is the publicly shared **384kHzStereo.wav** preservation copy in [this source folder](https://drive.google.com/drive/folders/0B0Swx_1rwA6XcFFLc29ncFJSZmM). It is an uncompressed waveform, not a NASA-hosted, authenticated capture of the flight record. The exact bytes are pinned in `data/provenance.json`; chain of custody before that public copy is not established here. The engraved-cover image is fetched directly from NASA.

Public search was used to locate the signal and encountered prior decoding discussions. This is an independently written implementation, **not a controlled blind test** of a researcher who has never encountered the subject. The reconstruction uses the cover's constraints and signal measurements; reference photographs and existing decoder code were not used to generate or tune its outputs.

Original Sagan code and presentation graphics are MIT-licensed. The waveform, cover and recovered photographs retain their original rights; the code license does not relicense them. See [data notices](DATA-NOTICE.md). The project name acknowledges Carl Sagan and does not imply NASA endorsement.
