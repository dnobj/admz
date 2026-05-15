---
title: Imaging API
url: "https://developer.axis.com/vapix/network-video/imaging-api/"
category: vapix
subcategory: network-video
sha256: 118d4b53fd989f3f9d44a59a28469b087fe1dbe504aa66b002cb207513c83730
scraped_at: "2026-01-09T15:20:01.380Z"
page_height: 15197
---

# Imaging API

## Description

The AXIS Imaging API makes it possible to use parameters for `CCD/CMOS` image sources. This parameter group is product dependent and only available in network cameras. The first step should therefore always be to check for product specific parameters, as well as default and valid values.

### Identification

-   **Property**: `ImageSource.I0.Sensor.parameters`
-   **AXIS OS**: 5.00 or higer

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## API specification
### ImageSource.I0.Sensor parameters

`ImageSource.I0.Sensor` parameters are defined for 1 channel cameras, however, these parameters can be used in modular cameras by extending for other channels as well.

| Parameter | Default values | Valid values | Security level (get/set) | Description |
| --- | --- | --- | --- | --- |
| `BacklightCompensation` | yes | yes no | admin: r/w operator: r/w | Makes darker objects in the foreground appear clearer if the background is very bright, but has no effect if Dynamic Contrast is enabled or Exposure Window is not set to auto. |
| `BlueBalance` | 50 | 0...100 | admin: r/w operator: r/w | Fine-tune blue gain for the manual white balance mode. |
| `Brightness` | 50 | 0...100 | admin: r/w operator: r/w | The image brightness. |
| `ColorDesaturation` | 100 | 0...100 | admin: r/w operator: r/w | Controls the de-saturation of colors in low light. **100**: All colors are de-saturated **0**: No color is de-saturated. |
| `ColorLevel` | 50 | 0...100 | admin: r/w operator: r/w | The level of color saturation in the image. |
| `Contrast` | 50 | 0...100 | admin: r/w operator: r/w | The image contrast. |
| `CoordX` | 5000 | 0...9999 | admin: r/w operator: r/w | X coordinate for the manual white balance mode. |
| `CoordY` | 5000 | 0...9999 | admin: r/w operator: r/w | Y coordinate for the manual white balance mode. |
| `DynamicContrastEnabled` | Product dependent | yes no | admin: r/w operator: r/w | If enabled, visibility may increase in scenes with a high dynamic range. This is not available on all cameras. |
| `DynamicContrastLevel` | 50 | 0...100 | admin: r/w operator: r/w | A high value means that visibility in bright parts of the image is prioritized, while a low value means that visibility in dark parts are prioritized. This is not available on all cameras. |
| `Exposure` | auto | auto flickerfree50, flickerfree60, hold | admin: r/w operator: r/w | A type of exposure control. The flicker-free modes avoid flicker while the hold mode keeps the exposure regardless of changes in lightning. |
| `ExposureValue` | 50 | 0...100 | admin: r/w operator: r/w | Exposure value of the image. |
| `ExposurePriority` | 50 | 0 50 100 | admin: r/w operator: r/w | The balance between low noise and the camera’s motion. Prioritizes low noise to reduce frame rate and increase motion blur. Prioritizing motion prior may increase the image noise. **50**: None. **100**: Prioritize motion. **0**: Prioritize low noise. |
| `ExposureResponsiveness` | 50 | 0...100 | admin: r/w operator: r/w | Balances how fast the exposure should be (including tone mapping). A higher value will result in a faster control to handle rapid scene changes while a lower value will result in a more stable control. |
| `ExposureWindow` | auto | auto right left upper lower spot custom (only on some cameras) | admin: r/w operator: r/w | Defines which part of the image that should have the biggest influence over the auto exposure. |
| `MaxExposureTime` | Camera dependent | Camera dependent (but always in the interval \[-60, ..., 2 000 000\]) | admin: r/w operator: r/w | Maximum allowed shutter integration time. If the value is negative it represents the number of frames of the frame rate that the hardware can generate. E.g. if the hardware generates 30 fps then -5 gives a maximum exposure time of 5/30s = 167 ms. If the value is positive then it represents a number of micro seconds. E.g. the value 1 000 000 represents 1s. |
| `MinExposureTime` | Camera dependent | Camera dependent (but always in the interval \[-60, ..., 2 000 000\]) | admin: r/w operator: r/w | Minimum allowed shutter integration time. Has the same interpretation of values as MaxExposureTime. |
| `MaxGain` | 100 | 0...100 | admin: r/w operator: r/w | Decides how much gain the exposure control algorithm is allowed to use. **0**: The algorithm will never use more than the minimum value allowed by the hardware. **100**: The algorithm can use any gain setting the hardware supports. |
| `MinGain` | 0 | 0...100 | admin: r/w operator: r/w | Minimum gain the exposure control algorithm must use. Same interpretation of values as MaxGain. |
| `RedBalance` | 50 | 0...100 | admin: r/w operator: r/w | Fine-tune red gain for the manual white balance mode. |
| `Sharpness` | 50 | 0...100 | admin: r/w operator: r/w | The image sharpening. |
| `SNF` | 100 | 0...100 | admin: r/w operator: r/w | The impact of the spatial noise filter (SNF). |
| `TNF` | 100 | 0...100 | admin: r/w operator: r/w | The impact of the temporal noise filter (TNF). |
| `ToneMapping` | 50 | 0...100 | admin: r/w operator: r/w | Decides the amount of tone mapping that is applied to the image. If the value is set to zero only the standard gamma correction is applied, while a higher value will increase the visibility in the image. |
| `WDR` | Camera dependant | off, on | admin: r/w operator: r/w | Wide Dynamic Range mode. |
| `WDRLevel` | Camera dependant | Camera dependant (but always in the interval \[0, ..., 100\]) | admin: r/w operator: r/w | Wide Dynamic Range level. Higher level results in more WDR effect. |
| `WhiteBalance` | auto | auto, auto\_indoor, auto\_outdoor, hold, manual, fixed\_outdoor1, fixed\_outdoor2, fixed\_indoor, fixed\_fluor1, fixed\_fluor2 | admin: r/w operator: r/w | The white balance modes: **auto**: Automatic identification and compensation for the light source color. This can be used in most situations and is the recommended setting. **auto\_indoor**: Automatic identification and compensation for the light source color. This can be used in most indoor situations and is the recommended setting for indoor purposes. **auto\_outdoor**: Automatic identification and compensation for the light source color. This can be used in most outdoor situations and the recommended setting for outdoor purposes. **hold**: Fixes the white balance at its current state. **manual**: Fix the white balance with the help of a color neutral object. Set `CoordX` / `CoordY` to trigger a white balance measurement in the position of the object. Fine-tune with `RedBalance` and `BlueBalance` after setting the coordinate. **fixed\_outdoor1**: Fixed color adjustment for sunny weather, with a color temperature at around 5500K. **fixed\_outdoor2**: Fixed color adjustment for cloudy weather, with a color temperature at around 6500K. **fixed\_indoor**: Fixed color adjustment, ideal for a room with some artificial light other than fluorescent lighting and good for a normal color temperature at around 3000K. **fixed\_fluor1**: Fixed color adjustment; good for fluorescent lighting with a color temperature at around 4000K. **fixed\_fluor2**: Fixed color adjustment; good for fluorescent lighting with a color temperature at around 3000K. |
| `WhiteBalanceWindow` | auto | auto, custom | admin: r/w operator: r/w | The image area that the camera should try to compensate the light source color for. Both size and position of the area can be adjusted. |
| `LocalContrast` | 50 | 0...100 | admin: r/w operator: r/w | The level of local contrast. This will enhance the contrast locally, especially in scenes with high dynamic range. |
| `Stabilizer` | off | off on low high | admin: r/w operator: r/w viewer: r | Image stabilizer. Some products only allow toggling the image stabilizer on and off. Others have the two active states low and high, which enables the variable stabilization frequency. |
| `StabilizerType` | Product dependent | electronic, optical, limitedOptical | admin: r/w operator: r/w viewer: r | Parameters that indicate what type of image stabilization that is supported. **electronic**: Image stabilization that is supported by the software. **optical**: Image stabilization that is supported by optics. **limitedOptical**: Image stabilization that is supported by optics. Limited means that it cannot be used continuously due to mechanical limitations. |
| `StabilizerMargin` | 50 | 0...9999 | admin: r/w operator: r/w viewer: r | The max amplitude of vibration to stabilize for. Default value 50 means 0.5 degrees of margin. Max value is 99.99 degrees. |
| `StabilizerFocalLength` | 0 | 0...2 147 483 646 | admin: r/w operator: r/w viewer: r | The focal length (in micrometers) of the optics. This is used when no feedback on optical zoom setting is available. |
| `Defog` | off | off on auto | admin: r/w operator: r/w | The contrast adaptations to remove fog effect from the image. **off**: No defog effect. **auto**: Automatic adaptation of defog effect with boundaries changed by DefogEffect. **on**: Fixed defog effect according to DefogEffect. |
| `DefogEffect` | 0 | 0...100 | admin: r/w operator: r/w | The amount of defog effect to apply when Defog is active. Controls defog in both on and auto mode, i.e. the range differs between on and auto mode. |
| `SensorProtector` | close | close open | admin: r/w operator: r/w | Some products have a mechanical shutter to protect the sensor from getting exposed to sunlight. This parameter controls the state of the sensor protector shutter. **open**: Opens the sensor protector shutter. **close**: Closes the sensor protector shutter. The sensor would NOT get any light and so there would be NO video. |

