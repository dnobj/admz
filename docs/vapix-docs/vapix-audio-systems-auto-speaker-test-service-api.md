---
title: Auto speaker test service API
url: "https://developer.axis.com/vapix/audio-systems/auto-speaker-test-service-api/"
category: vapix
subcategory: audio-systems
sha256: 64754d8beb7b2804f987bb9e4ddf33b677ce6640686af7b8feaf2bc784797296
scraped_at: "2026-01-09T15:18:26.851Z"
page_height: 11095
---

# Auto speaker test service API

## Description

VAPIX® Auto Speaker Test Service API is used to calibrate and execute speaker tests. Speaker tests executed by this service compare a series of test tones with reference values to determine if the speaker works normally. When the test is completed, the service emits a `tns1:Device/tnsaxis:SpeakerTest/TestResult` event with the test result.

Speaker test **calibration** must be run before tests can be executed. During calibration, the speaker plays a series of test tones. The test tones are registered by the built-in microphone and saved as reference values.

The reference values depend on how the speaker is mounted and on its surrounding environment. Calibration should therefore be run when the speaker is installed in its final environment. If the speaker is moved or its surrounding changes, for example, a wall is built or removed, the speaker test should be re-calibrated.

info

If the acoustic path is blocked or if the speaker is malfunctioning during calibration, subsequent speaker tests may report erroneous results. Make sure that someone at the installation site listens to the test tones during calibration.

Speaker test **execution** can be run remotely any time after calibration. During execution, the same series of test tones is played and registered using the built-in microphone. The registered values are then compared to the reference values.

The test result is emitted as a `tns1:Device/tnsaxis:SpeakerTest/TestResult` event but can also be retrieved using `GetSpeakerTestReport`.

For Axis products with multiple audio channels, the speaker test is run on all channels.

### Identification

The Auto Speaker Test Service API is supported if:

-   **Property**: `Properties.API.SpeakerTest.AutomaticTest=yes`
-   **Property**: `Properties.API.SpeakerTest.Version=1.0`
-   **Namespace**: `axast = http://www.axis.com/vapix/axast`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples

