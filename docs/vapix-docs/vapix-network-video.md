---
title: Network video
url: "https://developer.axis.com/vapix/network-video/"
category: vapix
sha256: 510b28cca744fb7c4137dffba98ee67c397a110c639764c2d15c6ac5272123c7
scraped_at: "2026-01-09T15:19:15.493Z"
page_height: 28560
---

# Network video

VAPIX® Network video APIs is a set of application programming interfaces (APIs) for configuration and management of Axis network video products.

Selected functionality:

-   Get video and audio streams.
-   Get information about supported features and current product configuration.
-   Update product configuration.
-   Control pan, tilt and zoom (PTZ) functionality.
-   Control I/O and serial ports with connected external equipment.
-   Subscribe to events and notifications.
-   Record video to edge storage

The network video API documentation describes the different APIs and provides numerous examples how to use the API functions in common scenarios. VAPIX® contains documentation for VAPIX version 3.

All Axis network cameras and video encoders support VAPIX but most products do not support all APIs and API functions. Use the `Properties` parameters to check supported APIs. Some network video APIs can also be used for products such as video decoders, audio products, I/O modules and access control products.

## Version history

| Date | Updates |
| --- | --- |
| 2024–11–05 | [RAID Management](/vapix/network-video/raid-management/): New events added [Thermometry](/vapix/network-video/thermometry/): Updated to API version 1.1 |
| 2024–11–04 | [Virtual input API](/vapix/network-video/input-and-outputs/#virtual-input-api): Added parameter `duration` to `/axis-cgi/virtualinput/activate.cgi`. [Overlay text action](/vapix/network-video/event-and-action-services/#overlay-text-action): Added parameter `index`. |
| 2024–10–25 | [Network settings API](/vapix/network-video/network-settings-api/): Support for MACsec-PSK functionality added |
| 2024–10–22 | Removed **Integrating AXIS Q6000-E** |
| 2024–10–15 | [Optics Control](/vapix/network-video/optics-control/): Added method `setRelativeFocus` and `setRelativeMagnification`. Added examples. |
| 2024–09–19 | [Time API](/vapix/network-video/time-api/): Method `maxYearSupported` added, updated examples. |
| 2024–09–05 | [Network settings API](/vapix/network-video/network-settings-api/): Method `setGlobalProxyConfiguration` added. [Privacy mask API](/vapix/network-video/overlay-api/#privacy-mask-api): Upgraded to version 3. |
| 2024–08–01 | [Privacy mask API](/vapix/network-video/overlay-api/#privacy-mask-api), [Geolocation API](/vapix/network-video/geolocation-api/): Corrected security levels. [Zipstream API](/vapix/network-video/zipstream-technology/#zipstream-api): Corrected security levels for `/axis-cgi/zipstream/setprofile.cgi` and `/axis-cgi/zipstream/listprofiles.cgi`. [Video streaming](/vapix/network-video/video-streaming/): Corrected security level for Always multicast. [Guard tour API](/vapix/network-video/guard-tour-api/): Corrected security levels for `GuardTour.G#` and `GuardTour.G#.Tour.T#`. [PTZ control API](/vapix/network-video/pantiltzoom-api/#ptz-control-api): Corrected security level for `NbrOfCameras`. [System date and time](/vapix/network-video/system-settings/#system-date-and-time): Corrected security level for `Time.DST`. |
| 2024–05–07 | [Network settings API](/vapix/network-video/network-settings-api/): Methods `addVlan` and `removeVlan` added. |
| 2024–05–03 | [Dynamic overlay API](/vapix/network-video/overlay-api/#dynamic-overlay-api): Deprecated scrolling text. |
| 2024–04–26 | [DayNight API](/vapix/network-video/daynight-api/): New API |
| 2024–03–14 | [Media stream over HTTP](/vapix/network-video/media-stream-over-http/) and [Rate control](/vapix/network-video/rate-control/): Added `fullframerate` option to the video bitrate priority sections. |
| 2024–03–06 | [Input and outputs](/vapix/network-video/input-and-outputs/): Added parameters `Output.DelayTime` and `Output.Mode` |
| 2024–02–06 | [Light control API](/vapix/network-video/light-control/#light-control-api): Extended `getServiceCapabilities` response. |
| 2024–01–03 | [API Discovery service](/vapix/network-video/api-discovery-service/): Updated security levels |
| 2023–12–08 | [RAID Management](/vapix/network-video/raid-management/): New API [Network settings API](/vapix/network-video/network-settings-api/): Method `setWLANConfiguration` added |
| 2023–10–13 | [Group View](/vapix/network-video/group-view/): New API |
| 2023–09–21 | [Pencil privacy filter](/vapix/network-video/pencil-privacy-filter/): New API |
| 2023–09–19 | [Network settings API](/vapix/network-video/network-settings-api/): Added options for wired link modes. [Overlay API](/vapix/network-video/overlay-api/): New parameter added to Dynamic text overlays. [NTP API](/vapix/network-video/ntp-api/): Updated `getNTPInfo` with parameters for min/max poll. [Remote Syslog](/vapix/network-video/remote-syslog/): Added the syslog format ‘AXIS’. [Light control API](/vapix/network-video/light-control/#light-control-api): Added error codes. |
| 2023–09–01 | [MQTT client API](/vapix/network-video/mqtt-client-api/): Added parameters for HTTP/HTTPS proxy. |
| 2023–08–28 | [Media stream over HTTP](/vapix/network-video/media-stream-over-http/): New parameters added to `/axis-cgi/media.cgi`. |
| 2023–07–13 | [PTZ driver management API](/vapix/network-video/pantiltzoom-api/#ptz-driver-management-api): Deprecated events and methods, updated responses. |
| 2023–06–27 | [Event streaming over WebSocket](/vapix/network-video/event-streaming-over-websocket/): New API [Thermometry](/vapix/network-video/thermometry/): New API |
| 2023–05–22 | [Network settings API](/vapix/network-video/network-settings-api/): Added support for wired MSCHAPv2 802.1x and the parameter `useStaticDHCPFallback`. |
| 2023–04–24 | [Power settings](/vapix/network-video/power-settings/): Added support for power profiles Reorganized content list |
| 2023–04–04 | [Z-Wave API](/vapix/network-video/z-wave-api/): New API [Systemready API](/vapix/network-video/systemready-api/): `previewmode` and `uptime` parameters added. |
| 2023–02–08 | [PIR sensor configuration](/vapix/network-video/pir-sensor-configuration/): New API |
| 2023–01–02 | [Media stream over HTTP](/vapix/network-video/media-stream-over-http/): New API |
| 2022–11–30 | [NVR PoE switch configuration](/vapix/network-video/nvr-poe-switch-configuration/): New API |
| 2022–11–22 | [Analytics Metadata Producer Configuration](/vapix/network-video/analytics-metadata-producer-configuration/): New API |
| 2022–11–09 | [Pan/tilt/zoom API](/vapix/network-video/pantiltzoom-api/): `AutoFocusType`, `QuickZoom` and `TiltIllumination` parameters added to the PTZ control API. |
| 2022–11–07 | [NTP API](/vapix/network-video/ntp-api/): Added NTS support information. [Video streaming](/vapix/network-video/video-streaming/): Deprecated Bitmap support. [Pan/tilt/zoom API](/vapix/network-video/pantiltzoom-api/): Added parameter `removeallserverpresets`. |
| 2022–09–30 | [RTSP Adjustable Live Stream](/vapix/network-video/rtsp-adjustable-live-stream/): New API |
| 2022–09–21 | [Pan/tilt/zoom API](/vapix/network-video/pantiltzoom-api/): `SpotFocus` parameter added to the PTZ control API. |
| 2022–07–04 | [System settings](/vapix/network-video/system-settings/): Removed `date.cgi`. The `/axis-cgi/time.cgi`, found in [Time API](/vapix/network-video/time-api/) should be used instead. |
| 2022–07–01 | [Event and action services](/vapix/network-video/event-and-action-services/): New method [Network settings API](/vapix/network-video/network-settings-api/): New method [PTZ driver management API](/vapix/network-video/pantiltzoom-api/#ptz-driver-management-api): Deprecated methods [Video streaming](/vapix/network-video/video-streaming/): New parameters [Zipstream technology](/vapix/network-video/zipstream-technology/): New methods The **Audio API**, **Call service API** and **Media clip API** have been removed from Network video, but are available in the [Audio](/vapix/audio-systems/) section. |
| 2022–05–02 | [Signed Video](/vapix/network-video/signed-video/): New API |
| 2022–04–28 | [PTZ control API](/vapix/network-video/pantiltzoom-api/#ptz-control-api): New attributes/properties [Supervised I/O](/vapix/network-video/supervised-io/): New API version |
| 2022–03–30 | [Network settings API](/vapix/network-video/network-settings-api/): New parameters [Video streaming](/vapix/network-video/video-streaming/): Deprecated parameters |
| 2022–03–09 | [Temperature control](/vapix/network-video/temperature-control/): New API [Feature Flag Service](/vapix/network-video/feature-flag-service/): New API [External IP Device Information](/vapix/network-video/external-ip-device-information/): New API [Export recording API](/vapix/network-video/edge-storage-api/#export-recording-api): New parameters |
| 2022–02–08 | [Certificate management API](/vapix/network-video/certificate-management-api/): Added the example **Set HTTPS certificate** and **Assign a certificate to the IEEE 802.1x configuration** [Remote Syslog](/vapix/network-video/remote-syslog/): Updated example **Send syslogs over TLS** |
| 2022–01–24 | [Video streaming](/vapix/network-video/video-streaming/): New RTSP parameters [Network settings API](/vapix/network-video/network-settings-api/): Added the method `scanWLANNetworks` |
| 2021–12–22 | [Stitching](/vapix/network-video/stitching/): New API |
| 2021–11–30 | [Event and action services](/vapix/network-video/event-and-action-services/): Added examples to LED control. [Input and outputs](/vapix/network-video/input-and-outputs/): Added Output event. [MQTT client API](/vapix/network-video/mqtt-client-api/): Split into MQTT client API and MQTT Event Bridge. [MQTT Event Bridge](/vapix/network-video/mqtt-event-bridge/): Split off from MQTT client API and extended with new examples and specifications. [Pan/tilt/zoom API](/vapix/network-video/pantiltzoom-api/): New parameters added for `PTZ.UserBasic` and `PTZ.UserAdv`. [Serial port API](/vapix/network-video/serial-port-api/): Support for `wait` added. |
| 2021–11–08 | [Event and action services](/vapix/network-video/event-and-action-services/): Added SHA256 public key support. [Video output API](/vapix/network-video/video-output-api/): Removed support for legacy overlays. |
| 2021–10–26 | [MQTT client API](/vapix/network-video/mqtt-client-api/): Support for ALPN added [Rate control](/vapix/network-video/rate-control/): ABR stream status example added. |
| 2021–10–12 | [Optics Control](/vapix/network-video/optics-control/): New API [mDNS-SD API](/vapix/network-video/mdns-sd-api/): Minor updates [Imaging API](/vapix/network-video/imaging-api/): Updated security levels |
| 2021–09–28 | [API Discovery service](/vapix/network-video/api-discovery-service/): New parameter [Imaging API](/vapix/network-video/imaging-api/): Minor updates [Network settings](/vapix/network-video/network-settings/): New parameter, minor updates [Parameter management](/vapix/network-video/parameter-management/): Minor updates [System settings](/vapix/network-video/system-settings/): Deprecated method, minor updates [Video streaming](/vapix/network-video/video-streaming/): Deprecated parameters |
| 2021–08–13 | [Network settings](/vapix/network-video/network-settings/): New parameter |
| 2021–08–04 | [Rate control](/vapix/network-video/rate-control/): Minor updates [mDNS-SD API](/vapix/network-video/mdns-sd-api/): New method |
| 2021–07–19 | [Clear view](/vapix/network-video/clear-view/): Minor updates [Thermal imaging](/vapix/network-video/thermal-imaging/): Minor updates |
| 2021–07–09 | [Network settings API](/vapix/network-video/network-settings-api/): New method [Event and action services](/vapix/network-video/event-and-action-services/): New action template Media clip API: Minor updates |
| 2021–06–11 | [Capture mode](/vapix/network-video/capture-mode/): Minor updates [I/O port management](/vapix/network-video/io-port-management/): Minor updates Media clip API: Minor updates [Overlay API](/vapix/network-video/overlay-api/): Minor updates |
| 2021–06–02 | AXIS Object analytics API : Transferred to Applications [I/O port API](/vapix/network-video/input-and-outputs/#io-port-api): Minor updates |
| 2021–05–21 | [Basic device information](/vapix/network-video/basic-device-information/): Minor updates [Disk management API](/vapix/network-video/edge-storage-api/#disk-management-api): Minor updates [Event and action services](/vapix/network-video/event-and-action-services/): Minor updates [I/O port API](/vapix/network-video/input-and-outputs/#io-port-api): Minor updates [Network settings](/vapix/network-video/network-settings/): Minor updates [PTZ control](/vapix/network-video/pantiltzoom-api/#ptz-control): Minor updates |
| 2021–04–28 | Audio API: Minor updates [Event and action services](/vapix/network-video/event-and-action-services/) Media clip API: Minor updates [Rate control](/vapix/network-video/rate-control/): Minor updates [MQTT client API](/vapix/network-video/mqtt-client-api/): Minor updates [Video output API](/vapix/network-video/video-output-api/): Minor updates [Dynamic overlay API](/vapix/network-video/overlay-api/#dynamic-overlay-api): Minor updates |
| 2021–04–15 | [Clear view](/vapix/network-video/clear-view/): New API |
| 2021–04–09 | AXIS Object analytics API: New API [Video streaming](/vapix/network-video/video-streaming/): Minor updates |
| 2021–03–17 | [Siren and light](/vapix/network-video/siren-and-light/): New API [Certificate management API](/vapix/network-video/certificate-management-api/): New API [System settings](/vapix/network-video/system-settings/): Minor updates [I/O port API](/vapix/network-video/input-and-outputs/#io-port-api): Minor updates [Queuing API](/vapix/network-video/pantiltzoom-api/#queuing-api): Minor updates |
| 2021–02–16 | [Introduction](/vapix/network-video/): New tutorial API [Light control API](/vapix/network-video/light-control/#light-control-api): Minor updates [On-screen controls](/vapix/network-video/on-screen-controls/): Minor updates |
| 2021–02–11 | [Event and action services](/vapix/network-video/event-and-action-services/): Minor updates [Video streaming indicator](/vapix/network-video/video-streaming-indicator/): Minor updates [MQTT client API](/vapix/network-video/mqtt-client-api/): Minor updates [Basic device information](/vapix/network-video/basic-device-information/): Minor updates |
| 2020–12–18 | [Recording group](/vapix/network-video/recording-group/): New API [OAK API](/vapix/network-video/oak-api/): New API [Input and outputs](/vapix/network-video/input-and-outputs/): Minor updates [Edge storage API](/vapix/network-video/edge-storage-api/): Minor updates [Network settings](/vapix/network-video/network-settings/): Minor updates [PTZ control API](/vapix/network-video/pantiltzoom-api/#ptz-control-api): Minor updates |
| 2020–11–24 | [Find my device](/vapix/network-video/find-my-device/): New API [PTZ Autotracker API](/vapix/network-video/ptz-autotracker-api/): New API |
| 2020–11–10 | [PTZ control API](/vapix/network-video/pantiltzoom-api/#ptz-control-api): Minor updates [MQTT client API](/vapix/network-video/mqtt-client-api/): Minor updates [Recording API](/vapix/network-video/edge-storage-api/#recording-api): Minor updates [Basic device information](/vapix/network-video/basic-device-information/): Minor updates |
| 2020–10–27 | [Event and action services](/vapix/network-video/event-and-action-services/): Minor updates |
| 2020–10–22 | [Network settings](/vapix/network-video/network-settings/): Minor updates [Light control API](/vapix/network-video/light-control/#light-control-api): Minor updates |
| 2020–10–06 | [Pan/tilt/zoom API](/vapix/network-video/pantiltzoom-api/): Minor updates. [Power settings](/vapix/network-video/power-settings/): Minor updates. |
| 2020–09–30 | [Overlay modifiers](/vapix/network-video/overlay-api/#overlay-modifiers): Minor updates [Event and action services](/vapix/network-video/event-and-action-services/): Minor updates |
| 2020–08–31 | [View Area API](/vapix/network-video/view-area-api/): New API |
| 2020–08–26 | [Imaging API](/vapix/network-video/imaging-api/): Minor updates [Image source rotation](/vapix/network-video/image-source-rotation/): Minor updates |
| 2020–08–25 | [Remote Syslog](/vapix/network-video/remote-syslog/): New API |
| 2020–08–05 | [Edge storage API](/vapix/network-video/edge-storage-api/): Minor updates Media clip API: Minor updates |
| 2020–07–22 | [Custom HTTP header API](/vapix/network-video/custom-http-header-api/): New API |
| 2020–07–16 | [MQTT client API](/vapix/network-video/mqtt-client-api/): New API |
| 2020–07–14 | [Zipstream technology](/vapix/network-video/zipstream-technology/): Minor updates [Edge storage API](/vapix/network-video/edge-storage-api/): Minor updates |
| 2020–06–16 | [Zipstream technology](/vapix/network-video/zipstream-technology/): Minor updates |
| 2020–06–15 | [Privacy mask API](/vapix/network-video/overlay-api/#privacy-mask-api): Minor updates |
| 2020–06–11 | Media clip API: Minor updates [System settings](/vapix/network-video/system-settings/): Minor updates [Disk management API](/vapix/network-video/edge-storage-api/#disk-management-api): Minor updates |
| 2020–06–04 | [Network settings](/vapix/network-video/network-settings/): Minor updates [Network settings API](/vapix/network-video/network-settings-api/): Minor updates [Image source rotation](/vapix/network-video/image-source-rotation/): Minor updates [Video streaming](/vapix/network-video/video-streaming/): Minor updates |
| 2020–05–29 | [Disk properties API](/vapix/network-video/edge-storage-api/#disk-properties-api): Minor updates. |
| 2020–05–19 | [Disk management API](/vapix/network-video/edge-storage-api/#disk-management-api): Minor updates [On-screen controls](/vapix/network-video/on-screen-controls/): Minor updates |
| 2020–05–15 | [QuadView configuration](/vapix/network-video/quadview-configuration/): New API |
| 2020–05–12 | [Stream profiles](/vapix/network-video/stream-profiles/): New API [NTP API](/vapix/network-video/ntp-api/): New API [Privacy mask API](/vapix/network-video/overlay-api/#privacy-mask-api): Minor updates |
| 2020–05–04 | [Firmware management API](/vapix/network-video/firmware-management-api/): Minor updates. |
| 2020–04–17 | [Video streaming](/vapix/network-video/video-streaming/): Minor updates. |
| 2020–04–02 | [Network settings API](/vapix/network-video/network-settings-api/): Minor updates, clarified the documentation. |
| 2020–03–13 | [Systemready API](/vapix/network-video/systemready-api/): New API. [Export recording API](/vapix/network-video/edge-storage-api/#export-recording-api): Minor update, clarified the documentation. [Firmware management API](/vapix/network-video/firmware-management-api/): Minor update. |
| 2020–03–09 | [I/O port management](/vapix/network-video/io-port-management/): New API. [SSH](/vapix/network-video/ssh/): New API. |
| 2020–02–10 | [Power settings](/vapix/network-video/power-settings/): New API. [Light control API](/vapix/network-video/light-control/#light-control-api) : Minor update. [Overlay image API](/vapix/network-video/overlay-api/#overlay-image-api): Minor update. [On-screen controls](/vapix/network-video/on-screen-controls/): Minor update. |
| 2020–01–21 | [Feature discovery](#feature-discovery): New information. |
| 2020–01–20 | Deprecated `/axis-cgi/record/play.cgi`. |
| 2019–12–20 | [Source-specific multicast](/vapix/network-video/video-streaming/#source-specific-multicast): New API. [Regional settings](/vapix/network-video/regional-settings/): New API. |
| 2019–12–13 | [Supervised I/O](/vapix/network-video/supervised-io/): New API. |
| 2019–11–15 | [Light control API](/vapix/network-video/light-control/#light-control-api): New API. |
| 2019–11–14 | [On-screen directional indicator](/vapix/network-video/on-screen-directional-indicator/): New API. |
| 2019–10–02 | Call service API: Minor updates. |
| 2019–09–25 | [Event and action services](/vapix/network-video/event-and-action-services/): Minor updates. |
| 2019–09–18 | [Overlay image API](/vapix/network-video/overlay-api/#overlay-image-api): New API. [Rate control](/vapix/network-video/rate-control/): Minor updates. |
| 2019–08–30 | [mDNS-SD API](/vapix/network-video/mdns-sd-api/): New API. |
| 2019–08–29 | [Image source rotation](/vapix/network-video/image-source-rotation/): New API. |
| 2019–08–23 | [Rate control](/vapix/network-video/rate-control/): New API. [Guard tour API](/vapix/network-video/guard-tour-api/): Minor update. |
| 2019–08–19 | [Serial port API](/vapix/network-video/serial-port-api/): Minor update. [Guard tour API](/vapix/network-video/guard-tour-api/): Minor update. |
| 2019–08–09 | [Time API](/vapix/network-video/time-api/): New API. [System date and time](/vapix/network-video/system-settings/#system-date-and-time): Minor update. |
| 2019–07–22 | [I/O port API](/vapix/network-video/input-and-outputs/#io-port-api): Minor update. |
| 2019–07–10 | [API versioning](#api-versioning): Added information about API versioning. |
| 2019–06–05 | [Video streaming indicator](/vapix/network-video/video-streaming-indicator/): New API. |
| 2019–06–03 | [Pan/tilt/zoom API](/vapix/network-video/pantiltzoom-api/): Minor update. [System settings](/vapix/network-video/system-settings/): Minor update. [Firmware management API](/vapix/network-video/firmware-management-api/): Minor update. |
| 2019–05–24 | [Dynamic overlay API](/vapix/network-video/overlay-api/#dynamic-overlay-api): Minor update. |
| 2019–05–02 | [On-screen controls](/vapix/network-video/on-screen-controls/): Clarified the documentation. |
| 2019–04–26 | [Network settings API](/vapix/network-video/network-settings-api/): New API. [PTZ control API](/vapix/network-video/pantiltzoom-api/#ptz-control-api): Minor update. |
| 2019–04–17 | [System settings](/vapix/network-video/system-settings/): Minor updates. [Basic device information](/vapix/network-video/basic-device-information/): Minor updates. |
| 2019–04–15 | [Scene profile API](/vapix/network-video/video-streaming/#scene-profile-api): Minor updates. [Basic device information](/vapix/network-video/basic-device-information/): Minor updates. [Server report](/vapix/network-video/system-settings/#server-report): Minor updates. |
| 2019–03–19 | [Imaging API](/vapix/network-video/imaging-api/): New API. |
| 2019–02–20 | **Firmware management API:** Updated error codes.**N/A:** Removed documentation that was not included in the firmware release. |
| 2018–12–20 | **Scene profile API:** Added parameters and clarified the documentation.**Event and action services:** Clarified the documentation. |
| 2018–12–14 | [Capture mode](/vapix/network-video/capture-mode/): New API.[API Discovery service](/vapix/network-video/api-discovery-service/): New API.[Basic device information](/vapix/network-video/basic-device-information/): New API. |
| 2018–10–01 | **Dewarped views:** Added support for additional views.**Edge storage API:** Clarified the documentation.**Zipstream technology:** Added support for minimum FPS. |
| 2018–09–05 | **Audio API:** Added new Audio compression formats & Audio source parameters.**Video output API:** Added support for picture-in-picture.**System settings:** Updated Content-type in the [Add, modify and delete user accounts](/vapix/network-video/system-settings/#add-modify-and-delete-user-accounts) examples. |
| 2018–05–18 | **Privacy mask API:** Updated the API and added support for Adaptive mosaic, Polygon and Multi channel products. |
| 2018–04–26 | **Audio API:** Updated the information in the transmit audio data-section. |
| 2018–04–06 | [Firmware management API](/vapix/network-video/firmware-management-api/): New API. |
| 2018–03–14 | **On-screen controls:** Clarified the documentation. |
| 2018–02–28 | [Decoder API](/vapix/network-video/decoder-api/): New API. |
| 2018–01–19 | [Dynamic overlay API](/vapix/network-video/overlay-api/#dynamic-overlay-api), [Overlay modifiers](/vapix/network-video/overlay-api/#overlay-modifiers) & [Geolocation API](/vapix/network-video/geolocation-api/): New API:s.**Edge storage API:** Corrected an error in the Disk management API parameters table [Parameters](/vapix/network-video/edge-storage-api/#parameters-disk-management-api).Harmonized content across sections. |
| 2017–10–10 | [Video output API](/vapix/network-video/video-output-api/): New API.**Video streaming:** Corrected example with multicast in [RTSP SETUP](/vapix/network-video/video-streaming/#rtsp-setup). Also added the parameter FrameSkipMode in [Parameter specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url). |
| 2017–09–22 | **Video streaming:** Added information about videozfpsmode and videozminfps [Parameter specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url).**Event and action services:** Login examples using ‘Basic’ has been updated to use ‘Digest’ instead. [Create web service connections](/vapix/network-video/event-and-action-services/#create-web-service-connections). |
| 2017–09–01 | Deprecated zipstream strengths 60–100 |
| 2017–07–26 | **PTZ control API**: Corrected example in section [PTZ control](/vapix/network-video/pantiltzoom-api/#ptz-control) |
| 2017-05-04 | Media clip API update: Added `/axis-cgi/stopclip.cgi` and support for MP3.Call service API update: Added support for IPv6. |
| 2017–04–12 | [On-screen controls](/vapix/network-video/on-screen-controls/): New API. |
| 2017–03–28 | Section **Applications** moved from VAPIX® Network video to VAPIX® applications. |
| 2017–03–09 | **Audio Control Service API**: Moved to VAPIX® Audio systems.**Audio Relay Service API**: Moved to VAPIX® Audio systems.**Auto Speaker Test API**: Moved to VAPIX® Audio systems.**Audio API**: Corrected example in section .**RTSP API**: Added `videocodec=h265`**VMD4**: Preset support for mechanical PTZ cameras. |
| 2017–02–27 | **Audio Control Service API**: New API.**Audio Relay Service API**: New API. |
| 2016–12–16 | [Speed dry API](/vapix/network-video/pantiltzoom-api/#speed-dry-api): New API. |
| 2016–12–07 | **Video Motion Detection 4 API**: New API (moved to the Applications folder as of 2017–03–28).: Updated. |
| 2016–10–18 | [Scene profile API](/vapix/network-video/video-streaming/#scene-profile-api): New API.[Zipstream technology](/vapix/network-video/zipstream-technology/): Updated API. |
| 2016–10–14 | Axis VAPIX® version 2 released. |
| 2016–08–26 | **Focus recall API**: New API. |
| 2016–07–07 | **Call service API** release 1.7: Added encryption and certificate configuration. Added attributes in SIP configuration and SIP accounts. Added calling timeout in SIP configuration.**Pan/Tilt/Zoom API**: Corrected PTZ error event topic name and description. |
| 2016–05–27 | **General purpose I/O service API**: New API.**Heartbeat service API**: New API.**Trigger data**: Deprecated. Replaced by Event data streaming. |
| 2016–01–27 | **Call service API** release 1.6: Added audio codec priority and stream parameter configuration.**Percent encoding**: Added list of percent-encoded characters. |
| 2015–11–13 | **Virtual input API**: Improved descriptions.**Applications**: All application API:s moved to a single chapter. |
| 2015–06–30 | **Audio API**: Added codec opus and `AudioSource.A#.Channel` parameters.**Auto speaker test API**: New API.**Pan/Tilt/Zoom API**: Corrected description of `continuousfocusmove` in PTZ control API `/axis-cgi/com/ptz.cgi` |
| 2015–05–25 | **Orientation API**: New API. |
| 2015–05–05 | **Thermal imaging**: New API. Includes Color palettes, Isotherm API and Temperature alarm API.**Edge storage API**: Added disk encryption in Disk management API and Disk properties API. Supported in AXIS OS 5.80.**Event and action services**: Parameter-based motion detection and its events are deprecated in AXIS OS 5.80 in later. Replaced by AXIS Video motion detection 3. |
| 2015–04–24 | **Call service API**: New API. |
| 2015–04–07 | **Axis Zipstream technology**: New API. |
| 2015–03–11 | **Edge storage API**: Added Recording storage limit API and Export recording API.**I/O port API and Virtual input API**: Clarified that URI-reserved characters must be percent-encoded.**Event and action services**: Added SFTP recipient. Supported in AXIS OS 5.70 and later. |
| 2015–02–16 | **Shock detection API**: New API.**Digital autotracking API**: Clarified that image rotation affects small object filter.**Video motion detection 3 API**: Clarified that image rotation affects small object filter. |
| 2015–01–08 | **Digital autotracking API**: Added Digital autotracking version 2.**Video motion detection 3 API**: Added information about multichannel products. |
| 2014–12–16 | **Integrating AXIS Q6000-E**: New API. |
| 2014–12–02 | Parameters `Log.System` and `Log.Access` removed in AXIS OS 5.60 and later.**Edge storage API**: Removed extra " characters.**Event data streaming**: Minor correctionsFTP recipient: Parameter `temporary` supported from AXIS OS 5.70. Added missing parameter `upload_path`. |
| 2014–10–30 | **Video Motion Detection 3 API**: New API. |
| 2014–10–14 | Axis VAPIX®. Initial version. |

## About VAPIX
### General abbreviations

The following abbreviations are used throughout the VAPIX® documentation.

-   **CGI**: Common Gateway Interface – a standardized method of communication between a client (for example a web browser) and a server (for example a web server).
-   **TBD**: To be done/designed – signifies that the referenced section/subsection/entity is intended to be specified, but has not reached a level of maturity to be public at this time.
-   **N/A**: Not applicable - the feature/parameter/value is of no use in a specific task.
-   **URL**: A Uniform Resource Location (URL) is a compact string representation for a resource available via the Internet. RFC 1738 describes the syntax and semantics for a URL.
-   **URI**: A Uniform Resource Identifier (URI) is a compact string of characters for identifying an abstract or physical resource. RFC 3986 describes the generic syntax of URI.

### Obsolete and removed CGIs
#### Obsolete

Some CGI requests, arguments and values in the VAPIX® documentation may be obsolete and are provided for backward compatibility. These might not be supported in the future.

#### Removed

The HTTP API version 1 (VAPIX 1) is no longer supported.

### HTTP status codes

The Axis product returns standard HTTP status codes. See RFC 1945 and RFC 2616.

### Percent encoding

HTTP and RTSP VAPIX requests must follow the URI generic syntax defined in RFC 3986. Use character encoding ISO/IEC 8859-1. If a parameter in the request contains characters that are not allowed in a URI, these characters must be percent-encoded. That is, characters such as `/`, `\`, `:`, `=`, `&`, `?`, etc in a `<argument>` or a `<value>` must be replaced by `%<ASCII hex>`.

Correct:

```bash
http://<servername>/axis-cgi/record/continuous/addconfiguration.cgi?diskid=SD\_DISK&options=resolution%3D640x480
```

Wrong:

```bash
http://<servername>/axis-cgi/record/continuous/addconfiguration.cgi?diskid=SD\_DISK&options=resolution=640x480
```

| Character | Percent encoding |
| --- | --- |
| blank space | `%20` |
| " | `%22` |
| # | `%23` |
| % | `%25` |
| & | `%26` |
| , | `%2C` |
| / | `%2F` |
| : | `%3A` |
| \= | `%3D` |
| ? | `%3F` |
| \\ | `%5C` |

### User access rights

User access rights for CGI requests are determined by group membership.

| Security level | Description |
| --- | --- |
| `viewer` | Users with `viewer`, `operator` or `admin` rights can access this functionality. |
| `operator` | Users with `operator` or `admin` rights can access this functionality. |
| `admin` | Users with `admin` rights can access this functionality. |

### Parameter value convention

In tables defining CGI arguments and supported values, the default value for optional arguments is system configured.

### Unknown arguments

If an unknown argument is requested, for example if an argument is misspelled it will be ignored by the built-in server in the Axis product. That means that no response feedback will be given.

### XML schemas

In many VAPIX API:s, responses are formatted according to an XML schema. Clients should always retrieve supported schema versions from the Axis product before sending other requests. In subsequent requests, the schema version must be specified. Make sure that the client and the Axis product use the same schema version.

Retrieve schema version example:

```bash
http://<servername>/axis-cgi/disks/networkshare/schemaversions.cgi
```

Subsequent request example:

```bash
http://<servername>/axis-cgi/disks/networkshare/list.cgi?schemaversion=1&shareid=all
```

Axis’ XML Schemas are available at [http://www.axis.com/vapix/http\_cgi/](http://www.axis.com/vapix/http_cgi/)

#### XML schema versions

The schema version consists of two numbers; major version and minor version. The major version is the number before the decimal point. The minor version is the number after the decimal point.

Example:

```bash
SchemaVersion=1.0
```

If a schema is updated, the version changes. The major version is changed if the update breaks backward compatibility, for example if a new element is added to the beginning of a sequence. If the major version changes, the schema namespace is also changed and the minor version is set to zero. The minor version is changed if the update does not break backward compatibility, for example if a new attribute is added.

In **API requests**, the major schema version must be specified. The latest minor version will be used.

In **API responses**, the root element contains the following attributes:

| Attribute | Description |
| --- | --- |
| `SchemaVersion` | The version of the XML schema that the response is formatted according to. |
| `Deprecated` | `true` = The schema version is deprecated and will eventually be removed. Deprecated schema versions should not be used.`false` = The schema version is not deprecated. |

info

Old schema versions may be removed without first being marked as deprecated.

### Style convention - CGIs
#### Content to be replaced

In URL syntax and in descriptions of CGI arguments, text within angle brackets denotes content that should be replaced with either a value or a text string. When replacing the text string, the angle brackets must also be replaced. For example, the name of the camera or video encoder is denoted by `<servername>` in the URL syntax description. In the URL syntax examples `<servername>` is replaced by the IP address or hostname of the device.

XML responses do not apply to this style convention. For this type of responses a text string within angle brackets (including the brackets) is a tag (start-tag or end-tag). XML response descriptions use text inside square or angle brackets to denote content that is replaced by the server. For example, `[int]`/`<int>` is replaced by an integer.

#### CGI requests

CGI requests are written in lower-case. CGI arguments are written in lower-case and as one word. When the CGI request includes internal parameters, the internal parameters must be written exactly as named in the Axis product. For the `POST` method the parameters must be included in the body of the HTTP request. The CGIs are organized in function-related directories under the `/axis-cgi` directory. The file extension is required.

URL syntax is written with the word "**Syntax**:" in bold face, followed by a box with the referred syntax, as shown below. The name of the Axis product is written as `<servername>`. This is intended to be replaced with the name of the actual Axis product. The name can either be a name, for example "`thecam`" or "`thecam.adomain.net`" or the associated IP number for the server, for example `10.10.2.139`. Text within square brackets denotes content that can be omitted.

**Syntax:**

```bash
http://<servername>/axis-cgi/<subdir>\[/<subdir>...\]<cgi>.<ext>\[?<argument>=<value>\[&<argument>=<value>...\]\]
```

#### CGI response

A description of the data response is written with "**Response**" in bold face, followed by the HTTP status code, header fields and a box with the HTTP body. Carriage Return and Line Feed (CRLF) are not explicitly printed.

**Response:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `image/jpeg`

Body:

```bash
<JPEG image data>
```

info

Response examples are examples only. The returned data will differ depending on product model and configuration.

#### CGI example

**Request default image**

**Request:**

```bash
http://<servername>/axis-cgi/jpg/image.cgi
```

### JSON and simplified key-value requests

In some VAPIX API:s, for example the Call service API, requests can be constructed using JSON or using a simplified key-value format.

The simplified key-value format is a flattened structure with `key=value` strings. Levels in the structure are indicated by underscores (\_).

-   Boolean values are encoded as `true` and `false`.
-   The `NULL` value is encoded as `null`.
-   Strings are URL-encoded and may start and end with quotation marks. Example: `"a+string%0A"`.
-   Array keys are encoded as `_index_` where `index` is an integer starting from 0.

Character sets are not converted or validated. UTF-8 is recommended.

This example from the Call service API shows how to request the current SIP configuration using cURL. The first example shows the JSON syntax, the second example shows the corresponding simplified syntax.

**NOTE**

When using cURL on Windows, you might need to escape the quote characters for the commands to work, i.e:

```bash
-d '{"axcall:GetSIPConfiguration":{}}'
```

should instead be written as:

```bash
-d "{\\"axcall:GetSIPConfiguration\\":{}}"
```

JSON request and response:

```bash
$ curl --anyauth "http://root:pass@192.168.0.90/vapix/call" -s -d '{"axcall:GetSIPConfiguration":{}}'> {>   "SIPConfiguration": {>     "SIPEnabled": false,>     "TURNServers": \[\],>     "STUNServers": \[\],>     "ICEEnabled": false,>     "AllowIncomingCalls": false,>     "TURNEnabled": false,>     "STUNEnabled": false,>     "ApplyUserAuthentication": false,>     "AllowedUsers": \[\],>     "SIPPort": 5060,>     "SIPTLSPort": 5061,>     "ApplyAllowedURIs": false,>     "AllowedURIs": \[\]>   }> }
```

Simplified request and response:

```bash
$ curl --anyauth "http://root:pass@192.168.0.90/vapix/call?format=simple&action=axcall:GetSIPConfiguration"'> SIPConfiguration\_SIPEnabled=false> SIPConfiguration\_SIPPort=5060> SIPConfiguration\_SIPTLSPort=5061> SIPConfiguration\_STUNEnabled=false> SIPConfiguration\_TURNEnabled=false> SIPConfiguration\_ICEEnabled=false> SIPConfiguration\_AllowIncomingCalls=false> SIPConfiguration\_ApplyUserAuthentication=false> SIPConfiguration\_ApplyAllowedURIs=false
```

This example shows how to retrieve a list of structures in simplified format. The example shows a list of three `SIPAccounts`. Each key is prefixed with `_index_` where `index` is the index of the element in the list. All keys that share the same prefix correspond to the same element.

Simplified request and response:

```bash
$ curl --anyauth "http://root:pass@192.168.0.90/vapix/call?format=simple&action=axcall:GetSIPAccounts"'> SIPAccount\_0\_Id="sip\_account\_0"> SIPAccount\_0\_Username="local\_account\_ipv4\_udp"> SIPAccount\_0\_Password=null> SIPAccount\_0\_Registrar=null> SIPAccount\_0\_PublicDomain=null> SIPAccount\_0\_IsDefault=false> SIPAccount\_0\_Transport="udp"> SIPAccount\_0\_CallerId="local\_account\_ipv4\_udp"> SIPAccount\_1\_Id="sip\_account\_1"> SIPAccount\_1\_Username="1234"> SIPAccount\_1\_Password="password"> SIPAccount\_1\_Registrar="192.168.0.91"> SIPAccount\_1\_PublicDomain="exampledomain.com"> SIPAccount\_1\_IsDefault=true> SIPAccount\_1\_Transport="udp"> SIPAccount\_1\_CallerId="Entrance Door"> SIPAccount\_1\_DTMFConfigurationId="internal\_config"> SIPAccount\_2\_Id="sip\_account\_2"> SIPAccount\_2\_Username="987654"> SIPAccount\_2\_Password="password2"> SIPAccount\_2\_Registrar=null> SIPAccount\_2\_PublicDomain="examplesecurity.se"> SIPAccount\_2\_IsDefault=false> SIPAccount\_2\_Transport="udp"> SIPAccount\_2\_CallerId="Entrance Door (Axis)"> SIPAccount\_2\_DTMFConfigurationId="remote\_config"> SIPAccount\_3\_Id="sip\_account\_3"> SIPAccount\_3\_Username="12309"> SIPAccount\_3\_Password="password3"> SIPAccount\_3\_Registrar=null> SIPAccount\_3\_PublicDomain="\[fd12:3456:789a:1::90\]"> SIPAccount\_3\_PrioritizeIPv6=true> SIPAccount\_3\_IsDefault=false> SIPAccount\_3\_Transport="udp"> SIPAccount\_3\_CallerId="Entrance Door (Axis)"> SIPAccount\_3\_DTMFConfigurationId="remote\_config"> SIPAccount\_4\_Id="sip\_account\_4"> SIPAccount\_4\_Username="local\_account\_ipv6\_tcp"> SIPAccount\_4\_Password=null> SIPAccount\_4\_Registrar=null> SIPAccount\_4\_PublicDomain=null> SIPAccount\_4\_PrioritizeIPv6=true> SIPAccount\_4\_IsDefault=false> SIPAccount\_4\_Transport="tcp"> SIPAccount\_4\_CallerId="local\_account\_ipv6\_tcp"
```

Corresponding request and response in JSON:

JSON request and response:

```bash
$ curl --anyauth "http://root:pass@192.168.0.90/vapix/call" -s -d '{"axcall:GetSIPAccounts":{}}'> {>   "SIPAccount": \[>     {>       "Username": "local\_account\_ipv4\_udp",>       "PublicDomain": null,>       "CallerId": "local\_account\_ipv4\_udp",>       "Registrar": null,>       "Transport": "udp",>       "Password": null,>       "Id": "sip\_account\_0",>       "IsDefault": false>     },>     {>       "Username": "1234",>       "PublicDomain": "exampledomain.com",>       "CallerId": "Entrance Door",>       "DTMFConfigurationId": "internal\_config",>       "Registrar": "192.168.0.91",>       "Transport": "udp",>       "Password": "password",>       "Id": "sip\_account\_1",>       "IsDefault": true>     },>     {>       "Username": "987654",>       "PublicDomain": "examplesecurity.se",>       "CallerId": "Entrance Door (Axis)",>       "DTMFConfigurationId": "remote\_config",>       "Registrar": null,>       "Transport": "udp",>       "Password": "password2",>       "Id": "sip\_account\_2",>       "IsDefault": false>     },>     {>       "Username": "12309",>       "Registrar": null,>       "PublicDomain": "\[fd12:3456:789a:1::90\]",>       "SecondaryRegistrar": "",>       "SecondaryPublicDomain": "",>       "CallerId": "Entrance Door (Axis)",>       "DTMFConfigurationId": "internal\_config",>       "Transport": "udp",>       "Password": "password3",>       "Id": "sip\_account\_3",>       "IsDefault": false>     },>     {>       "Username": "local\_account\_ipv6\_tcp",>       "PublicDomain": null,>       "CallerId": "local\_account\_ipv6\_tcp",>       "Registrar": null,>       "Transport": "tcp",>       "PrioritizeIPv6": true,>       "Password": null,>       "Id": "sip\_account\_4",>       "IsDefault": false>     }>   \]> }
```

This example shows a response with fault codes.

JSON request:

```bash
curl --anyauth "http://root:pass@192.168.0.90/vapix/axast" -s -d '{"axast:PerformSpeakerTest":{}}'
```

**JSON response:**

-   **HTTP code**: `400 Bad Request`

```bash
{    "Fault": "env:Receiver",    "FaultCode": "ter:Action",    "FaultSubCode": "axast:DeviceNotCalibrated",    "FaultReason": "The Auto Speaker Test cannot be done without prior calibration.",    "FaultMsg": null}
```

Simplified request:

```bash
curl --anyauth "http://root:pass@192.168.0.90/vapix/axast?format=simple&action=axast:PerformSpeakerTest"
```

**Simplified response:**

-   **HTTP code**: `400 Bad Request`

```bash
Fault="env:Receiver"FaultCode="ter:Action"FaultSubCode="axast:DeviceNotCalibrated"FaultReason="The Auto Speaker Test cannot be done without prior calibration."FaultMsg=null
```

### API versioning

An API includes version numbering that consists of two numbers separated by a dot `X.X`. The first number represents the major version number of the API while the second represents the minor.

The following example is from an entry in the API Discovery service, where the version number of the API :

```bash
{    "id": "basic-device-info",    "version": "1.2",    "docLink": "link to doc",    "name": "API name as described in the VAPIX documentation."}
```

Axis Communications uses both numbers to group new and/or upgraded functions. The numbers will increase for either the major or minor version depending on the change.

The major numbers of an API is changed when the API introduces an update that is backwards incompatible, i.e. when an existing client code ceases to work with the new API unless there are modifications done to it. Example of backwards incompatible changes are function signature changes, removal of a function or making an asynchronous function synchronous. To counter this, the API generally provides multiple sets of itself with different major numbers to make backwards compatibility possible when introducing new features.

The minor version of an API is changed to enhance functionality or fix bugs, which means that the client code should continue to work when there is a minor number change in the API.

As an example, a client implements a code to work with API version 1.0. The next release will then become API version 1.1. This means that the client code should work without any modifications.

A list of available APIs, together with their versions, can be retrieved through the [API Discovery service](/vapix/network-video/api-discovery-service/), which makes it possible to retrieve information about APIs supported on a specific Axis product.

### Feature discovery

To be able to drive and control a VAPIX® device, a user must first be aware of the features that the device is supporting. A feature discovery can be made by using one of 3 different methods:

-   API Discovery
-   Feature API version
-   Feature API informing capabilities

info

The order ranges from generic to a more specific feature discovery.

#### API Discovery

The easiest way to find a certain feature is to look for the existence of a feature API by using the API Discovery service. Through this you will be able to find an API entry with a version number that indicates whether there is support for the feature.

**Example**

Finding the Temperature control API entry with API Discovery means that the device supports the temperature feature.

#### Feature API version

The version of the feature API is found by using the API Discovery service and might indicate if features have been added to the API over time.

**Example**

The Temperature control API might exist on 2 different products and in 2 different versions. The first product might show Temperature control API version 1.0, while the second product has Temperature control API version 1.1. In this case, the documentation will show that the method `setTemperatureAlarm` was added as part of version 1.1.

#### Feature API informing capabilities

In some cases, the feature information cannot be obtained unless you first query the feature API. This can be done by invoking the API itself.

**Example**

You will be able to ask the Temperature control API for the device’s current temperature by calling the method `getCurrentTemperature`, which will give you the feature information, but only during the runtime of the device.

#### Legacy feature discovery

If the feature API doesn’t exist on the device, legacy feature detection can be used to search for the required feature as it combines all of the previously mentioned methods.

**Example**

Legacy features are exposed in the Legacy parameter handling API, where you must query the API Discovery service using the id `/axis-cgi/param.cgi`. Doing this will indicate the presence of the Legacy parameter handling API, which is used to discover features.

### Connection test: Ping, ports and IP addresses

The following examples will show you how to test your Ping or IP/port-address using the `/axis-cgi/pingtest.cgi` and `/axis-cgi/tcptest.cgi.`

**Ping**

To determine if your device is up and running and ready to ping another device or server on the network by searching for either its IP-address or the DNS-hostname, you should use the following URL:

```bash
http://<servername>/axis-cgi/pingtest.cgi?ip=ip-address
```

**Port**

To determine if your device is up and running and ready to reach another IP-address and port, i.e. test if the application itself is up and running on the server, you should use the following URL:

```bash
http://<servername>/axis-cgi/tcptest.cgi?address=ip-address&port=port
```