### ImageSource.I0 parameters

| Parameter | Default values | Valid values | Security level (get/set) | Description |
| --- | --- | --- | --- | --- |
| `AutoRotation` |  | 0 90 180 270 | admin: r/w operator: r/w viewer: r | The rotation of the device measured by sensors to use auto rotation compensation on an image. |
| `CameraTiltOrientation` |  | \-90 0 90 | admin: r/w operator: r/w viewer: r | **\-90**: Select this option if the camera is mounted in the ceiling. **0**: Select this option if the camera is mounted on a wall. **90**: Select this option if the camera is mounted on a desk or a similar flat surface. |
| `ShockTriggeredLensCalibration` | no | yes no | admin: r/w operator: r viewer: r | This parameter will either enable or disable automatic calibration of the lens after a shock, as defined in the Shock detection. The Shock detection must be enabled and configured for the automatic lens calibration to work. **no**: Do not automatically calibrate the lens after the Shock detection service emits a Shock event. **yes**: Automatically calibrate the lens after the Shock detection service emits a Shock event. |

### ImageSource.I0.Appearance parameters

| Parameter | Default values | Valid values | Security level (get/set) | Description |
| --- | --- | --- | --- | --- |
| `AutoRotationEnabled` | yes | yes no | admin: r/w; operator: r/w; viewer: r; | **yes** = The image is automatically rotated when the stream is started according to sensor readings. **no** = The image is rotated when stream is started according to the Rotation setting. |

## Error codes

Errors will be generated as HTML text HTTP response code `200 OK`.