API requests can be constructed using JSON or using a simplified key-value format. The request syntax is described in [JSON and simplified key-value requests](/vapix/intercom/call-service-api/#json-and-simplified-key-value-requests).

The speaker test is calibrated using `axast:CalibrateSpeakerTest`. The response is empty.

Calibrate speaker test JSON request:

```bash
{    "axast:CalibrateSpeakerTest": {}}
```

JSON response:

```bash
{}
```

Calibrate speaker test simplified request:

```bash
format=simple&action=axast:CalibrateSpeakerTest
```

Simplified response (empty):

```bash

```

During calibration, the speaker test report shows status **Pending**. The test and calibration timestamps are both empty.

Get test report JSON request:

```bash
{    "axast:GetSpeakerTestReport": {}}
```

JSON response:

```bash
{    "SpeakerTestReport": {        "SpeakerTestStatus": "Pending",        "TestTimestamp": "",        "CalibrationTimestamp": ""    }}
```

Get test report simplified request:

```bash
format=simple&action=axast:GetSpeakerTestReport
```

Simplified response:

```bash
SpeakerTestReport\_SpeakerTestStatus=PendingSpeakerTestReport\_TestTimestamp=SpeakerTestReport\_CalibrationTimestamp=
```

When calibration is completed, the speaker test report shows status **Calibrated**. The test timestamp is empty and the calibration timestamp shows the calibration time.

Get test report JSON request:

```bash
{    "axast:GetSpeakerTestReport": {}}
```

JSON response:

```bash
{    "SpeakerTestReport": {        "SpeakerTestStatus": "Calibrated",        "TestTimestamp": "",        "CalibrationTimestamp": "2015-05-28T16:30:02Z"    }}
```

Get test report simplified request:

```bash
format=simple&action=axast:GetSpeakerTestReport
```

Simplified response:

```bash
SpeakerTestReport\_SpeakerTestStatus=CalibratedSpeakerTestReport\_TestTimestamp=SpeakerTestReport\_CalibrationTimestamp=2015-05-28T16:30:02Z
```

The speaker test is executed using `axast:PerformSpeakerTest`. The response is empty.

Perform speaker test JSON request:

```bash
{    "axast:PerformSpeakerTest": {}}
```

JSON response:

```bash
{}
```

Perform speaker test simplified request:

```bash
format=simple&action=axast:PerformSpeakerTest
```

Simplified response (empty):

```bash

```

During the speaker test, the test report shows status **Pending**. The test timestamp is empty and the calibration timestamp shows when the test was calibrated.

Get test report JSON request:

```bash
{    "axast:GetSpeakerTestReport": {}}
```

JSON response:

```bash
{    "SpeakerTestReport": {        "SpeakerTestStatus": "Pending",        "TestTimestamp": "",        "CalibrationTimestamp": "2015-05-28T16:30:02Z"    }}
```

Get test report simplified request:

```bash
format=simple&action=axast:GetSpeakerTestReport
```

Simplified response:

```bash
SpeakerTestReport\_SpeakerTestStatus=PendingSpeakerTestReport\_TestTimestamp=SpeakerTestReport\_CalibrationTimestamp=2015-05-28T16:30:02Z
```

When the speaker test is completed and the speaker works normally, the test report shows status **OK**. The test timestamp shows the time when the test was executed.

Get test report JSON request:

```bash
{    "axast:GetSpeakerTestReport": {}}
```

JSON response:

```bash
{    "SpeakerTestReport": {        "SpeakerTestStatus": "OK",        "TestTimestamp": "2015-06-10T16:38:45Z",        "CalibrationTimestamp": "2015-05-28T16:30:02Z"    }}
```

Get test report simplified request:

```bash
format=simple&action=axast:GetSpeakerTestReport
```

Simplified response:

```bash
SpeakerTestReport\_SpeakerTestStatus=OKSpeakerTestReport\_TestTimestamp=2015-06-10T16:38:45ZSpeakerTestReport\_CalibrationTimestamp=2015-05-28T16:30:02Z
```

## Speaker test API documentation
### Data structures
#### SpeakerTestReport

The `SpeakerTestReport` data structure contains the test report of the latest speaker test. It contains the following mandatory fields.

| Field | Type | Description |
| --- | --- | --- |
| `SpeakerTestStatus` | `SpeakerTestStatus` | The test result. See [Enumeration: SpeakerTestStatus](#enumeration-speakerteststatus). |
| `TestTimestamp` | `dateTime` | The date and time that the test was performed. Empty if no test has been performed. |
| `CalibrationTimestamp` | `dateTime` | The date and time when the test was calibrated. Empty if the test is not calibrated. |

#### Enumeration: SpeakerTestStatus

`SpeakerTestStatus` is a non-normative enum that contains the result of the speaker test.

| Value | Description |
| --- | --- |
| `OK` | The speaker hardware has been tested. The speaker is working normally. |
| `Failed` | The speaker hardware has been tested. The speaker does not work normally. |
| `Calibrated` | The speaker test is calibrated. No speaker test has been performed. |
| `Pending` | Speaker test calibration or execution is in progress. |
| `Uncalibrated` | (Factory default value) The speaker test is not calibrated. |
| `DisabledInHardware` | The built-in microphone is disabled. It is not possible to run speaker test calibration or execution. |
| `InternalError` | The speaker test failed due to an internal error. Check the system log for information. |

### CalibrateSpeakerTest command

Use the `CalibrateSpeakerTest` command to initiate speaker test calibration. Calibration starts as soon as possible when the command has been sent. The calibration result is available in `SpeakerTestStatus` in the `SpeakerTestReport` and the calibration time is available in `CalibrationTimestamp`.

-   **Security level**: Administrator
-   **Method**: `GET/POST`
-   **Command**: `axast:CalibrateSpeakerTest`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `axast:DisabledInHardware` | Calibration could not be performed because the microphone is disabled in the hardware. |
| `env:Receiver` `ter:Action` `ter:Failure` | Internal error in the Axis product. Check the logs for more information. |

### PerformSpeakerTest command

Use the `PerformSpeakerTest` command to initiate a speaker test. The speaker test will be executed as soon as possible when the command has been sent. The result is available in `SpeakerTestReport`.

-   **Security level**: Administrator
-   **Method**: `GET/POST`
-   **Command**: `axast:PerformSpeakerTest`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{}
```

The response is empty.

| Fault codes | Description |
| --- | --- |
| `env:Receiver` `ter:Action` `axast:DisabledInHardware` | The speaker test could not be executed because the microphone is disabled in the hardware. |
| `env:Receiver` `ter:Action` `axast:DeviceNotCalibrated` | The speaker test could not be performed because the test is not calibrated.Calibration must be run before the speaker test. |
| `env:Receiver` `ter:Action` `ter:Failure` | Internal error in the Axis product. Check the logs for more information. |

### GetSpeakerTestReport command

Use the `GetSpeakerTestReport` command to retrieve the speaker test report from the latest speaker test.

-   **Security level**: Administrator
-   **Method**: `GET/POST`
-   **Command**: `axast:GetSpeakerTestReport`

Message name: Request

```bash
{}
```

The request is empty.

Message name: Response

```bash
{  "SpeakerTestReport": { SpeakerTestReport }}
```

with the following data fields:

| Data field | Valid values | Description |
| --- | --- | --- |
| `SpeakerTestReport` | `SpeakerTestReport` | The current speaker test report. See [SpeakerTestReport](#speakertestreport). |

## Speaker test result event

The `tns1:Device/tnsaxis:SpeakerTest/TestResult` event is emitted when a speaker test is finished and contains the result of the test.

Use `aev:GetEventInstances` to retrieve the event declaration.

Event declaration:

```bash
<tns1:Device>    <tnsaxis:SpeakerTest>        <TestResult wstop:topic="true">            <aev:MessageInstance aev:isProperty="false">                <aev:SourceInstance>                    <aev:SimpleItemInstance Type="xsd:string" Name="DeviceUUID">                        <aev:Value>\[DeviceID\]</aev:Value>                    </aev:SimpleItemInstance>                </aev:SourceInstance>                <aev:DataInstance>                    <aev:SimpleItemInstance Type="xsd:string" Name="SpeakerTestStatus">                        <aev:Value>OK</aev:Value>                        <aev:Value>Failed</aev:Value>                    </aev:SimpleItemInstance>                </aev:DataInstance>            </aev:MessageInstance>        </TestResult>    </tnsaxis:SpeakerTest></tns1:Device>
```

The topic is `tns1:Device/tnsaxis:SpeakerTest/TestResult`. `SourceInstance` specifies the device that emitted the event. `DataInstance` contains the result of the speaker test.

### Perform test action

The following template should be used when you wish to initiate a speaker test in the same manner as the API call `PerformSpeakerTest`.

```bash
<aa:ActionTemplate>    <aa:TemplateToken>com.axis.action.fixed.autospeakertest.performtest</aa:TemplateToken></aa:ActionTemplate>
```