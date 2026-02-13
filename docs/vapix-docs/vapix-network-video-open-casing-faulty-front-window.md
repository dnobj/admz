---
title: Open Casing and Faulty Front Window
url: "https://developer.axis.com/vapix/network-video/open-casing-faulty-front-window/"
category: vapix
subcategory: network-video
sha256: 5d840497b445134c11491080f161337c1c2e5b30f6779e7263027c3821d9e1d4
scraped_at: "2026-01-09T15:20:29.817Z"
page_height: 3474
---

# Open Casing and Faulty Front Window

The VAPIX® Open Casing and Faulty Front Window API can be used on Axis devices that has the ability to detect if the casing or front window has been tampered with.

## Overview

The API consist of two events, one that activates when the device casing is opened and another when the window is tampered with.

### Identification

See [Event and action services](/vapix/network-video/event-and-action-services/) for a complete guide to events and to find out which ones that are supported by your device.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Events
### Open Casing event

Open casing events can be accessed through VAPIX and ONVIF event web service API:s and are useful when you want to be notified if a device casing has been opened.

The declaration for an open casing event from the VAPIX API would look like this:

```bash
<tns1:Device aev:NiceName="Device">    <tnsaxis:Casing aev:NiceName="Casing">        <Open wstop:topic="true" aev:NiceName="Casing Open">            <aev:MessageInstance aev:isProperty="true">                <aev:SourceInstance>                    <aev:SimpleItemInstance Type="xsd:string" Name="Name">                        <aev:Value>NetworkCamera</aev:Value>                    </aev:SimpleItemInstance>                </aev:SourceInstance>                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:boolean" Name="Open" isPropertyState="true"/>                </aev:DataInstance>            </aev:MessageInstance>        </Open>    </tnsaxis:Casing></tns1:Device>
```

| Parameter | Description |
| --- | --- |
| `Property=<Open>` | The lid state value.  
`<Open>`: An open casing has the value '1', while an inactive event has the value '0'. |
| `Property=<Name>` | The name of the affected device. Names can consist of a maximum of 32 characters.  
`<Name>`: Potential names include _JunctionBox_ for a junction box or _NetworkCamera_ for a network camera. |

It is possible to subscribe to events from the VAPIX/ONVIF event streams. The format of streams and its elements are described in [Schema](http://www.onvif.org/onvif/ver10/schema/onvif.xsd) and [Topics](http://www.onvif.org/onvif/ver10/topics/topicns.xml).

In VAPIX, the stream can be retrieved over RTSP with the following URL:

```bash
rtsp://<servername>/axismedia/media.amp?event=on&eventtopic=tns1:Device/Casing
```

### Faulty Front Window event

Faulty front window events can be accessed through VAPIX and ONVIF event web service API:s and are useful when you want to be notified if a device window has been removed, vandalized or otherwise malfunctioned.

The declaration for a faulty front window event from the VAPIX API would look like this:

```bash
<tns1:Device aev:NiceName="Device">    <tnsaxis:Window aev:NiceName="Window">        <Faulty wstop:topic="true" aev:NiceName="Faulty Front Window">            <aev:MessageInstance aev:isProperty="true">                <aev:SourceInstance>                    <aev:SimpleItemInstance Type="xsd:string" Name="Name">                        <aev:Value>Housing</aev:Value>                    </aev:SimpleItemInstance>                </aev:SourceInstance>                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:boolean" Name="Faulty" isPropertyState="true"/>                </aev:DataInstance>            </aev:MessageInstance>        </Faulty>    </tnsaxis:Window></tns1:Device>
```

| Parameter | Description |
| --- | --- |
| `Property=<Faulty>` | The window state value.  
`<Faulty>`: A malfunctioning window has the value '1', while an inactive event has the value '0'. |
| `Property=<Name>` | The name of the affected device. Names can consist of a maximum of 32 characters.  
`<Name>`: Potential name includes _Housing_ for a camera housing. |

It is possible to subscribe to events from the VAPIX/ONVIF event streams. The format of streams and its elements are described in [Schema](http://www.onvif.org/onvif/ver10/schema/onvif.xsd) and [Topics](http://www.onvif.org/onvif/ver10/topics/topicns.xml).

In VAPIX, the stream can be retrieved over RTSP with the following URL:

```bash
rtsp://<servername>/axismedia/media.amp?event=on&eventtopic=tns1:Device/Window
```