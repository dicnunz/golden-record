# Decoding

| Step | Implementation |
|---|---|
| Sampling | 384 kHz stereo to 48 kHz per channel, polyphase resampling |
| Frame detection | 1.5–5 kHz preamble band energy |
| Synchronization | Calibration reset clock, then per-frame and per-line refinement |
| Raster | 400 samples along each of 512 vertical scans |
| Recording response | Inverse first-order AC-coupling model, fitted to blank calibration columns |
| Black level | Reset-level and shared calibration-pedestal subtraction |
| Geometry | Calibration ellipse determines the display aspect ratio |
| Display | First 320 samples; per-plane 1st–99th-percentile stretch |

The fitted scan period is approximately 8.33 ms. The inverse-response time constant is approximately 76 working samples. Output dimensions are 512 × 343 pixels.

[Calibration arrays](../output/calibration.npz) retain raw samples, resets, response and corrected raster. The [manifest](../output/manifest.json) identifies each plane's channel, source interval, timing and contrast limits. The response model is approximate; synchronization can follow image structure where reset pulses are weak.

## Verification

`verify.py` checks the source digest, reconstructs all 156 saved planes and requires exact pixel equality. It also tests a synthetic disk raster, measures the calibration circle and checks soundtrack correspondence and full video decoding. The included [report](../output/verification.json) records the original run. These checks establish source correspondence and computational consistency; photographic fidelity remains unmeasured.

## Video

The opening pairs a measured calibration scan with the vertical raster specified by the [engraved cover](https://science.nasa.gov/mission/voyager/golden-record-cover/). The circle reveal follows its source interval. Subsequent planes remain stationary at a common size. Captions contain plane identifiers and source times.

The 64-second soundtrack uses the corresponding source intervals at original speed, reduced gain and short boundary fades. `render_demo.py` uses the included soundtrack; if absent, it rebuilds it from the pinned master recording.
