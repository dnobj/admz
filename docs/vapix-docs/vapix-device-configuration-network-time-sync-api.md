---
title: Network time synchronization configuration API
url: "https://developer.axis.com/vapix/device-configuration/network-time-sync-api/"
category: vapix
subcategory: device-configuration
sha256: 4de54a8cc043c8741c2fb3fba876e1e65886a295c9848310f44162134c8698d6
scraped_at: "2026-01-09T15:18:55.282Z"
page_height: 3164
---

# Network time synchronization configuration API

## Description

The VAPIX Network Time Synchronization Configuration API allows you to configure how the device uses network protocols to synchronize the system time. It manages NTP client settings and enables or disable NTP client configuration.

note

This API includes operations on sensitive data. You must use a secured channel for the communication transmissions.

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Manage NTP client settings

You can manage the NTP client settings using `network-time-sync.v2.ntp.client` entity. It returns the current NTP client configuration.

### Get NTP client configuration

Time synchronization is essential for network security, for example when validating certificates or maintaining accurate logs.

Example:

```bash
{    "request": {        "operation": "GET",        "path": "network-time-sync.v1.ntp.client"    },    "response": {        "status": "success",        "data": {            "advertisedServers": \["192.168.0.1", "192.168.2.1", "1234::55", "1234::66"\],            "enabled": true,            "maximumPoll": 10,            "minimumPoll": 6,            "serversSource": "DHCP",            "staticServers": \["192.168.0.1"\],            "synced": false,            "timeOffset": 0,            "timeToNextSync": 0        }    }}
```

#### Set NTP client configuration

To configure the NTP client, set `network-time-sync.v2.ntp.client`.

#### Disable NTP client configuration

To disable the NTP client, set `network-time-sync.v2.ntp.client` to `false`.

#### Enable NTP client configuration

To turn on the NTP client set the `network-time-sync.v2.ntp.client` to `true`, this is the default value.

Example:

```bash
{    "request": {        "operation": "SET",        "path": "network-time-sync.v1.ntp.client",        "data": {            "enabled": true,            "maximumPoll": 10,            "minimumPoll": 6,            "serversSource": "DHCP",            "staticServers": \["192.168.0.1"\]        }    },    "response": {        "status": "success"    }}
```

## API definition
### Structure
#### Objects
##### network-time-sync.v1.ntp

This entity contains properties for the NTP protocol.

##### network-time-sync.v1.ntp.client

This entity contains the client specific configuration settings for the NTP protocol, such as polling intervals, server sources, and synchronization status.