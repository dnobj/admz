---
title: Edge storage API
url: "https://developer.axis.com/vapix/network-video/edge-storage-api/"
category: vapix
subcategory: network-video
sha256: 82a16174fef85e419a32b557ba2f9efc800b6bd557eca813ec9c39a982b2ac14
scraped_at: "2026-01-09T15:19:37.157Z"
page_height: 176111
---

# Edge storage API

Edge storage is the capability to record and store video on the edge, for example on a network share or an SD card. Recording on the edge can reduce the load on the network in particular in large installations and in installations with wireless connections.

The Edge storage API consists of:

-   **Disk management API**: List, format, mount and lock disks. A disk can be an SD card or a network share. See [Disk management API](#disk-management-api).
-   **Disk properties API**: Set disk properties. See [Disk properties API](#disk-properties-api).
-   **Network share API**: Add, remove and manage network shares. See [Network share API](#network-share-api).
-   **Recording storage Limit API**: Control the amount of disk space a camera can use. See [Recording storage limit API](#recording-storage-limit-api).
-   **Recording API**: Configure, start, access and play recordings. See [Recording API](#recording-api).
-   **Export recording API**: Export a recording to a playable file. See [Export recording API](#export-recording-api).

The Recording API is used to start and stop continuous recordings. Axis products also support event-triggered and scheduled recordings. These are configured using [Event and action services](/vapix/network-video/event-and-action-services/).

See also [Edge storage events and actions](#edge-storage-events-and-actions).

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Using a network share

These examples demonstrate how to set up an Axis product to record continuously to a network share.

Add the network share "myshare" on the storage device "mynas". User name for the share is "nasuser" and password is "pass". The network share is given a user-friendly name "My Share".

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/add.cgi?schemaversion=1&nicename=My%20Share&address=mynas&share=myshare&user=nasuser&pass=pass"
```

```bash
GET /axis-cgi/disks/networkshare/add.cgi?schemaversion=1&nicename=My%20Share&address=mynas&share=myshare&user=nasuser&pass=passHost: <servername>
```

The share’s unique Share ID is returned in the response. Here, the returned Share ID is `35419`

Bind the network share to a disk. The disk is mounted automatically. The Share ID is from the `/axis-cgi/disks/networkshare/add.cgi` response above.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/bind.cgi?schemaversion=1&shareid=35419"
```

```bash
GET /axis-cgi/disks/networkshare/bind.cgi?schemaversion=1&shareid=35419Host: <servername>
```

The Disk ID of the disk to which the share is bound is returned in the response. Here, the returned Disk ID is `NetworkShare`.

Define the cleanup policy for the network share by modifying parameters in the appropriate `Storage` group. First, use `/axis-cgi/disks/list.cgi` to find the group number.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/list.cgi?diskid=NetworkShare"
```

```bash
GET /axis-cgi/disks/list.cgi?diskid=NetworkShareHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/disk/list1.xsd">  <disks numberofdisks="1">    <disk diskid="NetworkShare"      name="My Share"      totalsize="4194304000"      freesize="3355443200"      cleanuplevel="95"      cleanupmaxage="1"      cleanuppolicy="none"      locked="no"      full="no"      readonly="no"      filesystem="cifs"      status="OK"      group="S1"      requiredfilesystem="none"/>  </disks></root>
```

As seen from the response, the disk to which the network share is bound is described by the parameters in the `Storage.S1` group. Modify the parameters so that recordings are kept for 7 days.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Storage.S1.CleanupPolicyActive=fifo&Storage.S1.CleanupMaxAge=7"
```

```bash
GET /axis-cgi/param.cgi?action=update&Storage.S1.CleanupPolicyActive=fifo&Storage.S1.CleanupMaxAge=7Host: <servername>
```

Add a configuration for a continuous recording to the network share.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/continuous/addconfiguration.cgi?diskid=NetworkShare&eventid=continuous\_nas&options=resolution%3D640x480"
```

```bash
GET /axis-cgi/record/continuous/addconfiguration.cgi?diskid=NetworkShare&eventid=continuous\_nas&options=resolution%3D640x480Host: <servername>
```

Play the continuous recording from 2011–08–12T08:12:11Z to 2011–08–14T10:10:00Z. To make sure that all recorded material from this time period is played, also if the recording was interrupted, the recordings are first listed. The play request is then a loop over the found recordings.

First, list recordings with `eventid=continuous_nas` from the desired time period.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/list.cgi?listentity=recordingid&eventid=continuous\_nas&starttime=2011-08-12T08:12:11Z&&stoptime=2011-08-14T10:10:00Z"
```

```bash
GET /axis-cgi/record/list.cgi?listentity=recordingid&eventid=continuous\_nas&starttime=2011-08-12T08:12:11Z&&stoptime=2011-08-14T10:10:00ZHost: <servername>
```

The response below shows that the continuous recording was interrupted twice during the requested time period. A recording can for example be interrupted if the Axis product is restarted or if network connection is lost. The response contains information such as the Recording IDs, start and stop times of the three recordings found during the requested time period. Only a part of the response is shown here.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/list1.xsd">  <recordings totalnumberofrecordings="6" numberofrecordings="3" >    <recording diskid="NetworkShare"      recordingid="20110812\_081211\_016F\_00408C1834FD"      starttime="2011-08-12T08:12:11Z"      stoptime="2011-08-13T09:30:30Z" ... >      <video ... />      <audio ... />    </recording>    <recording diskid="NetworkShare"      recordingid="20110813\_093530\_025B\_00408C1834FD"      starttime="2011-08-13T09:35:30Z"      stoptime="2011-08-13T010:30:30Z" ... >      <video ... />      <audio ... />    </recording>    <recording diskid="NetworkShare"      recordingid="20110813\_103530\_037C\_00408C1834FD"      starttime="2011-08-13T010:35:30Z"      stoptime="2011-08-14T10:10:00Z" ... >      <video ... />      <audio ... />    </recording>  </recordings></root>
```

To play the recordings, use the Recording IDs, start times and stop times from the response. The start and stop times are returned in UTC combined date and time format and must be converted before being used in the RTSP `Range` header. For example, `starttime="2011-08-12T08:12:11Z"` should be converted to `20110812T081211Z`. See [Date and time format](#date-and-time-format) for more information.

The play request below is to be inserted in a loop over the recordings from the response; `Rec.recordingid` is replaced with each of the three returned Recording IDs and _Rec.starttime_ and _Rec.stoptime_ are replaced with the returned start and stop times (converted to the proper time format).

```bash
PLAY rtsp://<servername>/axis-media/media.amp?recordingid=Rec.recordingidRange: clock=Rec.starttime-Rec.stoptime
```

### Using an SD card

These examples demonstrate how to use an SD card with an Axis product.

Set friendly name for storage 0 to "My SD card".

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Storage.S0.FriendlyName=My&20SD%20Card"
```

```bash
GET /axis-cgi/param.cgi?action=update&Storage.S0.FriendlyName=My&20SD%20CardHost: <servername>
```

List the file systems supported by the SD card.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/getcapabilities.cgi?diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/getcapabilities.cgi?diskid=SD\_DISKHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/disk/capabilities1.xsd">  <disk diskid="SD\_DISK" requiredfssupported="true">    <filesystems>      <filesystem name="vfat" nicename=" " requiredfssupported="false"/>      <filesystem name="ext4" nicename=" " requiredfssupported="true"/>    </filesystems>  </disk></root>
```

Format the SD card with `ext4`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/format.cgi?diskid=SD\_DISK&filesystem=ext4"
```

```bash
GET /axis-cgi/disks/format.cgi?diskid=SD\_DISK&filesystem=ext4Host: <servername>
```

The response gives the Job ID of the started job. Here, the returned Job ID is `4`.

Check the progress of the format job with `jobid=4`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/job.cgi?jobid=4&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/job.cgi?jobid=4&diskid=SD\_DISKHost: <servername>
```

The response below shows that the format job is in progress, 15% of the job is done.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/disk/checkjob1.xsd">  <job jobid="4"    diskid="SD\_DISK"    action="format"    result="OK"    progress="15"</root>
```

By running `/axis-cgi/disks/job.cgi` repeatedly, the progress of the job can be reported by showing incremental updates, for example:

```bash
15%32%45%68%92%Done!
```

Add a configuration for a continuous recording to the SD card.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/continuous/addconfiguration.cgi?diskid=SD\_DISK&options=resolution%3D640x480&eventid=continuous\_0"
```

```bash
GET /axis-cgi/record/continuous/addconfiguration.cgi?diskid=SD\_DISK&options=resolution%3D640x480&eventid=continuous\_0Host: <servername>
```

## Disk management API
### Description

Disks are removable storage devices such as SD cards and network shares. The Disk management API is used to manage disks, for example to list, format, mount and lock disks.

info

If using a network share, the share must first be added and bound to the disk using the Network Share API, see [Network share API](#network-share-api).

A disk is identified by its **Disk ID**. The Disk ID identifies a disk drive and not the physical disk, that is, the Disk ID does not change if the SD card or network share is replaced. For example, consider a network share with Disk ID `NetworkShare`. If the network share is unbound and replaced with a new one, the new share is also associated with the Disk ID `NetworkShare`.

The Disk management API consists of the following CGIs:

| Name | Description |
| --- | --- |
| `/axis-cgi/disks/list.cgi` | Retrieve information about available disks. An available disk is mounted and ready to be used. |
| `/axis-cgi/disks/format.cgi` | Format the disk. SD cards can be formatted with `ext4` or `vfat`. Formatting a network share removes all recordings made by the Axis product performing the operation. |
| `/axis-cgi/disks/checkdisk.cgi` | Check the status of a disk. |
| `/axis-cgi/disks/repair.cgi` | Repair the file system on a disk. |
| `/axis-cgi/disks/mount.cgi` | Mount or unmount a disk. Mounting is done automatically when the system boots, when an SD card is inserted and when a network share is bound. |
| `/axis-cgi/disks/job.cgi` | Check the progress of a format, check disk, repair, mount or unmount job. Typically used repeatedly until the job is done. |
| `/axis-cgi/disks/lock.cgi` | Lock or unlock a disk. A locked disk cannot be formatted or written to. Ongoing recordings will be stopped if the disk is locked. |
| `/axis-cgi/disks/getcapabilities.cgi` | Retrieve the capabilities supported by the disk, for example the file systems the disk can be formatted with, if required file system is supported and if disk encryption is supported. |
| `/axis-cgi/disks/gethealth.cgi` | List the health status (wear level, temperature and overall health) of all disks. |

The responses from `/axis-cgi/disks/format.cgi`, `/axis-cgi/disks/checkdisk.cgi`, `/axis-cgi/disks/repair.cgi` and `/axis-cgi/disks/mount.cgi` show if the job has been started or not. A successfully started job returns a **Job ID**, which should be used as input to `/axis-cgi/disks/job.cgi`. Typically, `/axis-cgi/disks/job.cgi` is run repeatedly until the job is finished. This workflow allows a user interface to be more responsive and to report the progress of a job by displaying incremental status updates, for example in a progress bar.

### Prerequisites
#### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.LocalStorage.LocalStorage=yes`
-   **Property**: `Properties.LocalStorage.Version=1.00`
-   **AXIS OS**: 5.40 and later

#### Obsoletes

Parameter `CleanupLevel` is obsolete in AXIS OS 5.50 and later. The parameter is replaced by an internal, fixed value.

### Common examples

Set friendly name for storage 0 to "My SD Card".

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/param.cgi?action=update&Storage.S0.FriendlyName=My&20SD%20Card"
```

```bash
GET /axis-cgi/param.cgi?action=update&Storage.S0.FriendlyName=My&20SD%20CardHost: <servername>
```

Get a list of all disks.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/list.cgi?diskid=all"
```

```bash
GET /axis-cgi/disks/list.cgi?diskid=allHost: <servername>
```

The response displays information about the disks.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/disk/list1.xsd">  <disks numberofdisks="2">    <disk diskid="SD\_DISK"      name="My SD Card"      totalsize="2097152"      freesize="2097152"      cleanuplevel="95"      cleanupmaxage="1"      cleanuppolicy="none"      locked="no"      full="no"      readonly="no"      filesystem="vfat"      status="OK"      group="S0"      requiredfilesystem="none"      diskencryptionenabled="false"      diskencrypted="false"/>    <disk diskid="NetworkShare"      name="My Share"      totalsize="4194304000"      freesize="3670016000"      cleanuplevel="95"      cleanupmaxage="1"      cleanuppolicy="none"      locked="no"      full="no"      readonly="no"      filesystem="cifs"      status="OK"      group="S1"      requiredfilesystem="none"      diskencryptionenabled="false"      diskencrypted="false"/>  </disks></root>
```

Unmount a network share.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/mount.cgi?action=unmount&diskid=NetworkShare"
```

```bash
GET /axis-cgi/disks/mount.cgi?action=unmount&diskid=NetworkShareHost: <servername>
```

The response gives the Job ID of the started job. Here, the returned Job ID is `3`.

List the file systems supported by the SD card.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/getcapabilities.cgi?diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/getcapabilities.cgi?diskid=SD\_DISKHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/disk/capabilities1.xsd">  <disk diskid="SD\_DISK" requiredfssupported="true" encryptionsupported="true">    <filesystems>      <filesystem name="vfat" nicename=" " requiredfssupported="false"/>      <filesystem name="ext4" nicename=" " requiredfssupported="true"/>    </filesystems>  </disk></root>
```

Format the SD card with `ext4`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/format.cgi?diskid=SD\_DISK&filesystem=ext4"
```

```bash
GET /axis-cgi/disks/format.cgi?diskid=SD\_DISK&filesystem=ext4Host: <servername>
```

The response gives the Job ID of the started job. Here, the returned Job ID is `4`.

Check the progress of the format job with `jobid=4`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/job.cgi?jobid=4&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/job.cgi?jobid=4&diskid=SD\_DISKHost: <servername>
```

The response below shows that the format job is in progress, 15% of the job is done.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/disk/checkjob1.xsd">  <job jobid="4"    diskid="SD\_DISK"    action="format"    result="OK"    progress="15"</root>
```

By running `/axis-cgi/disks/job.cgi` repeatedly, the progress of the job can be reported by showing incremental updates, for example:

```bash
15%32%45%68%92%Done!
```

Get the wear level for all disks.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/gethealth.cgi"
```

```bash
GET /axis-cgi/disks/gethealth.cgiHost: <servername>
```

Response

```bash
<?xml version="1.0" encoding="UTF-8" ?><HealthStatusResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/gethealth1.xsd">    <HealthStatusSuccess>        <HealthStatus diskid="SD\_DISK" wear="25" />        <HealthStatus diskid="NetworkShare" wear="-1" />        <HealthStatus diskid="HDD\_DISK" wear="13" temperature="315" overallhealth="1" />    </HealthStatusSuccess></HealthStatusResponse>
```

Check if an SD card is an Axis SD card.

-   If the `wear` value is 0 or positive, it is an Axis SD card.
-   If the `wear` value is negative, it is not an Axis SD card.

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/gethealth.cgi"
```

```bash
GET /axis-cgi/disks/gethealth.cgiHost: <servername>
```

Response

```bash
<?xml version="1.0" encoding="UTF-8" ?><HealthStatusResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/gethealth1.xsd">    <HealthStatusSuccess>        <HealthStatus diskid="SD\_DISK" wear="3" />        <HealthStatus diskid="NetworkShare" wear="-3" />        <HealthStatus diskid="EMMC" wear="0" overallhealth="1" />    </HealthStatusSuccess></HealthStatusResponse>
```

### Parameters

**Storage properties parameters**

The parameters in the `Properties.LocalStorage` group identify the storage capabilities supported by the Axis product.

Properties.LocalStorage

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `LocalStorage` | Product dependent | `yes` `no` | admin: read operator: read viewer: read | `yes` = Storage is supported. `no` = Storage is not supported. |
| `Version` | AXIS OS dependent | Integer | admin: read operator: read viewer: read | Specifies the version of the Disk Management API. |
| `SDCard` | Product dependent | `yes` `no` | admin: read operator: read viewer: read | `yes` = SD cards are supported. `no` = SD cards are not supported. |
| `ContinuousRecording` | Product dependent | `yes` `no` | admin: read operator: read viewer: read | `yes` = The product supports continuous recording profiles. Use `/axis-cgi/record/continuous/addconfiguration.cgi` to add a continuous recording configuration. `no` = The product does not support continuous recording profiles. Use `/axis-cgi/record/record.cgi` to start a continuous recording. |
| `NbrOfContinuousRecordingProfiles` | Product dependent | Integer | admin: read operator: read viewer: read | Specifies the number of continuous recording profiles. |

**Mount directory parameters**

Storage

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `MountDir` | `/var/spool/storage` | `/var/spool/storage` | admin: read operator: read | Mount directory. Read-only. |

**Storage parameters**

The parameters in the `Storage` group are used for disk management.

Storage.S#

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `DiskID` | Storage dependent | String | admin: read operator: read | The Disk ID. Read only. |
| `FriendlyName` |  | String | admin: read, write operator: read, write | A user friendly name for the disk. This name can for example be displayed on a web page. |
| `DeviceNode` | Storage dependent | String | admin: read, write operator: read | Valid values depends on what kind of storage that is used. |
| `CleanupLevel` | `95` | `0...99` | admin: read, write operator: read | Obsolete in AXIS OS 5.50 and later. Cleanup level in percent of the total disk space. The oldest parts of unlocked recordings will be deleted when the used disk space (in percent of total disk space) exceeds the cleanup level. Used in combination with `CleanupPolicyActive=fifo`. |
| `CleanupMaxAge` | `1` | `0...7000` | admin: read, write operator: read | Maximum number of days that unlocked recordings are kept on the disk. Recording parts that are older than the specified number of days will be deleted. Used in combination with `CleanupPolicyActive=fifo`. Note: Recordings will be deleted earlier if the disk becomes full. |
| `CleanupPolicyActive` | `fifo` | `fifo` `none` | admin: read, write operator: read | `fifo` = (first in, first out) Recordings are automatically deleted according to the rules specified by `CleanupMaxAge`. `none` = Recordings must be deleted manually. No recordings are deleted by the system. |
| `FileSystem` | Storage dependent | `ext4` `vfat` `cifs` | admin: read, write operator: read | Current file system on the storage device. Valid values are storage dependent. Read only. |
| `Locked` | `no` | `yes` `no` | admin: read, write operator: read | `yes` = The disk is locked and cannot be written to. `no` = The disk is unlocked. |
| `MountOnBoot` | `yes` | `yes` `no` | admin: read, write operator: read | `yes` = The disk is mounted on boot. `no` = The disk is not mounted on boot. A manual mount is required. |
| `RequiredFileSystem` | `none` | `none` `ext4` | admin: read, write operator: read | `none` = Required file system is disabled. `ext4` = Required file system is set to `ext4`. Note: To check if required file system is supported by the disk, use `/axis-cgi/disks/getcapabilities.cgi`. |
| `AutoRepair` | `yes` | `yes` `no` | admin: read, write operator: read | `yes`\= The file system is checked for errors before mounting and will be repaired if it is required. No check will be performed if the disk is locked. `no`\= The file system is not checked. |
| `MountPointPermissions` | `0770` | String | admin: read, write operator: read, write | The file permissions, which are used to set the mount point, in the form of a string. This has only an effect on volumes with an ext4 file system. |
| `Enabled` | `yes` | `yes` `no` | admin: read, write operator: read | `yes` = The disk is enabled. `no` = The disk is disabled, which means that it can’t be used, e.g. mounted. You must restart your device after changing this parameter before the change can begin to take effect. |
| `ExtraMountOptions` |  | String | admin: read, write operator: read | The additional mount options. For example, use `vers=3.0` to specify the SMB version. |

info

The # is replaced by a group number, for example Storage.S0. The group number is an integer between 0 and N, where N is the number of disks supported by the Axis product.

### List disks

Use `/axis-cgi/disks/list.cgi` to retrieve information about available disks and their status. An available disk is formatted, mounted and ready to be used.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/list.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/list.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `diskid=<string>` | `all` `<Disk ID 1>`, `<Disk ID 2>`, ... | Specify the Disk IDs of the disks to retrieve information about. `all`\= List all disks. `<Disk ID 1>`, `<Disk ID 2>` = List the disks with the specified Disk IDs. |

**Response**

Responses from `/axis-cgi/disks/list.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/list1.xsd">    <disks numberofdisks="\[number of disks returned in xml\]">        <disk            diskid="\[storage parameter DiskID\]"            name="\[storage parameter FriendlyName\]"            totalsize="\[total size of storage in kB\]"            freesize="\[free space of storage in kB\]"            cleanuplevel="\[storage parameter CleanupLevel\]"            cleanupmaxage="\[storage parameter CleanupMaxAge\]"            cleanuppolicy="\[storage parameter CleanupPolicyActive\]"            locked="\[storage parameter Locked\]"            full="\[storage full\]"            readonly="\[storage read only\]"            filesystem="\[file system of storage\]"            status="\[disk status\]"            group="\[storage group\]"            requiredfilesystem="\[required file system\]"            diskencryptionenabled="\[true | false\]"            diskencrypted="\[true | false\]" />    </disks></root>
```

info

In the `/axis-cgi/disks/list.cgi` response, some elements contain yes/no and some contain true/false.

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `disks` | The available disks | `numberofdisks` | Number of disks in the response. |
| `disk` | Information about the disk | `diskid` | The Disk ID. |
|  |  | `name` | User-friendly disk name. |
|  |  | `totalsize` | Total disk size in kilobytes (kB). |
|  |  | `freesize` | Free disk size in kilobytes (kB). |
|  |  | `cleanuplevel` | Obsolete in AXIS OS 5.50 and later. Cleanup level in percent of total disk space. |
|  |  | `cleanupmaxage` | Maximum number of days that unlocked recordings are kept on the disk. Recording parts that are older than the specified number of days will be deleted.Note: Recordings will be deleted earlier if the disk becomes full. |
|  |  | `cleanuppolicy` | `fifo` = (first in, first out). Recordings are automatically deleted after the number of days specified by `cleanupmaxage`.`none` = Recordings are not deleted automatically. Must be deleted manually. |
|  |  | `locked` | The disk is locked or unlocked. `yes` = Disk is locked. `no` = Disk is unlocked. |
|  |  | `full` | The disk is full or not. `yes` = Disk is full. `no` = Disk is not full. |
|  |  | `readonly` | The disk is read-only or not. `yes` = Disk is read-only. `no` = Disk is writable. |
|  |  | `filesystem` | Value of parameter `FileSystem`. |
|  |  | `status` | Disk status. Possible values are:`disconnected` = The disk is disconnected.`connected` = The disk is connected but not mounted.`OK` = The disk is working correctly.`failed` = A problem has been discovered. Use `/axis-cgi/disks/checkdisk.cgi` to find the problem.`no passphrase` = Encryption is disabled but the disk is encrypted. Format the disk before use.`wrong passphrase` = The disk is encrypted but the entered passphrase does not match the set passphrase. Set the correct passphrase before use.`not encrypted` = Encryption is enabled. The disk is not encrypted and not mounted. Format and mount the disk before use. |
|  |  | `group` | The parameter group `Storage.S#` defining the disk. |
|  |  | `requiredfilesystem` | The file system set as required file system. To change required file system, use `/axis-cgi/disks/properties/setrequiredfs.cgi`.`none` = Required file system is not set. |
|  |  | `diskencryptionenabled` | `true` = Disk encryption is enabled.`false` = Disk encryption is disabled. |
|  |  | `diskencrypted` | `true` = The disk content is encrypted. Disk content is encrypted when disk encryption is enabled and the disk has been mounted and formatted.`false` = The disk content is not encrypted. Disk content is not encrypted when disk encryption is disabled, or when disk encryption is enabled but the disk has not yet been mounted and formatted. |

### Format disk

Use `/axis-cgi/disks/format.cgi` format disks. Disks are normally preformatted but can be reformatted with a different file system.

info

Any data present on the disk is lost when the disk is formatted.

The response shows if the job has been started or not. A successfully started job returns a **Job ID**, which should be used as input to `/axis-cgi/disks/job.cgi`, see [Job progress](#job-progress-disk-management-api).

SD cards can be formatted with `ext4` or `vfat`. Using `ext4` is recommended to reduce the risk of data loss if the card is ejected and after abrupt power cycling. To read SD cards formatted with `ext4` on Windows, additional software is needed.

To format a network share, set the argument `filesystem` to `cifs`. Formatting a network share removes all data recorded to the share by the Axis product performing the operation. Data uploaded to a network share recipient and recordings made by other Axis products are not removed.

Use `/axis-cgi/disks/getcapabilities.cgi` to retrieve the file systems that the disk can be formatted with.

If required file system has been set, the disk is formatted automatically when mounted. See [Set required file system](#set-required-file-system).

If disk encryption is enabled, the disk is encrypted when formatted. See [Enable disk encryption](#enable-disk-encryption).

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/format.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/format.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `diskid=<string>` | `<Disk ID>` | Required. Specify the Disk ID of the disk to format. |
| `filesystem=<string>` | `ext4` `vfat` `cifs` | Specify the file system to format the disk with. Available values depend on the disk and can be retrieved using `/axis-cgi/disks/getcapabilities.cgi` Default: The file system present on the disk. |

**Response**

Responses from `/axis-cgi/disks/format.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">    <job action="format" diskid="\[Disk ID\]" result="OK" jobid="\[ID of the started job\]" /></root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">    <job action="format" diskid="\[Disk ID\]" result="ERROR" description="\[error description\]" /></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `job` | Information about the job | `action="format"` | The requested action: format |
|  |  | `diskid` | The Disk ID. |
|  |  | `result` | Result of the request. `OK` = The format job was started successfully. `ERROR` = The format job could not be started. |
|  |  | `jobid` | Job ID. |
|  |  | `description` | Error description. |

### Check disk

Use `/axis-cgi/disks/checkdisk.cgi` to check the integrity of the file system. If an error is found, try using `/axis-cgi/disks/repair.cgi` to repair the file system.

The response shows if the job has been started or not. A successfully started job returns a **Job ID**, which should be used as input to `/axis-cgi/disks/job.cgi`, see [Job progress](#job-progress-disk-management-api).

info

Only SD cards formatted with ext4 can be checked using this CGI.

The request fails if the disk is mounted or if disk encryption is enabled without a valid passphrase.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/checkdisk.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/checkdisk.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `diskid=<string>` | `<Disk ID>` | Required. The Disk ID of the disk to be checked. |

**Response**

Responses from `/axis-cgi/disks/checkdisk.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">    <job action="checkdisk" diskid="\[Disk ID\]" result="OK" jobid="\[ID of the started job\]" /></root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">    <job action="checkdisk" diskid="\[Disk ID\]" result="ERROR" description="\[error description\]" /></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `job` | Information about the job. | `action="checkdisk"` | The requested action: check disk |
|  |  | `diskid` | The Disk ID. |
|  |  | `result` | Result of the request. `OK` = The check disk job was started successfully. `ERROR` = The disk could not be checked. |
|  |  | `jobid` | The Job ID. |
|  |  | `description` | Error description. |

### Repair disk

Use `/axis-cgi/disks/repair.cgi` to perform a file system repair on the selected disk.

info

Repairing a disk may result in lost data.

The response shows if the job has been started or not. A successfully started job returns a **Job ID**, which should be used as input to `/axis-cgi/disks/job.cgi`, see [Job progress](#job-progress-disk-management-api).

info

Only SD cards formatted with ext4 can be repaired using this CGI.

The request fails if the disk is mounted or if disk encryption is enabled without a valid passphrase.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/repair.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/repair.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `diskid=<string>` | `<Disk ID>` | The Disk ID of the disk to be repaired. Required. |

**Response**

Responses from `/axis-cgi/disks/repair.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">    <job action="repair" diskid="\[Disk ID\]" result="OK" jobid="\[ID of the started job\]" /></root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">    <job action="repair" diskid="\[Disk ID\]" result="ERROR" description="\[error description\]" /></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `job` | Information about the job. | `action="repair"` | The requested action: repair |
|  |  | `diskid` | The Disk ID. |
|  |  | `result` | Result of the request. `OK` = The repair job was started successfully. `ERROR` = The repair job could not be started. |
|  |  | `jobid` | The Job ID. |
|  |  | `description` | Error description. |

### Mount and unmount a disk

Use `/axis-cgi/disks/mount.cgi` to mount a disk to the system and to unmount a disk from the system.

info

To prevent corruption of recordings, SD cards should always be unmounted before being ejected.

The response shows if the job has been started or not. A successfully started job returns a **Job ID**, which should be used as input to `/axis-cgi/disks/job.cgi`, see [Job progress](#job-progress-disk-management-api).

Mounting is done automatically:

-   when an SD card is inserted
-   when a network share is bound to a disk
-   when the system boots (provided that an SD is inserted or a network share has been bound)

A manual mount is only required if a disk has been unmounted and not automatically remounted (for example by a system restart).

Unmounting makes the disk unavailable to the system. A disk that has been unmounted can be safely removed from the product.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/mount.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/mount.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `action=<string>` | `mount` `unmount` | Required. Specify the action to perform. `mount` = Mount the disk. `unmount`\= Unmount the disk. |
| `diskid=<string>` | `<Disk ID>` | Required. Specify the Disk ID of the disk to be mounted or unmounted. |

**Response**

Responses from `/axis-cgi/disks/mount.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">    <job action="\[requested action\]" diskid="\[Disk ID\]" result="OK" jobid="\[ID of the started job\]" /></root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">    <job action="\[requested action\]" diskid="\[Disk ID\]" result="ERROR" description="\[error description\]" /></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `job` | Information about the job. | `action` | The requested action: `mount` `unmount` |
|  |  | `diskid` | The Disk ID. |
|  |  | `result` | Result of the request. `OK` = The job was started successfully `ERROR` = The job could not be started. |
|  |  | `jobid` | The Job ID. |
|  |  | `description` | Error description. |

### Job progress

Use `/axis-cgi/disks/job.cgi` to check the progress of a format, check disk, repair, mount or unmount job.

The job should be started by running one of `/axis-cgi/disks/format.cgi`, `/axis-cgi/disks/checkdisk.cgi`, `/axis-cgi/disks/repair.cgi` and `/axis-cgi/disks/mount.cgi`. If the job could be started successfully, a Job ID is returned. This Job ID is used as input to `/axis-cgi/disks/job.cgi`. Typically, `/axis-cgi/disks/job.cgi` is run repeatedly until the job is finished. This workflow allows a user interface to be more responsive and to report the progress of a job by displaying incremental status updates, for example in a progress bar.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/job.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/job.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `jobid=<integer>` | `<Job ID>` | Required. The ID of the job to check. |
| `diskid=<string>` | `<Disk ID>` | Required. The Disk ID of the disk to check. |

**Response**

Responses from `/axis-cgi/disks/job.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/checkjob1.xsd">    <job        jobid="\[ID of the started job\]"        diskid="\[Disk ID\]"        action="\[requested action\]"        result="OK"        progress="\[percentage done\]"        description="\[result description\]" /></root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/checkjob1.xsd">    <job        jobid="\[ID of the started job\]"        diskid="\[Disk ID\]"        action="\[current action\]"        progress="100"        result="ERROR"        description="\[error description\]" /></root>
```

Supported attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `job` | Contains the result or progress of the job. | `jobid` | The Job ID. |
|  |  | `diskid` | The Disk ID. |
|  |  | `action` | The requested job: `format` = Format the disk. `checkdisk` = Check disk. `repair` = Repair the disk. `mount` = Mount the disk. `unmount` = Unmount the disk. `N/A` = Not applicable. |
|  |  | `progress` | Progress in percent. |
|  |  | `result` | Result of the request. `OK` = The job is in progress or is finished successfully. `ERROR` = An error was found. |
|  |  | `description` | Description of the result or the error. |

### Lock or unlock a disk

Use `/axis-cgi/disks/lock.cgi` to lock or unlock a disk. When locked, all active recording are stopped and saved recordings cannot be removed. A locked disk cannot be formatted or written to.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/lock.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/lock.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `action=<string>` | `lock` `unlock` | Required. The action to perform. `lock` = Lock the disk. `unlock` = Unlock the disk. |
| `diskid=<string>` | `<Disk ID>` | Required. The Disk ID of the disk to be locked or unlocked. |

**Response**

Responses from `/axis-cgi/disks/lock.cgi`

**Return:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/lock1.xsd">    <lock diskid="\[Disk ID\]" result="OK" /></root>
```

or

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/lock1.xsd">    <unlock diskid="\[Disk ID\]" result="OK" /></root>
```

Supported attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `lock` | The requested action: lock | `diskid` | The Disk ID |
|  |  | `result` | `OK` = The disk was locked successfully |
| `unlock` | The requested action: unlock | `diskid` | The Disk ID |
|  |  | `result` | `OK` = The disk was unlocked successfully |

### Get disk capabilities

Use `/axis-cgi/disks/getcapabilities.cgi` to list the capabilities supported by the disk. The response shows the file systems that the disk can be formatted with, if required file system is supported and if disk encryption is supported.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/getcapabilities.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/getcapabilities.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `diskid=<string>` | `<Disk ID>` | Required. The Disk ID. |

**Response**

Responses from `/axis-cgi/disks/getcapabilities.cgi`

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/capabilities1.xsd">    <disk diskid="\[Disk ID\]" requiredfssupported="\[true | false\]" encryptionsupported="\[true | false\]">        <filesystems>            <filesystem name="\[filesystem 1\]" nicename="\[filesystem 1\]" requiredfssupported="\[true | false\]" />            <filesystem name="\[filesystem 2\]" nicename="\[filesystem 2\]" requiredfssupported="\[true | false\]" />            ...        </filesystems>    </disk></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `disk` | Contains information about the disk | `diskid` | The Disk ID |
|  |  | `requiredfssupported` | `true` = The disk supports required file system.`false` = The disk does not support required file system. |
|  |  | `encryptionsupported` | `true` = The disk supports disk encryption.`false` = The disk does not support disk encryption. |
| `filesystems` | Lists all file systems that the disk can be formatted with. |  |  |
| `filesystem` | Contains information about one file system | `name` | File system name |
|  |  | `nicename` | Descriptive name of the file system. |
|  |  | `requiredfssupported` | `true` = The file system can be used as required file system.`false` = The file system cannot be used as required file system. |

### Get disk health

Use `/axis-cgi/disks/gethealth.cgi` to list the health status (wear level, temperature and overall health) of all disks.

**Note:** Requires AXIS OS 7.20 and later.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: GET

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/gethealth.cgi"
```

```bash
GET /axis-cgi/disks/gethealth.cgiHost: <servername>
```

**Response**

-   **HTTP code**: 200 OK
-   **Content-Type**: `text/xml`

Success

```bash
<?xml version="1.0" encoding="UTF-8" ?><HealthStatusResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/gethealth1.xsd">    <HealthStatusSuccess>        <HealthStatus diskid="SD\_DISK" wear="25" />        <HealthStatus diskid="NetworkShare" wear="-1" />        <HealthStatus diskid="HDD\_DISK" wear="13" temperature="315" overallhealth="1" />    </HealthStatusSuccess></HealthStatusResponse>
```

The `wear` attribute value shows how much of the disk's expected life span (in percent) that has passed. The value can exceed 100 percent.

The `temperature` attribute value shows the disk temperature in Kelvin degrees (315 degrees Kelvin = 42 degrees Celsius). **Note:** AXIS OS 9.50 and later.

The `overallhealth` attribute value shows the overall health status for the device (0 = FAIL, 1 = PASSED). **Note:** AXIS OS 9.50 and later.

Wear level is only supported on an Axis SD card. If the `wear` value is 0 or positive, it means it is an Axis SD card. If the `wear` value is negative, it means it is not an Axis SD card.

The Health Status attributes can also have one of the following negative values: `-1` means that the feature is not supported for the disk, `-2` means that an error occured, `-3` means that the disk is not present.

Error

```bash
<?xml version="1.0" ?><HealthStatusResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/gethealth1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></HealthStatusResponse>
```

Possible values for the ErrorCode element:

| Error code | Description |
| --- | --- |
| 10 | An error occurred while processing the request. |

## Disk properties API
### Description

VAPIX® Disk properties API is used to configure various disk properties. The API consists of the following CGIs:

| Name | Description |
| --- | --- |
| `/axis-cgi/disks/properties/setrequiredfs.cgi` | Enable and set required file system. Required file system is used to automatically format SD cards. See [Set required file system](#set-required-file-system). |
| `/axis-cgi/disks/properties/enablediskencryption.cgi` | Enable disk encryption. Disk encryption is used to encrypt the SD card content in order to prevent unauthorized systems and individuals to access recorded video. See [Enable disk encryption](#enable-disk-encryption). |
| `/axis-cgi/disks/properties/disablediskencryption.cgi` | Disable disk encryption. See [Disable disk encryption](#disable-disk-encryption). |
| `/axis-cgi/disks/properties/changediskpassphrase.cgi` | Change the disk encryption passphrase. See [Change disk encryption passphrase](#change-disk-encryption-passphrase). |
| `/axis-cgi/disks/properties/schemaversions.cgi` | Retrieve a list of supported versions of the XML schema for the Disk Properties API. |

### Prerequisites
#### Identification

Required file system is supported if

-   **Property**: `Properties.LocalStorage.RequiredFileSystem=yes`

Disk encryption is supported if

-   **Property**: `Properties.LocalStorage.DiskEncryption=yes`

### Required file system

Check if required file system has been set.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/list.cgi?diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/list.cgi?diskid=SD\_DISKHost: <servername>
```

The response shows that required file system is disabled.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/disk/list1.xsd">  <disks numberofdisks="1">    <disk diskid="SD\_DISK"      name="My SD Card"      totalsize="2097152"      freesize="2097152"      cleanuplevel="95"      cleanupmaxage="1"      cleanuppolicy="none"      locked="no"      full="no"      readonly="no"      filesystem="vfat"      status="OK"      group="S0"      requiredfilesystem="none"      diskencryptionenabled="false"      diskencrypted="false"/>  </disks></root>
```

Check if the disk supports required file system.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/getcapabilities.cgi?diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/getcapabilities.cgi?diskid=SD\_DISKHost: <servername>
```

The response shows that required file system is supported and that `ext4` can be used as required file system.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/disk/capabilities1.xsd">  <disk diskid="SD\_DISK" requiredfssupported="true" encryptionsupported="true">    <filesystems>      <filesystem name="vfat" nicename=" " requiredfssupported="false"/>      <filesystem name="ext4" nicename=" " requiredfssupported="true"/>    </filesystems>  </disk></root>
```

Set required file system to `ext4`.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/setrequiredfs.cgi?schemaversion=1&diskid=SD\_DISK&filesystem=ext4"
```

```bash
GET /axis-cgi/disks/properties/setrequiredfs.cgi?schemaversion=1&diskid=SD\_DISK&filesystem=ext4Host: <servername>
```

Disable required file system.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/setrequiredfs.cgi?schemaversion=1&diskid=SD\_DISK&filesystem=none"
```

```bash
GET /axis-cgi/disks/properties/setrequiredfs.cgi?schemaversion=1&diskid=SD\_DISK&filesystem=noneHost: <servername>
```

### Disk encryption

Check if the disk supports disk encryption.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/getcapabilities.cgi?diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/getcapabilities.cgi?diskid=SD\_DISKHost: <servername>
```

The response shows that disk encryption is supported.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/capabilities1.xsd">  <disk diskid="SD\_DISK" requiredfssupported="true" encryptionsupported="true">    <filesystems>      <filesystem name="vfat" nicename=" " requiredfssupported="false"/>      <filesystem name="ext4" nicename=" " requiredfssupported="true"/>    </filesystems>  </disk></root>
```

Enable disk encryption. Before disk encryption can be enabled, the disk must be unmounted. After enabling disk encryption the disk must be formatted and mounted before it can be used. If required file system is set, the disk is formatted automatically.

Unmount the SD card. For detailed information about the request, see [Mount and unmount a disk](#mount-and-unmount-a-disk).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/mount.cgi?action=unmount&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/mount.cgi?action=unmount&diskid=SD\_DISKHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">  <job action=unmount    diskid="SD\_DISK"    result="OK"    jobid="10"/></root>
```

Enable disk encryption and set the password to `secret`. For detailed information about the request, see [Enable disk encryption](#enable-disk-encryption).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/enablediskencryption.cgi?schemaversion=1&diskid=SD\_DISK&passphrase=secret"
```

```bash
GET /axis-cgi/disks/properties/enablediskencryption.cgi?schemaversion=1&diskid=SD\_DISK&passphrase=secretHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><DiskPropertiesResponse xmlns="http://www.axis.com/vapix/http\_cgi/disks/properties1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/disks/properties1http://www.axis.com/vapix/http\_cgi/disks/properties/disk\_properties1.xsd" SchemaVersion="1.0">  <Success>    <GeneralSuccess />  </Success></DiskPropertiesResponse>
```

Format the disk. If required file system is set, the disk is formatted automatically when mounted and this step should be skipped. For detailed information about the request, see [Format disk](#format-disk).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/format.cgi?diskid=SD\_DISK&filesystem=ext4"
```

```bash
GET /axis-cgi/disks/format.cgi?diskid=SD\_DISK&filesystem=ext4Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">  <job action=format    diskid="SD\_DISK"    result="OK"    jobid="11"/></root>
```

Mount the disk:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/mount.cgi?action=mount&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/mount.cgi?action=mount&diskid=SD\_DISKHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">  <job action=mount    diskid="SD\_DISK"    result="OK"    jobid="12"/></root>
```

Disable disk encryption. Before disk encryption can be disabled, the disk must be unmounted. After disabling disk encryption the disk must be formatted and mounted before it can be used. If required file system is set, the disk is formatted automatically. Note that recordings will be removed when the disk is formatted.

Unmount the SD card. For detailed information about the request, see [Mount and unmount a disk](#mount-and-unmount-a-disk).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/mount.cgi?action=unmount&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/mount.cgi?action=unmount&diskid=SD\_DISKHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">  <job action=unmount    diskid="SD\_DISK"    result="OK"    jobid="10"/></root>
```

Disable disk encryption. For detailed information about the request, see [Disable disk encryption](#disable-disk-encryption).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/disablediskencryption.cgi?schemaversion=1&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/properties/disablediskencryption.cgi?schemaversion=1&diskid=SD\_DISKHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><DiskPropertiesResponse xmlns="http://www.axis.com/vapix/http\_cgi/disks/properties1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/disks/properties1http://www.axis.com/vapix/http\_cgi/disks/properties/disk\_properties1.xsd" SchemaVersion="1.0">  <Success>    <GeneralSuccess />  </Success></DiskPropertiesResponse>
```

Format the disk. If required file system is set, the disk is formatted automatically when mounted and this step should be skipped. For detailed information about the request, see [Format disk](#format-disk).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/format.cgi?diskid=SD\_DISK&filesystem=ext4"
```

```bash
GET /axis-cgi/disks/format.cgi?diskid=SD\_DISK&filesystem=ext4Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">  <job action=format    diskid="SD\_DISK"    result="OK"    jobid="11"/></root>
```

Mount the disk:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/mount.cgi?action=mount&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/disks/mount.cgi?action=mount&diskid=SD\_DISKHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/startjob1.xsd">  <job action=mount    diskid="SD\_DISK"    result="OK"    jobid="12"/></root>
```

Change the passphrase. The passphrase can only be changed when the disk is mounted. If the disk is unmounted, use `/axis-cgi/disks/mount.cgi` to mount the disk.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/changediskpassphrase.cgi?schemaversion=1&diskid=SD\_DISK&newpassphrase=verysecret&oldpassphrase=secret"
```

```bash
GET /axis-cgi/disks/properties/changediskpassphrase.cgi?schemaversion=1&diskid=SD\_DISK&newpassphrase=verysecret&oldpassphrase=secretHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="UTF-8"?><DiskPropertiesResponse xmlns="http://www.axis.com/vapix/http\_cgi/disks/properties1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/disks/properties1http://www.axis.com/vapix/http\_cgi/disks/properties/disk\_properties1.xsd" SchemaVersion="1.0">  <Success>    <GeneralSuccess />  </Success></DiskPropertiesResponse>
```

### Set required file system

Use `/axis-cgi/disks/properties/setrequiredfs.cgi` to enable and set a required file system for the disk. Required file system is disabled by default.

Required file system is used to automatically format SD cards to the file system set as required file system.

If required file system has been set, the Axis product checks each mounted SD card to see if the card uses the required file system. If the card uses another file system, or if the file system cannot be determined, the card is formatted to the required file system automatically. During formatting, any data on the card is lost.

An SD card that has been locked (using the switch on the card or using `/axis-cgi/disks/lock.cgi`) is not reformatted. If the card is unlocked using `/axis-cgi/disks/lock.cgi`, the card will be formatted the next time it is mounted.

If a required file system is set while a card is mounted and in use, the card will be reformatted when it is remounted and all data will be lost.

Note

-   To check the current required file system setting, use `/axis-cgi/disks/list.cgi`. See [List disks](#list-disks).
-   Before setting a required file system, use `/axis-cgi/disks/getcapabilities.cgi` to check if the intended file system can be used as required file system. See [Get disk capabilities](#get-disk-capabilities).
-   Required file system can be set to `ext4`. Using `ext4` is recommended to reduce the risk of data loss if the card is ejected and after abrupt power cycling. To read SD cards formatted with `ext4` on Windows, additional software is needed.
-   In the Axis product web interface, the required file system setting is called autoformat.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/setrequiredfs.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/properties/setrequiredfs.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid=<string>` | `<Disk ID>` | Required. The Disk ID of the disk to set required file system on. |
| `filesystem=<integer>` | `none` `ext4` | Required. The file system to use as required file system. Supported file systems can be requested using `/axis-cgi/disks/getcapabilities.cgi` as described in [Get disk capabilities](#get-disk-capabilities).`none` = Disable the required file system functionality. |

**Response**

Responses from `/axis-cgi/disks/properties/setrequiredfs.cgi`

**Success**

If the request is successful, required file system is set and a `Success` response is returned. See [General success response](#general-success-response-disk-properties-api).

**Error**

If an error occurred, an `Error` response is returned. See [General error response](#general-error-response-disk-properties-api).

Error codes: 10, 20, 30, 40

### Enable disk encryption

Use `/axis-cgi/disks/properties/enablediskencryption.cgi` to enable disk encryption.

Disk encryption is disabled by default. Disk encryption can only be enabled when the disk is unmounted. After enabling disk encryption, the disk must be formatted and mounted. See [Disk encryption](#disk-encryption).

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/enablediskencryption.cgi?<argument>=<value>&\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/properties/enablediskencryption.cgi?<argument>=<value>&\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid=<string>` | _<Disk ID>_ | Required. Disk ID of the disk to encrypt. |
| `passphrase=<string>` | String | Required. The passphrase to use for disk encryption.Maximum length: 512 bytes |

**Response**

Responses from `/axis-cgi/disks/properties/enablediskencryption.cgi`

**Success**

If the request is successful, the disk content is encrypted and a `Success` response is returned. See [General success response](#general-success-response-disk-properties-api).

**Error**

If an error occurred, an `Error` response is returned. See [General error response](#general-error-response-disk-properties-api).

Error codes: 10, 20, 40, 50, 100, 110, 140, 160

### Disable disk encryption

Use `/axis-cgi/disks/properties/disablediskencryption.cgi` to disable disk encryption.

Disk encryption can only be disabled when the disk is unmounted. After disabling disk encryption, the disk must be formatted and mounted.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/disablediskencryption.cgi?<argument>=<value>&\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/properties/disablediskencryption.cgi?<argument>=<value>&\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid=<string>` | _<Disk ID>_ | Required. The disk’s Disk ID. |

**Response**

Responses from `/axis-cgi/disks/properties/disablediskencryption.cgi`

**Success**

If the request is successful, disk encryption is disabled and a `Success` response is returned. See [General success response](#general-success-response-disk-properties-api).

**Error**

If an error occurred, an `Error` response is returned. See [General error response](#general-error-response-disk-properties-api).

Error codes: 10, 20, 40, 50, 100, 160

### Change disk encryption passphrase

Use `/axis-cgi/disks/properties/changediskpassphrase.cgi` to change the passphrase used for disk encryption. The passphrase can only be changed when the disk is mounted. Changing the passphrase does not disrupt ongoing recordings.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/changediskpassphrase.cgi?<argument>=<value>&\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/properties/changediskpassphrase.cgi?<argument>=<value>&\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid=<string>` | _<Disk ID>_ | Required. The disk’s Disk ID. |
| `newpassphrase=<string>` | String | Required. The new passphrase to use for disk encryption.Maximum length: 512 bytes |
| `oldpassphrase=<string>` | String | Required. The current passphrase. |

**Response**

Responses from `/axis-cgi/disks/properties/changediskpassphrase.cgi`

**Success**

If the request is successful, disk encryption is disabled and a `Success` response is returned. See [General success response](#general-success-response-disk-properties-api).

**Error**

If an error occurred, an `Error` response is returned. See [General error response](#general-error-response-disk-properties-api).

Error codes: 10, 20, 40, 50, 100, 120, 130, 150

### Update cleanup max age

Use `/axis-cgi/disks/properties/setcleanupmaxage.cgi` to update the current cleanup max age setting.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/setcleanupmaxage.cgi?<argument=value>"
```

```bash
GET /axis-cgi/disks/properties/setcleanupmaxage.cgi?<argument=value>Host: <servername>
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schema version` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid` | String | Required. The disk’s Disk ID. |
| `maxage` | 0–7000 | Required. The maximum number of days that the unlocked recordings are kept on the disk itself. Recordings older than the specified number will be deleted. This parameter is only used when `CleanupPolicy` is set to `fifo`. Please note that recordings will be deleted if the free amount of storage space becomes low. |

**Response**

Responses from `/axis-cgi/disks/properties/setcleanupmaxage.cgi`

**Success**

If the request is successful, the disk content is encrypted and a `Success` response is returned. See [General success response](#general-success-response-disk-properties-api).

**Error**

If an error occurred, an `Error` response is returned. See [General error response](#general-error-response-disk-properties-api).

Error codes: 10, 20, 40, 50, 100, 110, 140, 160

### Update cleanup policy

Use `/axis-cgi/disks/properties/setcleanuppolicy.cgi` to update the current cleanup policy setting.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/setcleanuppolicy.cgi?<argument=value>"
```

```bash
GET /axis-cgi/disks/properties/setcleanuppolicy.cgi?<argument=value>Host: <servername>
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schema version` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid` | String | Required. The disk’s Disk ID. |
| `cleanuppolicy` | `fifo` `none` | Required. `fifo` = first in, first out. Recordings are automatically deleted according to the rules specified by `cleanupmaxage`. `none` = Recordings must be manually deleted. Please note that recordings will be deleted if the free amount of storage space becomes low |

**Response**

Responses from `/axis-cgi/disks/properties/setcleanuppolicy.cgi`

**Success**

If the request is successful, the disk content is encrypted and a `Success` response is returned. See [General success response](#general-success-response-disk-properties-api).

**Error**

If an error occurred, an `Error` response is returned. See [General error response](#general-error-response-disk-properties-api).

Error codes: 10, 20, 40, 50, 100, 110, 140, 160

### Set disk alert levels

Use `/axis-cgi/disks/properties/setdiskalertlevels.cgi` to update the alert levels for a disk.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/setdiskalertlevels.cgi?<argument=value>&\[<argument=value>...\]"
```

```bash
GET /axis-cgi/disks/properties/setdiskalertlevels.cgi?<argument=value>&\[<argument=value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid=<string>` | String | Required. The disk’s Disk ID. |
| `wear` | `>=0` | The wear level of the disk that should trigger a storage alert event. The event will be sent once with the alert property set to `True` when any property reaches its alert level. Once all properties are below their alert levels for the event will be sent again, but with the alert property set to `False`. |
| `temperature` | `>=0` | The temperature, measured in Kelvin, of the disk at which to trigger a Storage alert event. This event is sent once with the alert property set to `True` when any property reaches its alert level. Once all properties are below their alert levels for the event will be sent again, but with the alert property set to `False`. |

**Response**

Responses from `/axis-cgi/disks/properties/setdiskalertlevels.cgi`

**Success**

If the request is successful, the disk content is encrypted and a `Success` response is returned. See [General success response](#general-success-response-disk-properties-api).

**Error**

If an error occurred, an `Error` response is returned. See [General error response](#general-error-response-disk-properties-api).

Error codes: 10, 20, 40, 50, 100, 110, 140, 160

### Get disk alert levels

Use `/axis-cgi/disks/properties/getdiskalertlevels.cgi` to check the alert levels for a disk.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/getdiskalertlevels.cgi?<argument=value>&\[<argument=value>...\]"
```

```bash
GET /axis-cgi/disks/properties/getdiskalertlevels.cgi?<argument=value>&\[<argument=value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion` | Integer | Required. The major version of the XML schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid` | String | Required. The disk’s Disk ID. |

**Response**

Responses from `/axis-cgi/disks/properties/getdiskalertlevels.cgi`

**Success**

Successful response

```bash
HTTP/1.0 200 OKContent-Type: text/xml<DiskPropertiesResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disks/properties/disk\_properties1.xsd" SchemaVersion="1.1">  <Success>    <GetAlertLevelsSuccess>      <AlertLevels Wear="50" Temperature="360"/>    </GetAlertLevelsSuccess>  </Success></DiskPropertiesResponse>
```

**Error**

If an error occurred, an `Error` response is returned. See [General error response](#general-error-response-disk-properties-api).

Error codes: 10, 20, 40, 50, 100, 110, 140, 160

### XML schema versions

Use `/axis-cgi/disks/properties/schemaversions.cgi` to list supported versions of the XML schema for the Disk properties API and whether the schemas are deprecated or not.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/properties/schemaversions.cgi"
```

```bash
GET /axis-cgi/disks/properties/schemaversions.cgiHost: <servername>
```

This CGI has no arguments.

**Response**

Responses from `/axis-cgi/disks/properties/schemaversions.cgi`

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><DiskPropertiesResponse    xmlns="http://www.axis.com/vapix/http\_cgi/disks/properties1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/disks/properties1    http://www.axis.com/vapix/http\_cgi/disks/properties/disk\_properties1.xsd"    SchemaVersion="1.0">    <Success>        <SchemaVersionsSuccess>            <SchemaVersion>                <VersionNumber>\[major.minor\]</VersionNumber>                <Deprecated>\[true/false\]</Deprecated>                ...            </SchemaVersion>        </SchemaVersionsSuccess>    </Success></DiskPropertiesResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `DiskPropertiesResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `Success` | Successful request |
| `SchemaVersionsSuccess` | Contains the supported XML schema versions. |
| `SchemaVersion` | Contains one schema version. |
| `VersionNumber` | Schema version. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used. |

### General success response

General success response from Disk Properties API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="UTF-8" ?><DiskPropertiesResponse    xmlns="http://www.axis.com/vapix/http\_cgi/disks/properties1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/disks/properties1http://www.axis.com/vapix/http\_cgi/disks/properties/disk\_properties1.xsd"    SchemaVersion="1.0">    <Success>        <GeneralSuccess />    </Success></DiskPropertiesResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `DiskPropertiesResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `Success` | Successful request. |
| `GeneralSuccess` | Successful request. |

### General error response

General error response from the Disk properties API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><DiskPropertiesResponse    xmlns="http://www.axis.com/vapix/http\_cgi/disks/properties1"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:schemaLocation="http://www.axis.com/vapix/http\_cgi/disks/properties1http://www.axis.com/vapix/http\_cgi/disks/properties/disk\_properties1.xsd"    SchemaVersion="1.0">    <Error>        <GeneralError>            <ErrorCode>\[error code\]</ErrorCode>            <ErrorDescription>\[description\]</ErrorDescription>        </GeneralError>    </Error></DiskPropertiesResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `DiskPropertiesResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `Error` | Error response. |
| `GeneralError` | Error response. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid request. | All |
| `30` | Specified file system is not supported. | `/axis-cgi/disks/properties/setrequiredfs.cgi` |
| `40` | Specified version is not supported. | All |
| `50` | Invalid disk ID. | `/axis-cgi/disks/properties/enablediskencryption.cgi`, `/axis-cgi/disks/properties/disablediskencryption`, `/axis-cgi/disks/properties/changediskpassphrase.cgi` |
| `100` | The disk does not support disk encryption. | `/axis-cgi/disks/properties/enablediskencryption.cgi`, `/axis-cgi/disks/properties/disablediskencryption`, `/axis-cgi/disks/properties/changediskpassphrase.cgi` |
| `110` | Invalid passphrase. | `/axis-cgi/disks/properties/enablediskencryption.cgi` |
| `120` | Invalid new passphrase. | `/axis-cgi/disks/properties/changediskpassphrase.cgi` |
| `130` | The `oldpassphrase` does not match the existing passphrase. | `/axis-cgi/disks/properties/changediskpassphrase.cgi` |
| `140` | Encryption is already enabled. | `/axis-cgi/disks/properties/enablediskencryption.cgi` |
| `150` | The disk is unmounted. Passphrase can only be changed when the disk is mounted. | `/axis-cgi/disks/properties/changediskpassphrase.cgi` |
| `160` | The disk is mounted. Encryption can only be enabled/disabled when the disk is unmounted. | `/axis-cgi/disks/properties/enablediskencryption.cgi`, `/axis-cgi/disks/properties/disablediskencryption` |

## Network share API
### Description

Use VAPIX® Network share API to add, remove and manage network shares. A network share can be a share on a NAS (Network Attached Storage) or on any server that uses CIFS (Common Internet File System), also known as SMB (Server Message Block).

The Axis product identifies the share using a unique **Share ID**. The share ID is assigned to the share by the Axis product but can also be set manually when adding the share.

To store recordings on a network share, the share must be bound to a disk. The bind request returns a **Disk ID** which should be used when setting up and accessing recordings. For information about recordings, see [Recording API](#recording-api).

The Network share API consists of the following CGIs:

| Name | Description |
| --- | --- |
| `/axis-cgi/disks/list.cgi` | List the added network shares and their parameters. |
| `/axis-cgi/disks/networkshare/add.cgi` | Add a network share. |
| `/axis-cgi/disks/networkshare/modify.cgi` | Modify a network share. The network share must first be unbound. |
| `/axis-cgi/disks/networkshare/remove.cgi` | Remove a network share. The network share must first be unbound. |
| `/axis-cgi/disks/networkshare/bind.cgi` | Bind the network share to a disk. This makes it possible to access the share through the Disk Management API, see [Disk management API](#disk-management-api). |
| `/axis-cgi/disks/networkshare/unbind.cgi` | Unbind the network share. |
| `/axis-cgi/disks/networkshare/test.cgi` | Test the network share to verify that the parameters are correct and that the share can be used as a storage device. A successfully started test returns a **Job ID** which should be used as input to `/axis-cgi/disks/networkshare/job.cgi`. |
| `/axis-cgi/disks/networkshare/job.cgi` | Check the progress of a job. Typically used repeatedly until the job is done. |
| `/axis-cgi/disks/networkshare/schemaversions.cgi` | Retrieve a list of supported versions of the XML Schema for the Network Share API. |

Recordings stored on a network share cannot be accessed directly. This is because the Axis product creates an internal database on the share. If recordings need to be accessed directly, create a network share recipient in an action rule instead.

### Prerequisites
#### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.NetworkShare.NetworkShare=yes`
-   **Property**: `Properties.NetworkShare.CIFS=yes`
-   **AXIS OS**: 5.40 and later

### Common examples

Test that the network share "myshare" on the storage device "mynas" can be used for storage. User name for the share is "nasuser" and password is "pass".

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/test.cgi?schemaversion=1&address=mynas.mycompany.com&share=myshare&user=nasuser&pass=pass"
```

```bash
GET /axis-cgi/disks/networkshare/test.cgi?schemaversion=1&address=mynas.mycompany.com&share=myshare&user=nasuser&pass=passHost: <servername>
```

The response returns the Job ID of the started job. Here, the returned Job ID is `1`. The Job ID is to be used as input to `/axis-cgi/disks/networkshare/job.cgi` to check the progress of the started job.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/job.cgi?schemaversion=1&jobid=1"
```

```bash
GET /axis-cgi/disks/networkshare/job.cgi?schemaversion=1&jobid=1Host: <servername>
```

The response shows that the job is in progress, 15% of the job is done.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><NetworkShareResponse SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">  <JobSuccess>    <Progress>15</Progress>  </JobSuccess></NetworkShareResponse>
```

By running `/axis-cgi/disks/networkshare/job.cgi` repeatedly, the progress of the job can be reported by showing incremental updates, for example:

```bash
15%32%45%68%92%Done!
```

Add the network share "myshare" on the storage device "mynas". User name for the share is "nasuser" and password is "pass". The network share is given a user-friendly name "My Share".

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/add.cgi?schemaversion=1&nicename=My%20Share&address=mynas&share=myshare&user=nasuser&pass=pass"
```

```bash
GET /axis-cgi/disks/networkshare/add.cgi?schemaversion=1&nicename=My%20Share&address=mynas&share=myshare&user=nasuser&pass=passHost: <servername>
```

The share’s unique Share ID is returned in the response. Here, the returned Share ID is `485279c5-6676-4abd-b04c-4434e4791730`

List all network shares.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/list.cgi?schemaversion=1&shareid=all"
```

```bash
GET /axis-cgi/disks/networkshare/list.cgi?schemaversion=1&shareid=allHost: <servername>
```

The response shows that one network share has been added.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><NetworkShareResponse SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">  <ListSuccess>    <NetworkShares NumberOfShares="1">      <NetworkShare NiceName="My Share"        ShareId="35419"        Address="mynas.mycompany.com"        Share="myshare"        User="nasuser" />    </NetworkShares>  </ListSuccess></NetworkShareResponse>
```

Bind the network share to a disk. The disk is mounted automatically. The Share ID is from the `/axis-cgi/disks/networkshare/add.cgi` response.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/bind.cgi?schemaversion=1&shareid=35419"
```

```bash
GET /axis-cgi/disks/networkshare/bind.cgi?schemaversion=1&shareid=35419Host: <servername>
```

The Disk ID of the disk to which the share is bound is returned in the response. Here, the returned Disk ID is `NetworkShare`.

Unbind and remove the network share.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/unbind.cgi?schemaversion=1&shareid=35419"
```

```bash
GET /axis-cgi/disks/networkshare/unbind.cgi?schemaversion=1&shareid=35419Host: <servername>
```

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/remove.cgi?schemaversion=1&shareid=35419"
```

```bash
GET /axis-cgi/disks/networkshare/remove.cgi?schemaversion=1&shareid=35419Host: <servername>
```

### List network shares

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/list.cgi?schemaversion=1&shareid=all"
```

```bash
GET /axis-cgi/disks/networkshare/list.cgi?schemaversion=1&shareid=allHost: <servername>
```

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/list.cgi?schemaversion=1&shareid=35419"
```

```bash
GET /axis-cgi/disks/networkshare/list.cgi?schemaversion=1&shareid=35419Host: <servername>
```

Use `/axis-cgi/disks/networkshare/list.cgi` to retrieve information about network shares used by the Axis product.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/list.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/networkshare/list.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>[.<integer>]` | Integers | The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `shareid=<string>` | `all` `<Share ID 1>`, `<Share ID 2>`,... | Required. The Share IDs of the shares to list.`all` = List all network shares that have been added to the Axis product.`<Share ID 1>`, `<Share ID 2>` = List shares with the specified Share IDs. |

**Response**

The response from `/axis-cgi/disks/networkshare/list.cgi` is a list of network shares or a general error.

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <ListSuccess>        <NetworkShares NumberOfShares="\[number of shares\]">            <NetworkShare                NiceName="\[nicename 1\]"                ShareId="\[Share ID 1\]"                Address="\[address 1\]"                Share="\[share 1\]"                User="\[user 1\]"                DiskId="\[Disk ID 1\]" />            ...        </NetworkShares>    </ListSuccess></NetworkShareResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `NetworkShareResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `ListSuccess` | Request was successful. |
| `NetworkShares` | Contains the network shares that have been added.`NumberOfShares` = The number of network shares. |
| `NetworkShare` | Contains the parameters that define the network share.`NiceName` = User-friendly name for the network share.`ShareId` = The Share ID.`Address` = Network address of the storage device.`Share` = The name of the share on the storage device.`User` = User name for a user on the share.`DiskId` = The Disk ID of the disk to which the share is bound. This attribute is not present if the share is unbound. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-network-share-api).

Error codes: 10, 20, 40

### Add network share

Use `/axis-cgi/disks/networkshare/add.cgi` to add a network share.

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/add.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/networkshare/add.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>[.<integer>]` | Integers | The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `nicename=<string>` | String | Required. A user-friendly name for the network share. |
| `address=<string>` | IPv4 address or host name | Required. The network address of the storage device. |
| `share=<string>` | String | Required. The name of the share on the storage device. |
| `shareid=<string>` | String | A unique Share ID. The ID is restricted to the regular expression `[A-Za-z0-9-]+` |
| `user=<string>` | String | User name for a user on the share. |
| `pass=<string>` | String | Password for the user above. |

**Response**

Responses from `/axis-cgi/disks/networkshare/add.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <AddSuccess ShareId="\[Share ID\]" /></NetworkShareResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `NetworkShareResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `AddSuccess` | Successful request.`ShareId` = The Share ID. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-network-share-api).

Error codes: 10, 20, 40, 200, 210, 220, 230

### Remove network share

Use `/axis-cgi/disks/networkshare/remove.cgi` to remove a network share from the product. Before removing, make sure that the network share is not bound. To unbound the share, use `/axis-cgi/disks/networkshare/unbind.cgi`, see [Unbind network share](#unbind-network-share).

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/remove.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/networkshare/remove.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>[.<integer>]` | Integers | The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `shareid=<string>` _Required_ | `<Share ID 1>`, `<Share ID 2>`,... | Remove the shares with the specified Share IDs. |

**Response**

Responses from `/axis-cgi/disks/networkshare/remove.cgi`

**Success**

If the request is successful, disk encryption is disabled and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-network-share-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-network-share-api).

Error codes: 10, 20, 40, 500

### Modify network share

Use `/axis-cgi/disks/networkshare/modify.cgi` to modify an existing network share. The user-friendly name `NiceName` can always be changed. To change the other parameters, the share must be unbound from the disk using `/axis-cgi/disks/networkshare/unbind.cgi`, see [Unbind network share](#unbind-network-share).

**Request**

-   **Security level**: Administrator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/modify.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/networkshare/modify.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>[.<integer>]` | Integers | The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `shareid=<string>` _Required_ | String | The Share ID of the network share to modify. |
| `nicename=<string>` | String | A user-friendly name for the network share. |
| `address=<string>` | IPv4 address or host name | The network address of the storage device. |
| `share=<string>` | String | The name of the share on the storage device. |
| `user=<string>` | String | User name for a user on the share. |
| `pass=<string>` | String | Password for the user above. |

**Response**

Responses from `/axis-cgi/disks/networkshare/modify.cgi`

**Success**

If the request is successful, disk encryption is disabled and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-network-share-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-network-share-api).

Error codes: 10, 20, 40, 600, 610, 620

### Bind network share

Use `/axis-cgi/disks/networkshare/bind.cgi` to bind an existing network share to a disk. This makes it possible to store recordings on the share and to access the share through the Disk management API. The request returns the **Disk ID** of the disk to which the share was bound. The Disk ID should be used when setting up and accessing recordings through the Recording API.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/bind.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/networkshare/bind.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>[.<integer>]` | Integers | The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `shareid=<string>` | `<Share ID>` | Required. The Share ID of the network share to bind. |
| `automaticmount=<string>` | `yes` `no` | `yes` = Turn on automatic mounting. The disk to which the share is bound will be mounted automatically after binding.`no` = Turn off automatic mount. The disk will not be mounted automatically.Default: `yes`. |

**Response**

Responses from `/axis-cgi/disks/networkshare/bind.cgi`

**Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <BindSuccess DiskID="\[Disk ID\]" /></NetworkShareResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `NetworkShareResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `BindSuccess` | Successful request.`DiskID` = The Disk ID of the disk that the network share was bound to. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-network-share-api).

Error codes: 10, 20, 40, 300, 310

### Unbind network share

Use `/axis-cgi/disks/networkshare/unbind.cgi` to free a bound network share so that the share can be modified or removed.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/unbind.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/networkshare/unbind.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>[.<integer>]` | Integers | The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `shareid=<string>` | `<Share ID>` | Required. The Share ID of the network share to unbind. |

**Response**

Responses from `/axis-cgi/disks/networkshare/unbind.cgi`

**Success**

If the request is successful, disk encryption is disabled and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-network-share-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-network-share-api).

Error codes: 10, 20, 40, 400

### Test network share

Use `/axis-cgi/disks/networkshare/test.cgi` to test a network share. The submitted parameters specifies the share to test. These parameters are only used to run the test and are not stored. The test checks if the network share can be used as a storage device.

The response shows if the job has been started or not. A successfully started job returns a **Job ID**, which should be used as input to `/axis-cgi/disks/networkshare/job.cgi`, see [Job progress](#job-progress-network-share-api).

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/test.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/networkshare/test.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>[.<integer>]` _Optional_ | Integers | The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `address=<string>` _Optional_ | IPv4 address or host name | The network address of the storage device. |
| `share=<string>` _Optional_ | String | The name of the share on the storage device. |
| `user=<string>` _Optional_ | String | User name for a user on the share. |
| `pass=<string>` _Optional_ | String | Password for the user above. |
| `shareid=<string>` _Optional_ | String | A Share ID. `shareid` can be used instead of one or more of `address`, `share`, `user` and `pass`. If `shareid` is used together with one or more the above arguments, the specified arguments will override the values stored in the Share ID. |

**Response**

Responses from `/axis-cgi/disks/networkshare/test.cgi`

**Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <TestSuccess JobId="\[Job ID\]" /></NetworkShareResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `NetworkShareResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `TestSuccess` | Test was started successfully.`JobId` = The Job ID. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-network-share-api).

Error codes: 10, 20, 40, 700, 710, 720, 730, 740, 750, 760

### Job progress

Use `/axis-cgi/disks/networkshare/job.cgi` to check the progress of a test job.

The test job should be started by running `/axis-cgi/disks/networkshare/test.cgi`. If the job could be started successfully, a Job ID is returned. This Job ID is used as input to `/axis-cgi/disks/networkshare/job.cgi`. The Job ID can also be retrieved by running `/axis-cgi/disks/networkshare/job.cgi`.

Typically, `/axis-cgi/disks/networkshare/job.cgi` is run repeatedly until the job is finished. This workflow allows a user interface to be more responsive and to report the progress of a job by displaying incremental status updates, for example in a progress bar.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/job.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/disks/networkshare/job.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>[.<integer>]` _Required_ | Integers | The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `jobid=<string>` _Required_ | `<Job ID>` | The ID of the job to check progress for. |

**Response**

Responses from `/axis-cgi/disks/networkshare/job.cgi`

**Success: Job is in progress**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <JobSuccess>        <Progress>\[progress\]</Progress>    </JobSuccess></NetworkShareResponse>
```

**Success: Job finished successfully**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <JobSuccess>        <GeneralSuccess />    </JobSuccess></NetworkShareResponse>
```

**Success: Job finished but with errors**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <JobSuccess>        <GeneralError>            <ErrorCode>\[code\]</ErrorCode>            <ErrorDescription>\[description\]</ErrorDescription>        </GeneralError>    </JobSuccess></NetworkShareResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `NetworkShareResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `JobSuccess` | Successful request.Contains `Progress` if the job is not finished.Contains `GeneralSuccess` if the job finished successfully.Contains `GeneralError` if the job finished with errors. |
| `GeneralSuccess` | The job finished successfully. |
| `Progress` | Progress of the job in percent. |
| `GeneralError` | The job finished with errors. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-network-share-api).

Error codes: 10, 20, 40, 700, 710, 720, 730, 740, 750, 760

### XML schema versions

Use `/axis-cgi/disks/networkshare/schemaversions.cgi` to list supported versions of the XML schema for the Network share API and whether the schemas are deprecated or not.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/networkshare/schemaversions.cgi"
```

```bash
GET /axis-cgi/disks/networkshare/schemaversions.cgiHost: <servername>
```

This CGI has no arguments.

**Response**

Responses from `/axis-cgi/disks/networkshare/schemaversions.cgi`

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <SchemaVersionsSuccess>        <SchemaVersion>            <VersionNumber>\[major1\].\[minor1\]</VersionNumber>            <Deprecated>\[deprecated\]</Deprecated>            ...        </SchemaVersion>    </SchemaVersionsSuccess></NetworkShareResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `NetworkShareResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `SchemaVersionsSuccess` | Contains the supported XML schema versions. |
| `SchemaVersion` | Contains one schema version. |
| `VersionNumber` | Schema version. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used. |

### General success response

General success response from Network Share API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <GeneralSuccess /></NetworkShareResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `NetworkShareResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralSuccess` | Successful request. |

### General error response

General error response from Network share API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><NetworkShareResponse    SchemaVersion="1.0"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/networkshare1.xsd">    <GeneralError>        <ErrorCode>\[error code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></NetworkShareResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `NetworkShareResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralError` | Error response. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid request. | All |
| `40` | Specified version is not supported. | All |
| `200` | Invalid `ShareId` | `/axis-cgi/disks/networkshare/add.cgi` |
| `210` | The `ShareId` is not unique | `/axis-cgi/disks/networkshare/add.cgi` |
| `220` | The `NiceName` is not unique | `/axis-cgi/disks/networkshare/add.cgi` |
| `230` | Maximum number of network shares is already reached. No more shares can be added. | `/axis-cgi/disks/networkshare/add.cgi` |
| `300` | No available disk. Check if another network share is already bound. | `/axis-cgi/disks/networkshare/bind.cgi` |
| `310` | The network share is already bound to a disk. | `/axis-cgi/disks/networkshare/bind.cgi` |
| `400` | The network share is mounted and cannot be unbound. Unmount the share using Disk Management API. | `/axis-cgi/disks/networkshare/unbind.cgi` |
| `500` | The network share is bound and cannot be removed. Use `/axis-cgi/disks/networkshare/unbind.cgi` to unbind the share. | `/axis-cgi/disks/networkshare/remove.cgi` |
| `600` | The network share is bound and cannot be modified. Use `/axis-cgi/disks/networkshare/unbind.cgi` to unbind the share. | `/axis-cgi/disks/networkshare/modify.cgi` |
| `610` | The new `ShareID` parameter is no unique. | `/axis-cgi/disks/networkshare/modify.cgi` |
| `620` | The `NiceName` parameter is not unique. | `/axis-cgi/disks/networkshare/modify.cgi` |
| `700` | No such hostname. | `/axis-cgi/disks/networkshare/test.cgi`, `/axis-cgi/disks/networkshare/job.cgi` |
| `710` | Error while mounting network share. | `/axis-cgi/disks/networkshare/test.cgi`, `/axis-cgi/disks/networkshare/job.cgi` |
| `720` | Internal error while mounting network share. | `/axis-cgi/disks/networkshare/test.cgi`, `/axis-cgi/disks/networkshare/job.cgi` |
| `730` | Too many tests or jobs started, wait for some to finish. | `/axis-cgi/disks/networkshare/test.cgi`, `/axis-cgi/disks/networkshare/job.cgi` |
| `740` | Problem writing to the share. | `/axis-cgi/disks/networkshare/test.cgi`, `/axis-cgi/disks/networkshare/job.cgi` |
| `750` | Problem reading data written to the share. | `/axis-cgi/disks/networkshare/test.cgi`, `/axis-cgi/disks/networkshare/job.cgi` |
| `760` | Problem connecting to the share. | `/axis-cgi/disks/networkshare/test.cgi`, `/axis-cgi/disks/networkshare/job.cgi` |

## Recording storage limit API
### Description

VAPIX® Recording storage limit API allows applications to control how the capacity of a shared storage resource is distributed. For example, when several cameras record to the same network share, the API can be used to limit the amount of disk space each camera is allowed to use.

Setting recording storage limits is equivalent to setting up quota control on network-attached storage (NAS) devices. The Recording storage limit API enables applications to simplify recording and storage configuration by allowing the camera installer to configure storage limits at the same time and in the same application as the installer configures other recording and storage settings.

Supported functionality:

-   Retrieve current recording storage limit and currently used disk space.
-   Set recording storage limit.

#### Identification

VAPIX® Recording storage limit API is supported if:

-   **Property**: `Properties.LocalStorage.StorageLimit=yes`
-   **AXIS OS**: 5.70 and later

### Common examples

Get supported XML schema versions.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/schemaversions.cgi"
```

```bash
GET /axis-cgi/record/storage/schemaversions.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><StorageLimitsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.0" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">  <SchemaVersionsSuccess>    <SchemaVersion>      <VersionNumber>1.0</VersionNumber>      <Deprecated>false</Deprecated>    </SchemaVersion>  </SchemaVersionsSuccess></StorageLimitsResponse>
```

Suppose that two cameras should record to the same network share. Use `/axis-cgi/disks/list.cgi` to retrieve the network share’s disk space. The response shows that the total disk space is 4000 GB.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/disks/list.cgi?diskid=NetworkShare"
```

```bash
GET /axis-cgi/disks/list.cgi?diskid=NetworkShareHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/disk/list1.xsd">  <disks numberofdisks="1">    <disk diskid="NetworkShare"      name="My Share"      totalsize="4194304000"      freesize="3670016000"      cleanuplevel="95"      cleanupmaxage="1"      cleanuppolicy="none"      locked="no"      full="no"      readonly="no"      filesystem="cifs"      status="OK"      group="S1"      requiredfilesystem="none"      diskencryptionenabled="false"      diskencrypted="false"/>  </disks></root>
```

Divide the disk space among the two cameras so that one camera uses 2/3 of the disk space and the other camera uses 1/3.

Requests:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/setlimit.cgi?schemaversion=1&diskid=NetworkShare&size=2796202667"
```

```bash
GET /axis-cgi/record/storage/setlimit.cgi?schemaversion=1&diskid=NetworkShare&size=2796202667Host: <servername>
```

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/setlimit.cgi?schemaversion=1&diskid=NetworkShare&size=1398101333"
```

```bash
GET /axis-cgi/record/storage/setlimit.cgi?schemaversion=1&diskid=NetworkShare&size=1398101333Host: <servername>
```

Responses:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><StorageLimitsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.0" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">  <GeneralSuccess /></StorageLimitsResponse>
```

Retrieve the current recording storage limit, that is, the amount of disk space the Axis product is allowed to use. When no `diskid` is specified, storage limits for all disks are returned. In the response, attribute `size` contains the current storage limit. Attribute `usedspace` contains the disk space currently used for recordings. In this example, the SD card has `size=0` which means that there is no storage limit for the SD card.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/getlimit.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/record/storage/getlimit.cgi?schemaversion=1Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><StorageLimitsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.0" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">  <GetStorageLimitsResponse>    <StorageLimit diskid="NetworkShare" size="2796202667" usedspace="553324" />    <StorageLimit diskid="SD\_DISK" size="0" usedspace="661324" />  </GetStorageLimitsResponse></StorageLimitsResponse>
```

To only retrieve the recording storage limit set for the network share, specify the share’s `diskid`.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/getlimit.cgi?schemaversion=1&diskid=NetworkShare"
```

```bash
GET /axis-cgi/record/storage/getlimit.cgi?schemaversion=1&diskid=NetworkShareHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><StorageLimitsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.0" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">  <GetStorageLimitsResponse>    <StorageLimit diskid="NetworkShare" size="2796202667" usedspace="553324" />  </GetStorageLimitsResponse></StorageLimitsResponse>
```

Retrieve the recording storage limit for a non-existing storage device.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/getlimit.cgi?schemaversion=1&diskid=DUMMY"
```

```bash
GET /axis-cgi/record/storage/getlimit.cgi?schemaversion=1&diskid=DUMMYHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><StorageLimitsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.0" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">  <GeneralError>    <ErrorCode>110</ErrorCode>    <ErrorDescription>Disk not found</ErrorDescription>  </GeneralError></StorageLimitsResponse>
```

Disable recording storage limit for the network share.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/setlimit.cgi?schemaversion=1&diskid=NetworkShare&size=0"
```

```bash
GET /axis-cgi/record/storage/setlimit.cgi?schemaversion=1&diskid=NetworkShare&size=0Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><StorageLimitsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.0" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">  <GeneralSuccess /></StorageLimitsResponse>
```

Set an incorrect recording storage limit.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/setlimit.cgi?schemaversion=1&diskid=NetworkShare&size=textstring"
```

```bash
GET /axis-cgi/record/storage/setlimit.cgi?schemaversion=1&diskid=NetworkShare&size=textstringHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><StorageLimitsResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.0" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">  <GeneralError>    <ErrorCode>120</ErrorCode>    <ErrorDescription>Invalid size value</ErrorDescription>  </GeneralError></StorageLimitsResponse>
```

### Get schema versions

Use `/axis-cgi/record/storage/schemaversions.cgi` to retrieve the supported XML schema versions.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/schemaversions.cgi"
```

```bash
GET /axis-cgi/record/storage/schemaversions.cgiHost: <servername>
```

This CGI has no arguments

**Response**

Responses from `/axis-cgi/record/storage/schemaversions.cgi`

**Success**

A successful request returns the supported schema versions.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><StorageLimitsResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    SchemaVersion="1.0"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">    <SchemaVersionsSuccess>        <SchemaVersion>            <VersionNumber>\[major.minor\]</VersionNumber>            <Deprecated>\[true/false\]</Deprecated>        </SchemaVersion>        <SchemaVersion>            <VersionNumber>\[major.minor\]</VersionNumber>            <Deprecated>\[true/false\]</Deprecated>        </SchemaVersion>        \[...\]    </SchemaVersionsSuccess></StorageLimitsResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `StorageLimitsResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `SchemaVersionsSuccess` | Successful request |
| `SchemaVersion` | Contains the schema version |
| `VersionNumber` | Schema version. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-recording-storage-limit-api).

Error codes: 10, 20, 40

### Get recording storage limit

Use `/axis-cgi/record/storage/getlimit.cgi` to retrieve the current recording storage limit.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/getlimit.cgi?<argument>=<value>&\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/record/storage/getlimit.cgi?<argument>=<value>&\[<argument>=<value>\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid=<string>` | String | Optional. The disk ID of the disk to retrieve storage limit for. If omitted, storage limits for all disks is returned. |

**Response**

Responses from `/axis-cgi/record/storage/getlimit.cgi`

**Success**

If the request is successful, the recording storage limit for the specified disks is returned.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><StorageLimitsResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    SchemaVersion="1.0"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">    <GetStorageLimitsResponse>        <StorageLimit diskid="\[Disk ID\]" size="\[size\]" usedspace="\[used size\]" />        <StorageLimit diskid="\[Disk ID\]" size="\[size\]" usedspace="\[used size\]" />    </GetStorageLimitsResponse></StorageLimitsResponse>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `StorageLimitsResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |  |  |
| `GetStorageLimitsResponse` | Successful request |  |  |
| `StorageLimit` | Contains the storage limit for one disk. | `diskid` | The disk ID. |
|  |  | `size` | The set recording storage limit size. Unit: kilobytes.`0` = recording storage limit is disabled. |
|  |  | `usedsize` | Space already used by recording data. Unit: kilobytes. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-recording-storage-limit-api).

Error codes: 10, 20, 40, 110

### Set recording storage limit

Use `/axis-cgi/record/storage/setlimit.cgi` to set the recording storage limit, that is, the amount of disk space the Axis product is allowed to use.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/storage/setlimit.cgi?<argument>=<value>&\[<argument>=<value>\]"
```

```bash
GET /axis-cgi/record/storage/setlimit.cgi?<argument>=<value>&\[<argument>=<value>\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `diskid=<string>` | String | Required. The Disk ID of the disk to use. |
| `size=<string>` | Integer | Required. The recording storage limit to set. Unit: kilobytes.Use `size=0` to disable recording storage limit for the disk.Minimum allowed size is 1048576 kilobytes, that is, 1 GB. |

**Response**

Responses from `/axis-cgi/record/storage/setlimit.cgi`

**Success**

If the request is successful, the recording storage limit is set and a `GeneralSuccess` response is returned. See [General success response](#general-success-response-recording-storage-limit-api).

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-recording-storage-limit-api).

Error codes: 10, 20, 40, 110, 120, 130

### General success response

General success response from Recording storage limit API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="UTF-8" ?><StorageLimitsResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    SchemaVersion="1.0"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">    <GeneralSuccess /></StorageLimitsResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `StorageLimitsResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralSuccess` | Successful request. |

### General error response

General error response from Recording storage limit API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><StorageLimitsResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    SchemaVersion="1.0"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recordingstoragelimit1.xsd">    <GeneralError>        <ErrorCode>\[error code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></StorageLimitsResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `StorageLimitsResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralError` | Error. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid request. | All |
| `40` | Specified version is not supported. | All |
| `110` | Disk not found. | `/axis-cgi/record/storage/getlimit.cgi`, `/axis-cgi/record/storage/setlimit.cgi` |
| `120` | Invalid size value. | `/axis-cgi/record/storage/setlimit.cgi` |
| `130` | Supplied size is less than the minimum allowed limit. | `/axis-cgi/record/storage/setlimit.cgi` |

## Recording API
### Description

The Recording API is used for recording management. Recordings can be listed, played, stopped and removed. Continuous recordings can be started and stopped. Each recording is identified by a unique **Recording ID**.

Recordings are stored on disks, for example SD cards and network shares. Disks are handled by the Disk Management API, see [Disk management API](#disk-management-api).

The Recording API is used to start and stop continuous recordings. Axis products also support event-triggered and scheduled recordings. These are configured using [Event and action services](/vapix/network-video/event-and-action-services/).

If the Axis product supports continuous recording profiles (parameter `Properties.LocalStorage.ContinuousRecording` is set to `yes`), a continuous recording should be configured using `/axis-cgi/record/continuous/addconfiguration.cgi`.

To play recordings, use `media.amp` from the RTSP API. Using RTSP for playback is recommended because all video formats as well as audio and video synchronization is supported. MJPEG recordings can also be played using `/axis-cgi/record/play.cgi` from the HTTP API.

The Recording API consists of:

| Name | Description |
| --- | --- |
| `/axis-cgi/record/continuous/addconfiguration.cgi` | Add continuous recording profile. |
| `/axis-cgi/record/continuous/listconfiguration.cgi` | List continuous recording profile. |
| `/axis-cgi/record/continuous/removeconfiguration.cgi` | Remove continuous recording profile. |
| `/axis-cgi/record/list.cgi` | Search for recordings and retrieve information. |
| `/axis-cgi/record/record.cgi` | Start recording (continuous recording). |
| `/axis-cgi/record/stop.cgi` | Stop active recording. |
| `/axis-cgi/record/remove.cgi` | Remove recordings. |
| `/axis-cgi/record/play.cgi` | Play MJPEG recording. _This CGI has been deprecated and will no longer receive updates as of AXIS OS version 10.2._ |
| RTSP API | Play H.264, MPEG-4 and MJPEG recordings. See [RTSP PLAY](/vapix/network-video/video-streaming/#rtsp-play). |

Recordings can be exported using the Export Recording API. See [Export recording API](#export-recording-api).

### Date and time format

The date and time format used in the Recording API is the UTC combined date and time format defined in ISO 8601:

```bash
<yyyy>-<mm>-<dd>T<HH>:<MM>:<SS>Z
```

If required, the fraction of a second `.<mmmm>` can also be used:

```bash
<yyyy>-<mm>-<dd>T<HH>:<MM>:<SS>.<mmmm>Z
```

The time offset from UTC can also be included:

```bash
<yyyy>-<mm>-<dd>T<HH>:<MM>:<SS>.<mmmm>±hh:mm
```

When using the `clock` option with the `Range` header in RTSP requests, the following date and time formats should be used:

```bash
<yyyy><mm><dd>T<HH><MM><SS>\[.<mmmm>\]Z
```

The `Range` header also supports NPT and SMPTE times, see [Play recording using RTSP](#play-recording-using-rtsp).

### Prerequisites
#### Identification

-   **Property**: `Properties.API.HTTP.Version=3`
-   **Property**: `Properties.LocalStorage.LocalStorage=yes`
-   **AXIS OS**: 5.40 and later

`/axis-cgi/record/continuous/addconfiguration.cgi`, `/axis-cgi/record/continuous/removeconfigration.cgi` and `/axis-cgi/record/continuous/listconfiguration.cgi`in addition require

-   **Property**: `Properties.LocalStorage.ContinuousRecording=yes`
-   **Property**: `Properties.LocalStorage.NbrOfContinuousRecordingProfiles > 0`

Playback over RTSP requires:

-   **Property**: `Properties.API.RTSP.Version=2.01` and later

### Common examples

Retrieve a list with information about all recordings.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/list.cgi?recordingid=all"
```

```bash
GET /axis-cgi/record/list.cgi?recordingid=allHost: <servername>
```

The response gives a list of all recordings with information about Recording ID, video and audio settings etc (only a part of the response is shown here).

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/list1.xsd">  <recordings totalnumberofrecordings="3" numberofrecordings="3" >    <recording diskid="NetworkShare"      recordingid="20110812\_081211\_016F\_00408C1834FD" ... >      <video ... />      <audio ... />    </recording>    <recording diskid="NetworkShare"      recordingid="20110813\_093530\_025B\_00408C1834FD" ... >      <video ... />      <audio ... />    </recording>    <recording diskid="NetworkShare"      recordingid="20110813\_103530\_037C\_00408C1834FD" ... >      <video ... />      <audio ... />    </recording>  </recordings></root>
```

Retrieve information about a specific recording.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/list.cgi?recordingid=20010115\_091153\_025B\_00408C1834FD"
```

```bash
GET /axis-cgi/record/list.cgi?recordingid=20010115\_091153\_025B\_00408C1834FDHost: <servername>
```

List the Event IDs associated with recordings on the SD card.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/list.cgi?listentity=eventid&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/record/list.cgi?listentity=eventid&diskid=SD\_DISKHost: <servername>
```

The response shows that recordings with Event IDs `motion` and `audio detection` are stored on the SD card.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/list1.xsd">  <eventids >    <eventid> motion </eventid>    <eventid> audio detection </eventid>  </eventids></root>
```

Play a recording over HTTP.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/play.cgi?recordingid=20010115\_091153\_025B\_00408C1834FD"
```

```bash
GET /axis-cgi/record/play.cgi?recordingid=20010115\_091153\_025B\_00408C1834FDHost: <servername>
```

Remove a recording.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/remove.cgi?recordingid=20010115\_091153\_025B\_00408C1834FD"
```

```bash
GET /axis-cgi/record/remove.cgi?recordingid=20010115\_091153\_025B\_00408C1834FDHost: <servername>
```

Add a configuration for continuous recording to the SD card.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/continuous/addconfiguration.cgi?diskid=SD\_DISK&options=resolution%3D640x480&eventid=continuous\_0"
```

```bash
GET /axis-cgi/record/continuous/addconfiguration.cgi?diskid=SD\_DISK&options=resolution%3D640x480&eventid=continuous\_0Host: <servername>
```

Add a configuration for continuous recording to the network share.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/continuous/addconfiguration.cgi?diskid=NetworkShare&eventid=continuous\_nas&options=resolution%3D640x480"
```

```bash
GET /axis-cgi/record/continuous/addconfiguration.cgi?diskid=NetworkShare&eventid=continuous\_nas&options=resolution%3D640x480Host: <servername>
```

Play the continuous recording from 2011–08–12T08:12:11Z to 2011–08–14T10:10:00Z. To make sure that all recorded material from this time period is played, also if the recording was interrupted, the recordings are first listed. The play request is then a loop over the found recordings.

First, list recordings with `eventid=continuous_nas` from the desired time period.

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/list.cgi?listentity=recordingid&eventid=continuous\_nas&starttime=2011-08-12T08:12:11Z&stoptime=2011-08-14T10:10:00Z"
```

```bash
GET /axis-cgi/record/list.cgi?listentity=recordingid&eventid=continuous\_nas&starttime=2011-08-12T08:12:11Z&stoptime=2011-08-14T10:10:00ZHost: <servername>
```

The response below shows that the continuous recording was interrupted twice during the requested time period. A recording can for example be interrupted if the Axis product is restarted or if network connection is lost. The response contains information such as the Recording IDs, start and stop times of the three recordings found during the requested time period. Only a part of the response is shown here.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/list1.xsd">  <recordings totalnumberofrecordings="6" numberofrecordings="3" >    <recording diskid="NetworkShare"      recordingid="20110812\_081211\_016F\_00408C1834FD"      starttime="2011-08-12T08:12:11Z"      stoptime="2011-08-13T09:30:30Z" ... >      <video ... />      <audio ... />    </recording>    <recording diskid="NetworkShare"      recordingid="20110813\_093530\_025B\_00408C1834FD"      starttime="2011-08-13T09:35:30Z"      stoptime="2011-08-13T010:30:30Z" ... >      <video ... />      <audio ... />    </recording>    <recording diskid="NetworkShare"      recordingid="20110813\_103530\_037C\_00408C1834FD"      starttime="2011-08-13T010:35:30Z"      stoptime="2011-08-14T10:10:00Z" ... >      <video ... />      <audio ... />    </recording>  </recordings></root>
```

To play the recordings, use the Recording IDs, start times and stop times from the response. The start and stop times are returned in UTC combined date and time format and must be converted before being used in the RTSP `Range` header. For example, `starttime="2011-08-12T08:12:11Z"` should be converted to `20110812T081211Z`. See [Date and time format](#date-and-time-format) for more information.

The play request below is to be inserted in a loop over the recordings from the response; `Rec.recordingid` is replaced with each of the three returned Recording IDs and _Rec.starttime_ and _Rec.stoptime_ are replaced with the returned start and stop times (converted to the proper time format).

```bash
PLAY rtsp://<servername>/axis-media/media.amp?recordingid=Rec.recordingidRange: clock=Rec.starttime-Rec.stoptime
```

### Parameters

**Recording default parameters**

The parameters in the `Recording` group define default recording settings.

Recording

| Parameter | Default value | Valid values | Access control | Description |
| --- | --- | --- | --- | --- |
| `DefaultDiskId` | Product dependent | String | admin: read, write operator: read, write viewer: read | Default Disk ID. |
| `DefaultSplitDuration` | `300` | Integer | admin: read, write operator: read, write viewer: read | The default length (in seconds) of each recording block. |

### Add continuous recording profile

Use `/axis-cgi/record/continuous/addconfiguration.cgi` to configure a continuous recording. The recording will be started when possible.

An existing recording profile cannot be changed. To change settings, the profile must be removed and replaced with a new recording profile.

This CGI is available if `Properties.LocalStorage.ContinuousRecording=yes` and `Properties.LocalStorage.NbrOfContinuousRecordingProfiles > 0`.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/continuous/addconfiguration.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/continuous/addconfiguration.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `diskid=<string>` | `<Disk ID>` | Required.The Disk ID of the disk to record to. |
| `options=<string>` | Percent-encoded string | Required.Stream options for the recording. Example: `streamprofile%3DMyProfile` or other image URL settings. |
| `eventid=<string>` | `<Event ID>` | Optional.The Event ID classifies the recording. Used with `/axis-cgi/record/list.cgi` to select recordings generated by this continuous recording configuration.Default: `continuous` |

**Response**

Responses from `/axis-cgi/record/continuous/addconfiguration.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/continuousconfigurationadd1.xsd">  <configure profile="\[profile number\]"         result="OK" />  ...</root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/continuousconfigurationadd1.xsd">  <configure profile="\[profile number\]"         result="ERROR"         errormsg="\[error description\]" />  ...</root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `configure` | Information about the new profile. | `profile` | The profile number. |
|  |  | `result` | `OK` = The configuration was added successfully. `ERROR` = An error occurred while configuring the recording. |
|  |  | `errormsg` | Description of the error. |

### List continuous recording profiles

Use `/axis-cgi/record/continuous/listconfiguration.cgi` to list information about continuous recording profiles.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/continuous/listconfiguration.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/continuous/listconfiguration.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `profile=<integer>` | Integer | Optional. The continuous recording profile to be listed. If omitted, all profiles will be listed. Value of the attribute profile from an `Add` or `List` containing continous recording profile responses. |

**Response**

Responses from `/axis-cgi/record/continuous/listconfiguration.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/continuousconfigurationlist1.xsd">  <continuousrecordingconfigurations>    <continuousrecordingconfiguration profile="\[profile number\]"          diskid="\[disk ID\]"          options="\[stream options\]"          eventid="\[event ID\]" />    ...  </continuousrecordingconfigurations></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `continuousrecordingconfigurations` | Contains the listed continuous recording profiles. |  |  |
| `continuousrecordingconfiguration` | Contains information about one continuous recording profile. | `profile` | The profile number. |
|  |  | `diskid` | The Disk ID of the disk where the recording is stored. |
|  |  | `options` | The stream options. |
|  |  | `eventid` | The profile’s Event ID. |

### Remove continuous recording profile

Use `/axis-cgi/record/continuous/removeconfiguration.cgi` to stop and remove a continuous recording profile.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/continuous/removeconfiguration.cgi?<<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/continuous/removeconfiguration.cgi?<<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `profile=<integer>` | Integer | Required. The continuous recording profile to be removed. Value of the attribute profile from an `Add` or `List` containing continous recording profile responses. |

**Response**

Responses from `/axis-cgi/record/continuous/removeconfiguration.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="    http://www.axis.com/vapix/http\_cgi/recording/continuousconfigurationremove1.xsd">  <remove profile="\[profile number\]"         result="OK" />  ...</root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="    http://www.axis.com/vapix/http\_cgi/recording/continuousconfigurationremove1.xsd">  <remove profile="\[profile number\]"         result="ERROR"         errormsg="\[error description\]" />  ...</root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `remove` | Information about the removed profile. | `profile` | The profile number. |
|  |  | `result` | `OK` = Recording was removed successfully. `ERROR` = An error occurred while removing the recording. |
|  |  | `errormsg` | Description of the error. |

### List recordings

Use `/axis-cgi/record/list.cgi` to search for recordings and list information about found recordings.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET/POST`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/list.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/list.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `listentity=<string>` | `recording` (One of `recordingid`,`starttime` or `stoptime` is required if `listentity=recording`) `eventid` `source` | Optional. `recording` = List recordings (Default). `eventid` = List all Event IDs used in recordings. `source` = List all sources used for recordings. `eventid` and `source` can be combined with the `diskid` argument. |
| `recordingid=<string>` (One of `recordingid`,`starttime` or `stoptime` is required if `listentity=recording`) | `all` `<Recording ID>` | `all` = List all recordings. `<Recording ID>` = List recording with the specified Recording ID. |
| `maxnumberofresults=<integer>` | Integer | Optional. Maximum number of recordings returned. |
| `startatresultnumber=<integer>` | Integer | Optional. Start the returned result on the n:th recording. |
| `eventid=<string>` | `<Event ID>` | Optional. Name of the event that triggered the recording. |
| `diskid=<string>` | `<Disk ID>` | Optional. The Disk ID of the disk to search for recordings on. |
| `starttime=<time>` (One of `recordingid`,`starttime` or `stoptime` is required if `listentity=recording`) | UTC ISO 8601 combined date and time. See [Date and time format](#date-and-time-format). | Optional. Include all recordings with any part of it on or after this time and date. |
| `stoptime=<time>` (One of `recordingid`,`starttime` or `stoptime` is required if `listentity=recording`) | UTC ISO 8601 combined date and time. See [Date and time format](#date-and-time-format). | Optional. Include all recordings with any part of it on or before this time and date. |
| `sortorder=<string>` | `ascending` `descending` | Optional. `ascending` = Sort the list in ascending order according to the recording start time. `descending` = Sort the list in descending order according to the recording start time. Default. |
| `source=<integer>` | `Quad` _Product dependent_ `<channel number>` | Optional. The source of the recording on a multichannel video encoder. `Quad` = The quad stream `<channel number>` = The video channel number (values are product dependent). |

**Response**

The response from `/axis-cgi/record/list.cgi` depends on the submitted `listentity`.

**List recording IDs — Success**

The following response is returned if `listentity=recordingid`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/recording/list1.xsd">    <recordings        totalnumberofrecordings="\[the number of recordings in all attached disks\]"        numberofrecordings="\[the number of matched recordings\]">        <recording            diskid="\[Disk ID\]"            recordingid="\[Recording ID\]"            starttime="\[UTC start time\]"            starttimelocal="\[Local start time\]"            stoptime="\[UTC stop time or empty string\]"            stoptimelocal="\[Local stop time or empty string\]"            recordingtype="\[Triggered, scheduled or continuous recording\]"            eventid="\[Name of the event that initiated the recording\]"            eventtrigger="\[Software input for the event that initiated the recording\]"            recordingstatus="\[Recording is active or inactive\]"            source="\[Recording source\]">            <video                mimetype="\[video mime type\]"                source="\[video source\]"                framerate="\[frame rate\]"                resolution="\[resolution\]"                width="\[width\]"                height="\[height\]" />            <audio                mimetype="\[audio mime type\]"                source="\[audio source\]"                bitrate="\[bit rate\]"                samplerate="\[sample rate\]" />        </recording>    </recordings></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `recordings` | Contains the recordings in the response. | `totalnumberofrecordings` | The number of recordings in all attached disks. If `diskid` is used, only recordings in that disk is counted. |
|  |  | `numberofrecordings` | The number of matched recordings, without taking into account`startatresultnumber` and `maxnumberofresults`. |
| `recording` | Contains information about the recording. | `diskid` | The Disk ID of the disk on which the recording is stored. |
|  |  | `recordingid` | The Recording ID. |
|  |  | `starttime` | Start time of the recording (UTC time). |
|  |  | `starttimelocal` | Start time of the recording (local time). |
|  |  | `stoptime` | Stop time of the recording (UTC time). |
|  |  | `stoptimelocal` | Stop time of the recording (local time). |
|  |  | `recordingtype` | The type of recording. `triggered` = Triggered recording. `scheduled` = Scheduled recording. `continuous` = Continuous recording. |
|  |  | `eventid` | Name of the event that initiated the recording. |
|  |  | `eventtrigger` | The trigger for the event that initiated the recording. |
|  |  | `recordingstatus` | Status of the recording. `recording` = Recording in progress. `completed` = Recording finished. `unknown` = Unknown status. |
|  |  | `source` | Multichannel video encoders only. The video channel used for the recording. |
| `video` | Contains video stream information. | `mimetype` | Video mime type. |
|  |  | `source` | Video source. |
|  |  | `framerate` | Frame rate. |
|  |  | `resolution` | Video resolution. |
|  |  | `width` | Image width in pixels. |
|  |  | `height` | Image height in pixels. |
| `audio` | Contains audio stream information. | `mimetype` | Audio mime type. |
|  |  | `source` | Audio source. |
|  |  | `bitrate` | Bit rate (optional). |
|  |  | `samplerate` | Sample rate (optional). |

**List event IDs — Success**

The following response is returned if `listentity=eventid`.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/list1.xsd">  <eventids>    <eventid>"\[Event name\]" </eventid>    ...  </eventids></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `eventids` | The events in the response. |  |  |
| `eventid` | Name of the event. |  |  |

**List sources — Success**

If `listentity=source`, the response lists the sources in which recordings were found.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/list1.xsd">  <sources>    <source>\[Source\]" </source>    ...  </sources></root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `sources` | List of the sources in which recordings were found. |  |  |
| `source` | Source identifier. For multichannel video encoders, the source is the channel number or the quad stream. |  |  |

### Start recording

Use `/axis-cgi/record/record.cgi` to start a recording. The recording will start at once and a recording ID will be returned.

info

The recording **must** be stopped by calling `/axis-cgi/record/stop.cgi`, see [Stop recording](#stop-recording).

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/record.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/record.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `diskid=<string>` | `<Disk ID>` | Required. The Disk ID of the disk to record to. Example: `SD_DISK` |
| `options=<string>` | String | Optional. Stream options for the recording. Example: `streamprofile%3DMyProfile` or other image URL settings. Please note that the system default will be used if no value is specified. |

**Response**

Responses from `/axis-cgi/record/record.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/record1.xsd">  <record recordingid="\[Recording ID\]"         result="OK" />  ...</root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/record1.xsd">  <record         result="ERROR"         errormsg="\[error description\]" />  ...</root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `record` | Information about the started recording. | `recordingid` | The Recording ID. |
|  |  | `result` | `OK` = Recording was started successfully. `ERROR` = An error occurred while starting the recording. |
|  |  | `errormsg` | Description of the error. |

### Stop recording

Use `/axis-cgi/record/stop.cgi` to stop an active recording.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/stop.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/stop.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `recordingid=<string>` | `<Recording ID>` | Required. Stop recording with the specified Recording ID. |

**Response**

Responses from `/axis-cgi/record//stop.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/stop1.xsd">  <stop recordingid="\[Recording ID\]"         result="OK" />  ...</root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/stop1.xsd">  <stop recordingid="\[Recording ID\]"         result="ERROR"         errormsg="\[error description\]" />  ...</root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `stop` | Information about the stopped recording. | `recordingid` | The Recording ID. |
|  |  | `result` | `OK` = Recording was stopped successfully. `ERROR` = An error occurred while stopping the recording. |
|  |  | `errormsg` | Description of the error. |

### Remove recording

Use `/axis-cgi/record/remove.cgi` to remove one or more recordings.

**Request**

-   **Security level**: Administrator, Operator
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/remove.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/remove.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `recordingid=<string>` | `all` `<Recording ID 1>`, `<Recording ID 2>`, ... | `all` = remove all recordings. Remove recordings with specified Recording IDs. |
| `diskid=<string>` | `<Disk ID>` | Optional. The disk ID to remove recordings from, for example `SD_DISK`. |
| `beforetime=<time>` | UTC ISO 8601 combined date and time. See [Date and time format](#date-and-time-format). | Optional. Remove all recordings with any part of it on or before this time and date. The whole recording will be removed. Active recordings will be stopped and then removed. Cannot be combined with `recordingid`. |
| `eventid=<string>` | `<Event ID>` | Optional. Remove recordings triggered by the event with this ID. Cannot be combined with `recordingid`. |
| `source=<string>` | String | Optional. Remove recordings from this video source. Cannot be combined with `recordingid`. |

**Response**

Responses from `/axis-cgi/record/remove.cgi`

**Success:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/remove1.xsd">  <remove recordingid="\[Recording ID\]"         result="OK" />  ...</root>
```

**Error:**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" ?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation=    "http://www.axis.com/vapix/http\_cgi/recording/remove1.xsd">  <remove recordingid="\[Recording ID\]"         result="ERROR"         errormsg="\[error description\]" />  ...</root>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `remove` | Information about the removed recording. | `recordingid` | The Recording ID. |
|  |  | `result` | `OK` = recording was removed successfully. `ERROR` = an error occurred while removing the recording. |
|  |  | `errormsg` | Description of the error. |

### Play recording

info

`/axis-cgi/record/play.cgi` has been deprecated and will no longer receive updates.

Use `/axis-cgi/record/play.cgi` to play a MJPEG recording as a stream. The format will be the same as the live view stream.

info

Only MJPEG recordings can be played using this method. H.264 and MPEG-4 recordings must be played using RTSP, see [Play recording using RTSP](#play-recording-using-rtsp).

> If possible, use the RTSP playback method. RTSP supports all video formats and synchronization of video and audio.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/play.cgi?<argument>=<value>\[&<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/play.cgi?<argument>=<value>\[&<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `recordingid=<string>` | `<Recording ID>` | Required. Play recording with the specified Recording ID. |
| `mediatype=<string>` | `video` `audio` | Optional. Default: `video` `video` = play video `audio` = play audio |
| `rate=<string>` | `max` numerator/denominator | Optional. The playback rate. `max` = Play as fast as possible. This is useful when an external monitoring application wants to retrieve stored recordings as fast as possible. numerator/denominator = Specifies the playback rate as a fraction of the original rate. 1/1 means the original rate. 1/2 means half the original rate. 2/1 means double the original rate. Minimum: 1/1000 Maximum: 1000/1 |
| `starttime=<time>` | UTC ISO 8601 combined date and time. See [Date and time format](#date-and-time-format). | Optional Playback start time. Playback will start at the frame closest to this time. If not specified, recording is played from the beginning. |
| `stoptime=<time>` | UTC ISO 8601 combined date and time. See [Date and time format](#date-and-time-format). | Optional Playback stop time. Playback will stop at the frame closest to this time. If not specified, the recording is played to the end. |

### Play recording using RTSP

Recordings in all media formats, with video and audio synchronization, can be played using the RTSP API.

info

When playing MJPEG , the maximum resolution is 2040x2040.

**Request**

-   **Security level**: Administrator, Operator, Viewer

Syntax:

```bash
PLAY rtsp://<servername>/axis-media/media.amp?<parameter>=<value>\[&<parameter>=<value>...\]Headerfield1: val1<CRLF>Headerfield2: val2<CRLF>Range: \[npt | clock | smpte\]=<starttime>-<stoptime><CRLF>...<CRLF>\[Body\]
```

With the following RTSP parameters values:

| RTSP parameter | Valid values | Description |
| --- | --- | --- |
| `recordingid=<string>` | `<Recording ID>` | Required. Play the recording with the specified Recording ID. |
| `pull=<bool>` | `0` `1` | Optional. `1` = Stream as fast as possible. Because the receiving part determines the transfer rate, this is only useful when tunneling RTSP over HTTP. `0` = Disabled. Default. |

The following additional header field is accepted when playing a recording:

| Header field | Description |
| --- | --- |
| `Range: [npt | clock | smpte]=<starttime>- <stoptime>` | Play recording from `starttime` to `stoptime`. `stoptime` is optional.`npt` = Normal Play Time. The `starttime` and `stoptime` times are relative to the start of the recording.`clock` = Absolute time. `starttime` and `stoptime` are UTC ISO 8601 combined date and time strings. See [Date and time format](#date-and-time-format).`smpte` = SMPTE (Society of Motion Pictures and Television Engineers) timestamps relative to the start of the recording. `starttime` and `stoptime` are SMPTE timecodes.Refer to RFC 2326 for details. |

info

Refer to the RTSP API for additional header fields and RTSP parameters.

## Export recording API
### Description

VAPIX® Export recording API is used to export an edge storage recording to a single playable file. It is possible to export a complete recording or to export a part of a recording (a video clip). The exported recording is a Matroska (.mkv) file and can be exported in an encrypted ZIP archive.

Supported functionality:

-   Retrieve supported capabilities.
-   Retrieve recording export properties such as start time, stop time and estimated file size. Recording export properties should be retrieved before exporting the recording.
-   Export recording.

#### Identification

VAPIX® Export recording API is supported if:

-   **Property**: `Properties.LocalStorage.ExportRecording=yes`
    
-   **AXIS OS**: 5.60 and later
    
-   API version 1.1 onwards supports a method to export recordings to an external disk (e.g. USB).
    
-   API version 1.2 onwards supports a method to export encrypted recordings. 256–bit AES ZIP archive encryption is currently supported.
    

### Common examples
#### Get supported XML schema versions

Use this example to retrieve a list of supported XML schema versions.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/schemaversions.cgi"
```

```bash
GET /axis-cgi/record/export/schemaversions.cgiHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ExportRecordingResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.2" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">  <SchemaVersionsSuccess>    <SchemaVersion>      <VersionNumber>1.0</VersionNumber>      <Deprecated>false</Deprecated>    </SchemaVersion>    <SchemaVersion>      <VersionNumber>1.1</VersionNumber>      <Deprecated>false</Deprecated>    </SchemaVersion>    <SchemaVersion>      <VersionNumber>1.2</VersionNumber>      <Deprecated>false</Deprecated>    </SchemaVersion>  </SchemaVersionsSuccess></ExportRecordingResponse>
```

#### Get export capabilities

Use this example to retrieve export recording capabilities. The response shows that recordings can be exported as Matroska files.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/capabilities.cgi?schemaversion=1"
```

```bash
GET /axis-cgi/record/export/capabilities.cgi?schemaversion=1Host: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ExportRecordingResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.2" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">  <CapabilitiesSuccess>    <ExportCapabilities ExportFormat="matroska">      <ExportEncryption EncryptionFormat="zip-aes256"/>    </ExportCapabilities>  </CapabilitiesSuccess></ExportRecordingResponse>
```

#### Get Recording ID

Use this example to retrieve the Recording ID. Use `/axis-cgi/record/list.cgi` from the Recording API. See [Recording API](#recording-api).

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/list.cgi?recordingid=all"
```

```bash
GET /axis-cgi/record/list.cgi?recordingid=allHost: <servername>
```

The response shows the Recording ID and information such as recording start time and stop time. Only a part of the response is shown here. For details, see [List recordings](#list-recordings).

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation= "http://www.axis.com/vapix/http\_cgi/recording/list1.xsd">  <recordings totalnumberofrecordings="30" numberofrecordings="30" >    <recording diskid="SD\_DISK" recordingid="20141211\_091153\_025B\_00408CCAD5D78" ... >      <video ... />      <audio ... />    </recording>    ...  <recordings></root>
```

#### Get recording export properties

Use these examples to retrieve recording export properties. Export properties include the recording’s start time, stop time and an estimated file size. Clients should always request recording export properties before exporting a recording.

**Retrieve information about a recording**

To retrieve export properties for a complete recording, specify the Recording ID and the Disk ID:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/properties.cgi?schemaversion=1&recordingid=20141211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK"
```

```bash
GET /axis-cgi/record/export/properties.cgi?schemaversion=1&recordingid=20141211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISKHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ExportRecordingResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.1" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">  <PropertiesSuccess>    <ExportProperties RecordingId="20141211\_091153\_025B\_00408CCAD5D78" ExportFormat="matroska" EstimatedFileSize="1234" Starttime="2014-12-11T09:11:52Z" Stoptime="2014-12-11T11:00:46Z"/>  </PropertiesSuccess></ExportRecordingResponse>
```

**Retrieve information about a recording between a time interval**

To retrieve export properties for a part of a recording, specify the start and stop times.

In this example, the complete recording’s start time is 2014-12-11 09:11:53 and the stop time is 2014-12-11 11:00:46. The part of the recording to be exported has start time 2014-12-11 09:45:11 and stop time 2014-12-11 10:10:00. These are the start and stop times specified in the export properties request.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/properties.cgi?schemaversion=1&recordingid=20141211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&starttime=2014-12-11T09:45:11Z&stoptime=2014-12-11T10:10:00Z"
```

```bash
GET /axis-cgi/record/export/properties.cgi?schemaversion=1&recordingid=20141211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&starttime=2014-12-11T09:45:11Z&stoptime=2014-12-11T10:10:00ZHost: <servername>
```

The response shows that the recording’s proper start time is 09:45:09. The proper start time is the preceding key frame that is closest to the start time specified in the request. Make sure to use the proper start time when exporting the recording.

Response:

```bash
HTTP/1.0 200 OKContent-Type: text/xml<?xml version="1.0" encoding="utf-8"?><ExportRecordingResponse xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" SchemaVersion="1.1" xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">  <PropertiesSuccess>    <ExportProperties RecordingId="20141211\_091153\_025B\_00408CCAD5D78" ExportFormat="matroska" EstimatedFileSize="1234" Starttime="2014-12-11T09:45:09Z" Stoptime="2014-12-11T10:10:00Z"/>  </PropertiesSuccess></ExportRecordingResponse>
```

**Retrieve information about a recording encrypted with 256–bit AES**

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/properties.cgi?schemaversion=1&recordingid=20121211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&encryptionformat=zip-aes256"
```

```bash
GET /axis-cgi/record/export/properties.cgi?schemaversion=1&recordingid=20121211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&encryptionformat=zip-aes256Host: <servername>
```

Response

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <PropertiesSuccess>        <ExportProperties            RecordingId="20121211\_091153\_025B\_00408CCAD5D78"            ExportFormat="matroska"            EncryptionFormat="zip-aes256"            EstimatedFileSize="1234"            Starttime="2012-12-11T09:11:52Z"            Stoptime="2012-12-11T10:10:00Z" />    </PropertiesSuccess></ExportRecordingResponse>
```

#### Export the recording

Use the following examples to export a complete or parts of a recording.

**Export a complete recording**

To export a complete recording, specify the Recording ID, the Disk ID and the export format:

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20141211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska"
```

```bash
GET /axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20141211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroskaHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Disposition: attachment; filename="20141211\_0911531234\_20141211\_1234565678.mkv"Content-Type: video/x-matroska<file data>
```

**Export part of a recording**

To export a part of a recording, specify the start and stop times retrieved in the response from `/axis-cgi/record/export/properties.cgi`.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20141211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&starttime=2014-12-11T09:45:09Z&stoptime=2014-12-11T10:10:00Z"
```

```bash
GET /axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20141211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&starttime=2014-12-11T09:45:09Z&stoptime=2014-12-11T10:10:00ZHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-Disposition: attachment; filename="20141211\_0945091234\_20141211\_1010565678.mkv"Content-Type: video/x-matroska<file data>
```

**Export a recording**

To export a recording, specify the Recording ID, the Disk ID, the export format and the start and stop times.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20121211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&starttime=2012-12-11T09:45:09Z&stoptime=2012-12-11T10:10:00Z"
```

```bash
GET /axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20121211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&starttime=2012-12-11T09:45:09Z&stoptime=2012-12-11T10:10:00ZHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-disposition: attachment; filename="20121211\_0945091234\_20121211\_1010005678.mkv"Content-Type: video/x-matroska<file data>
```

**Export an ongoing recording**

Export an ongoing recording. In this example, the recording’s start time is 2014-12-11 12:11:53 and the recording is exported at 2014-12-12 14:15:43. The exported file contains video from the start time to the export time 2014-12-12 14:15:43.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20141211\_121153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska"
```

```bash
GET /axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20141211\_121153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroskaHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-disposition: attachment; filename="20141211\_1211531234\_20141212\_1415435678.mkv"Content-Type: video/x-matroska<file data>
```

**Export a complete recording and specify the file name**

Specify the file name when exporting a recording. The file extension is added automatically.

Request:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20141211\_121153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&filename=my\_file"
```

```bash
GET /axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20141211\_121153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&filename=my\_fileHost: <servername>
```

Response:

```bash
HTTP/1.0 200 OKContent-disposition: attachment; filename="my\_file.mkv"Content-Type: video/x-matroska<file data>
```

**Export a recording in a ZIP archive encrypted with 256–bit AES**

To export a recording as a ZIP-file you must use the following request:

Request

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20121211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&password=pass\_1&encryptionformat=zip-aes256&filename=encrypted\_video"
```

```bash
GET /axis-cgi/record/export/exportrecording.cgi?schemaversion=1&recordingid=20121211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&password=pass\_1&encryptionformat=zip-aes256&filename=encrypted\_videoHost: <servername>
```

Response

```bash
HTTP/1.0 200 OKContent-disposition: attachment; filename="encrypted\_video.zip"Content-Type: application/zip<ZIP file data>
```

**Export part of a recording to USB**

1.  Start exporting the recording using `/axis-cgi/record/export/exporttoexternal.cgi`.
    
    Request:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exporttoexternal.cgi?schemaversion=1&recordingid=20121211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&starttime=2012-12-11T09:45:09Z&stoptime=2012-12-11T10:10:00Z&externaldiskid=USB\_DISK&filepath=video.mkv"
    ```
    
    ```bash
    GET /axis-cgi/record/export/exporttoexternal.cgi?schemaversion=1&recordingid=20121211\_091153\_025B\_00408CCAD5D78&diskid=SD\_DISK&exportformat=matroska&starttime=2012-12-11T09:45:09Z&stoptime=2012-12-11T10:10:00Z&externaldiskid=USB\_DISK&filepath=video.mkvHost: <servername>
    ```
    
    Response:
    
    ```bash
    <?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <ExportToExternalSuccess>        <ExportToExternal JobId="1" FilePath="video.mkv" />    </ExportToExternalSuccess></ExportRecordingResponse>
    ```
    
2.  Check the progress.
    
    Request:
    
    -   curl
    -   HTTP
    
    ```bash
    curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/getjobstatus.cgi?schemaversion=1&jobid=1"
    ```
    
    ```bash
    GET /axis-cgi/record/export/getjobstatus.cgi?schemaversion=1&jobid=1Host: <servername>
    ```
    
    Response:
    
    ```bash
    <?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <GetJobStatusSuccess>        <JobStatus Status="In Progress" Progress="45" />    </GetJobStatusSuccess></ExportRecordingResponse>
    ```
    

### API specification
#### Get schema versions

Use `/axis-cgi/record/export/schemaversions.cgi` to retrieve the supported XML schema versions.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/schemaversions.cgi"
```

```bash
GET /axis-cgi/record/export/schemaversions.cgiHost: <servername>
```

This CGI has no arguments

**Response**

Responses from `/axis-cgi/record/export/schemaversions.cgi`

**Success**

A successful request returns the supported schema versions.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    SchemaVersion="1.1"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <SchemaVersionsSuccess>        <SchemaVersion>            <VersionNumber>\[major.minor\]</VersionNumber>            <Deprecated>\[true/false\]</Deprecated>        </SchemaVersion>        <SchemaVersion>            <VersionNumber>\[major.minor\]</VersionNumber>            <Deprecated>\[true/false\]</Deprecated>        </SchemaVersion>        \[...\]    </SchemaVersionsSuccess></ExportRecordingResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ExportRecordingResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `SchemaVersionsSuccess` | Successful request. |
| `SchemaVersion` | Contains one schema version. |
| `VersionNumber` | Schema version. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `Deprecated` | If `true`, this version of the XML Schema is deprecated and should not be used. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-export-recording-api).

Error codes: 10, 20, 40

#### Get capabilities

Use `/axis-cgi/record/export/capabilities.cgi` to retrieve capabilities supported by the Export Recording API.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/capabilities.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/record/export/capabilities.cgi?<argument>=<value>Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |

**Response**

Responses from `/axis-cgi/record/export/capabilities.cgi`

**Success**

A successful request returns supported capabilities.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    SchemaVersion="1.1"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <CapabilitiesSuccess>        <ExportCapabilities ExportFormat="\[Format 1\]" />        <ExportCapabilities ExportFormat="\[Format 2\]" />        ...    </CapabilitiesSuccess></ExportRecordingResponse>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `ExportRecordingResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |  |  |
| `CapabilitiesSuccess` | Successful request. |  |  |
| `ExportCapabilities` | Contains one Export Recording API capability. | `ExportFormat` | Supported media format. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-export-recording-api).

Error codes: 10, 20, 40

#### Get export properties

Use `/axis-cgi/record/export/properties.cgi` to retrieve recording export properties. Export properties include the recording’s start time, stop time and an estimated file size. The start time in the response is the proper start time, that is, the preceding key frame that is closest to the requested start time.

Clients should always request recording properties before exporting a recording.

To retrieve properties from a specific time interval, specify the start and stop times in the request.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/properties.cgi?<argument>=<value>&\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/export/properties.cgi?<argument>=<value>&\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `recordingid=<string>` | String | Required. The recording’s Recording ID. |
| `diskid=<string>` | String | Required. Disk ID of the disk where the recording is stored. |
| `starttime=<time>` | UTC ISO 8601 combined date and time. (See [Date and time format](#date-and-time-format)) | Optional. Start time. Use if retrieving recording export properties for a part of a recording.If omitted, start time is set to the recording’s beginning. |
| `stoptime=<time>` | UTC ISO 8601 combined date and time. See [Date and time format](#date-and-time-format) | Optional. Stop time. Use if retrieving recording export properties for a part of a recording.Ongoing recordings: If `stoptime` is omitted, stop time is set to the time the request is sent.Finished recordings: If `stoptime` is omitted, stop time is set to the recording end time. |
| `exportformat=<string>` | String | Optional. The media format that the recording should be exported to. |
| `encryptionformat=<string>` | String | Optional. Specifies the encryption format of the recording. |

**Response**

Responses from `/axis-cgi/record/export/properties.cgi`

**Success**

A successful request returns information about the recordings.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <PropertiesSuccess>        <ExportProperties            RecordingId="\[Recording ID\]"            ExportFormat="\[Format\]"            EncryptionFormat="\[Encryption format\]"            EstimatedFileSize="\[File size\]"            Starttime="\[Start time\]"            Stoptime="\[Stop time\]" />    </PropertiesSuccess></ExportRecordingResponse>
```

Supported elements, attributes and values:

| Element | Description | Attribute | Description |
| --- | --- | --- | --- |
| `ExportRecordingResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |  |  |
| `PropertiesSuccess` | Successful request. |  |  |
| `ExportProperties` | Contains information about one recording. | `RecordingId` | Recording ID. |
|  |  | `ExportFormat` | Media format. |
|  |  | `EncryptionFormat` | Encryption format. |
|  |  | `EstimatedFileSize` | Estimated file size. Unit: kilobytesIf the file size cannot be estimated, the size is set to `-1`. |
|  |  | `Starttime` | Recording start time.The returned start time is set to the preceding key frame that is closest to the start time in the request. |
|  |  | `Stoptime` | Recording stop time. |

**Error**

If an error occurred, a `GeneralError` response is returned. See [General error response](#general-error-response-export-recording-api).

Error codes: 10, 20, 40, 110, 120, 130, 140, 150, 160, 170, 180

#### Export recording

Use `/axis-cgi/record/export/exportrecording.cgi` to export a recording. To only export a part of a recording, specify the start and stop times.

The recording is exported as a single playable file in the specified export format, for example Matroska. If no file name is specified, the file is given a default name constructed from the recording’s start and stop times.

**Request**

-   **Security level**: Administrator, Operator, Viewer
-   **Method**: `GET`

Syntax:

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exportrecording.cgi?<argument>=<value>&\[<argument>=<value>...\]"
```

```bash
GET /axis-cgi/record/export/exportrecording.cgi?<argument>=<value>&\[<argument>=<value>...\]Host: <servername>
```

With the following query string parameters:

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. See [XML schemas](/vapix/network-video/#xml-schemas). |
| `recordingid=<string>` | String | Required. Recording ID of the recording to export |
| `diskid=<string>` | String | Required. Disk ID of the disk where the recording is stored. |
| `exportformat=<string>` | String | Required. Media format to export the recording to. Use `/axis-cgi/record/export/properties.cgi` to retrieve supported media formats. |
| `starttime=<time>` | UTC ISO 8601 combined date and time. (See [Date and time format](#date-and-time-format)) | Optional. Start time. Use if exporting a part of a recording.The start time should match a key frame; use the start time from the response from `/axis-cgi/record/export/properties.cgi`.If start time does not match a key frame, the start time is set to the closest preceding key frame. If the set start time is outside the recording, a best effort response is returned.If `starttime` is omitted, start time is set to the recording’s beginning. |
| `stoptime=<time>` | UTC ISO 8601 combined date and time. (See [Date and time format](#date-and-time-format)) | Optional. Stop time. Use if exporting a part of a recording.Ongoing recordings: If `stoptime` is omitted, stop time is set to the time the export recording request is sent.Finished recordings: If `stoptime` is omitted, stop time is set to the recording end time.If the set stop time is outside the recording, a best effort response is returned. |
| `filename=<string>` | String | Optional. Name of the exported file. The name must be UTF-8 encoded. File extension will be added automatically and should not be specified. |
| `password=<string>` | String | Optional. Specifies if the exported file should be password protected. It is recommended to not have a password exceed 99 characters, as some applications may not be able to run it. Maximum length is 512 bytes. |
| `encryptionformat=<string>` | String | Required if a password has been set and also specifies the encryption format. Please note that a password must be set before you can use `encryptionformat`. |

**Response**

Responses from `/axis-cgi/record/export/exportrecording.cgi`

**Success**

A successful request returns the exported recording as a single playable file. If `filename` was specified in the request, the file is named accordingly. If `filename` was not specified, the file is given a default name. The default name is constructed using the exported recording’s start and stop times. Start time is set to the preceding key frame that is closest to the requested start time. Stop time is the requested stop time or the end of the recording. If a password has been set the file will be encrypted according to the encryption format. Recordings encrypted in a ZIP archive and without a specified file name will receive a randomized name in the format `XXXXXX.zip`.

**Success Matroska**

-   **HTTP Code**: `200 OK`
-   **Content-Disposition**: `attachment; filename="YYYYMMDD_HHMMSS_YYYYMMDD_HHMMSS.mkv"`
-   **Content-Type**: `video/x-matroska`

Body:

```bash
HTTP/1.0 200 OKContent-disposition: attachment; filename="20121219\_123456\_20121220\_123456.mkv"Content-Type: video/x-matroska<file data>
```

**Success ZIP archive**

-   **HTTP Code**: `200 OK`
-   **Content-Disposition**: `attachment; filename="XXXXXX.zip"`
-   **Content-Type**: `application/zip`

Body:

```bash
HTTP/1.0 200 OKContent-disposition: attachment; filename="XXXXXX.zip"Content-Type: application/zip<file data>
```

#### Export a recording to an external disk

Available from version 1.1.

Export the recording to an external disk (e.g. USB). It is not possible to run several export-to-external simultaneously.

**Request**

-   **Security level**: Viewer
-   **Method**: `GET`

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/exporttoexternal.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/record/export/exporttoexternal.cgi?<argument>=<value>Host: <servername>
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. |
| `recordingid=<string>` | String | Required. Recording ID of the recording to export. |
| `diskid=<string>` | String | Required. Disk ID of the disk where the recording is stored. |
| `externaldiskid=<string>` | String | Required. Specifies the disk the recording should be exported to. Allowed values are `USB_DISK`. |
| `exportformat=<string>` | String | Required. Media format to export the recording to. Use `/axis-cgi/record/export/properties.cgi` to retrieve supported media formats. |
| `starttime=<time>` | UTC ISO 8601 combined data and time. (See [Date and time format](#date-and-time-format)) | Optional. Start time. Use if exporting a port of a recording.The start time should match a key frame; use the start time from the response from `/axis-cgi/record/export/properties.cgi`.If start time does not match a key frame, the start time is set to the closest preceding key frame. If the set start time is outside the recording, a best effort response is returned.If `starttime` is omitted, start time is set to the recording’s beginning. |
| `stoptime=<time>` | UTC ISO 8601 combined data and time. (See [Date and time format](#date-and-time-format)) | Optional. Stop time. Use if exporting a part of a recording.Ongoing recordings: If `stoptime` is omitted, stop time is set to the time the export recording request is sent.Finished recordings: If `stoptime` is omitted, stop time is set to the recording end time. |
| `filepath=<string>` | String | Optional. Specifies where the exported recording will be saved and what file name it will get. Any missing directories in the path will be created. If no file path is specified, a default file name will be used and the exported recording is saved to the root of the external disk. No `..` are allowed in the path. |
| `password=<string>` | String | Optional. Specifies if the exported file should be password protected. It is recommended to not have a password exceed 99 characters, as some applications may not be able to run it. Maximum length is 512 bytes. |
| `encryptionformat=<string>` | String | Required if a password has been set and also specifies the encryption format. Please note that a password must be set before you can use `encryptionformat`. |

**Response**

Returns a job ID that can be used to track the status of the export.

**Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <ExportToExternalSuccess>        <ExportToExternal JobId="\[jobid1\]" FilePath="\[filepath1\]" />    </ExportToExternalSuccess></ExportRecordingResponse>
```

**Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></ExportRecordingResponse>
```

#### Get job status

Available from version 1.1.

Request to query the job status of a specified job.

**Request**

-   **Security level**: Viewer
-   **Method**: `GET`

Syntax

-   curl
-   HTTP

```bash
curl --request GET \\  --anyauth \\  --user "<username>:<password>" \\  "http://<servername>/axis-cgi/record/export/getjobstatus.cgi?<argument>=<value>"
```

```bash
GET /axis-cgi/record/export/getjobstatus.cgi?<argument>=<value>Host: <servername>
```

| Parameter | Valid values | Description |
| --- | --- | --- |
| `schemaversion=<integer>` | Integer | Required. The major version of the XML Schema to use for the response. |
| `jobid=<integer>` | Integer | Required. Specifies the job that the status should be returned for. |

**Responses**

Returns the job status. It is possible to receive the job status for all ongoing jobs and the last five completed ones.

**Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

**Body:**

For ongoing and successfully completed jobs:

Status can be either `In Progress` or `Done`, while `Progress` is an integer with a value between 0–100 (or -1 if the progress is unknown).

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <GetJobStatusSuccess>        <JobStatus Status="\[status\]" Progress="\[progress\]" />    </GetJobStatusSuccess></ExportRecordingResponse>
```

For failed jobs:

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <GetJobStatusSuccess>        <GeneralError>            <ErrorCode>\[code\]</ErrorCode>            <ErrorDescription>\[description\]</ErrorDescription>        </GeneralError>    </GetJobStatusSuccess></ExportRecordingResponse>
```

**Error**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    SchemaVersion="1.2"    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <GeneralError>        <ErrorCode>\[code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></ExportRecordingResponse>
```

#### General error response

General error response from Export recording API.

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `text/xml`

Body:

```bash
<?xml version="1.0" encoding="utf-8" ?><ExportRecordingResponse    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"    SchemaVersion="1.1"    xsi:noNamespaceSchemaLocation="http://www.axis.com/vapix/http\_cgi/exportrecording1.xsd">    <GeneralError>        <ErrorCode>\[error code\]</ErrorCode>        <ErrorDescription>\[description\]</ErrorDescription>    </GeneralError></ExportRecordingResponse>
```

Supported elements, attributes and values:

| Element | Description |
| --- | --- |
| `ExportRecordingResponse` | Contains the response. For information about XML schema versions, see [XML schemas](/vapix/network-video/#xml-schemas). |
| `GeneralError` | Error. |
| `ErrorCode` | A numeric error code. See table below. |
| `ErrorDescription` | Description of the error. |

| Error code | Description | CGI |
| --- | --- | --- |
| `10` | Error while processing the request. | All |
| `20` | Invalid request. | All |
| `40` | Specified version is not supported. | All |
| `110` | Recording not found. | `/axis-cgi/record/export/properties.cgi` |
| `120` | Invalid start time. | `/axis-cgi/record/export/properties.cgi` |
| `130` | Invalid stop time. | `/axis-cgi/record/export/properties.cgi` |
| `140` | Invalid start time. The requested start time is after the stop time. | `/axis-cgi/record/export/properties.cgi` |
| `150` | Invalid start time. The requested start time is after the recording’s stop time. | `/axis-cgi/record/export/properties.cgi` |
| `160` | Invalid stop time. The requested stop time is before the recording’s start time. | `/axis-cgi/record/export/properties.cgi` |
| `170` | Invalid export format. | `/axis-cgi/record/export/properties.cgi` |
| `180` | Requested export format is not compatible with the media type. | `/axis-cgi/record/export/properties.cgi` |
| `190` | Job not found. | `/axis-cgi/record/export/getjobstatus.cgi` |
| `200` | Invalid external disk. | `/axis-cgi/record/export/exporttoexternal.cgi` |
| `210` | Unusable external disk. | `/axis-cgi/record/export/exporttoexternal.cgi` |
| `220` | Maximum number of jobs reached. | `/axis-cgi/record/export/exporttoexternal.cgi` |
| `230` | Invalid file path. | `/axis-cgi/record/export/exporttoexternal.cgi` |
| `240` | Invalid password. | `/axis-cgi/record/export/exporttoexternal.cgi` |
| `250` | Invalid encryption format. | `/axis-cgi/record/export/properties.cgi`, `/axis-cgi/record/export/exporttoexternal.cgi` |
| `260` | Password not set. | `/axis-cgi/record/export/exporttoexternal.cgi` |
| `270` | Encryption format not set. | `/axis-cgi/record/export/exporttoexternal.cgi` |
| `280` | Requested encryption format is not compatible with requested export format. | `/axis-cgi/record/export/properties.cgi` `/axis-cgi/record/export/exporttoexternal.cgi` |

## Edge storage events and actions
### Event recording ongoing

The Recording ongoing event is emitted when there is an ongoing recording to an edge storage device.

**Topic**

-   **Name**: `tnsaxis:Storage/tnsaxis:Recording`
-   **Type**: Stateful
-   **Nice name**: `Recording ongoing`

**Source instance**

None

**Data instance**

-   **Nice name**: Recording ongoing
-   **Type**: boolean
-   **Name**: recording
-   **isPropertyState**: true

### Event storage disruption detection

The Storage disruption detection event is true when there is a problem with a storage device.

The event is emitted with data instance `disruption` set to `true` in the following situations: storage is unmounted, storage is mounted in read-only mode, on read/write errors, storage is removed, storage is full, storage is locked.

The event is emitted with data instance `disruption` set to `false` in the following situations: storage is mounted successfully with read/write permissions, a storage that was locked has been unlocked, data has been successfully removed so that the storage is no longer full.

Use `/axis-cgi/disks/checkdisk.cgi` and/or `/axis-cgi/disks/list.cgi` to troubleshoot storage problems.

**Topic**

-   **Name**: `tnsaxis:Storage/tnsaxis:Disruption`
-   **Type**: Stateful
-   **Nice name**: `Storage Disruption`

**Source instance**

-   Name:
    
    disk\_id
    
-   **Type**: string
    
-   **Nice name**: Disk
    

**Data instance**

-   **Nice name**: Storage Disruption
-   **Type**: boolean
-   **Name**: `disruption`
-   **isPropertyState**: `true`

### Record video action template

Use the Record Video action to record video to a storage device, for example an SD card or a network share. For information about how to retrieve recordings, see [Recording API](#recording-api).

This action can be run as:

-   **fixed action** — video is recorded during a pre-event and post-event time
    
-   **unlimited action** — video is recorded during a pre-event time, while the event is running and during a post-event time
    
-   Action ID
    
    `com.axis.action.fixed.recording.storage`
    
-   Action ID
    
    `com.axis.action.unlimited.recording.storage`
    

| Parameter | Valid values | Description |
| --- | --- | --- |
| `stream_options` | Percent-encoded string | List of stream parameters such as resolution, compression etc. All parameters supported by RTSP and HTTP stream requests can be used. See [Parameter specification RTSP URL](/vapix/network-video/video-streaming/#parameter-specification-rtsp-url) and [Video streaming over HTTP](/vapix/network-video/video-streaming/#video-streaming-over-http). Example: `stream_options=resolution%3D640x480%26compression%3D30%26rotation%3D180` |
| `pre_duration` | Unsigned integer | Pre-trigger time in milliseconds. Specify the number of milliseconds to include from the time immediately before the event. |
| `post_duration` | Unsigned integer | Post-trigger time in milliseconds. Specify the number of milliseconds to include from the time immediately after the event. |
| `storage_id` | Disk ID | Disk ID of the storage device to record to. Use `/axis-cgi/disks/list.cgi?diskid=all` to list the disks supported by the product. For information about storage disks, see [Disk management API](#disk-management-api). |

### Recording group video action template

By using this action along with [Recording group](/vapix/network-video/recording-group/) allows you to record video to a recording group, for example on an SD card or a network share. This is useful when you want to set up a recording group that with multiple actions creates a single recording, even when two or more actions are active in parallel.

This action can be run as:

-   **unlimited action** — video is recorded during a pre-duration time, while the event is running and during a post-duration time.
    
-   Action ID
    
    `com.axis.action.unlimited.recording_group.storage`
    

| Parameter | Valid values | Description |
| --- | --- | --- |
| `recording_group_id` | Recording group ID | Recording group ID for the recording group to record to. |