---
title: Audit log
url: "https://developer.axis.com/vapix/network-video/audit-log/"
category: vapix
subcategory: network-video
sha256: 958fcc2b61f1f99d61dd6406b28d160bd21cb5817b0cddd815b086522a41bf16
scraped_at: "2026-01-09T15:19:20.060Z"
page_height: 5058
---

# Audit log

The VAPIX® Audit Log API allows users to retrieve audit logs from Axis devices. This includes fetching the entire audit log, specific tails of the log, and the version of the CGI `/axis-cgi/auditlog.cgi`.

## Identification

-   API discovery: `id=audit-log`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Use cases
### Retrieve entire audit log

Request the entire audit log:

`http://<servername>/axis-cgi/auditlog.cgi`

**Response**:

-   HTTP Code: `200 OK`
-   Content-Type: `text/plain`

_Body_:

`audit log entries`

### Retrieve tail of audit log

Request the last nine audit log entries:

`http://<servername>/axis-cgi/auditlog.cgi?tail=9`

**Response**:

-   HTTP Code: `200 OK`
-   Content-Type: `text/plain`

_Body_:

```bash
2025-07-22T15:38:25.307+00:00 axis-abcdef123456 \[ INFO    \] fwmgr\[4518\]: Entity Management: Upgrade completed (12.6+snapshot-20250722).2025-07-22T15:39:57.364+00:00 axis-abcdef123456 \[ INFO    \] sshd-session\[7445\]: Authentication: judy@192.168.0.87 Authentication failed (SSH).2025-07-22T15:39:58.917+00:00 axis-abcdef123456 \[ INFO    \] sshd-session\[7445\]: Authentication: judy@192.168.0.87 Authentication successful (SSH).2025-07-22T15:40:08.825+00:00 axis-abcdef123456 \[ INFO    \] sshd-session\[7457\]: Authentication: chris@192.168.0.87 Authentication failed (SSH).2025-07-22T15:40:13.561+00:00 axis-abcdef123456 \[ INFO    \] sshd-session\[7457\]: Authentication: chris@192.168.0.87 Authentication successful (SSH).2025-07-22T15:40:42.707+00:00 axis-abcdef123456 \[ INFO    \] sshd-session\[7457\]: Authentication: chris Logged out (SSH).2025-07-22T15:40:46.612+00:00 axis-abcdef123456 \[ INFO    \] sshd-session\[7499\]: Authentication: judy@192.168.0.87 Authentication failed (SSH).2025-07-22T15:40:48.365+00:00 axis-abcdef123456 \[ INFO    \] sshd-session\[7499\]: Authentication: judy@192.168.0.87 Authentication successful (SSH).2025-07-22T16:09:59.358+00:00 axis-abcdef123456 \[ INFO    \] sshd-session\[7445\]: Authentication: judy Logged out (SSH).
```

### Retrieve CGI version

Request the current CGI version:

`http://<servername>/axis-cgi/auditlog.cgi?version=true`

**Response**:

-   HTTP Code: `200 OK`
-   Content-Type: `text/plain`

_Body_:

`1.0.0`

## API specifications

-   Security level: Admin
-   Method: `GET`

_Syntax_:

`http://<servername>/axis-cgi/auditlog.cgi[?<parameter>=<value>]`

| Parameter | Valid value | Description |
| --- | --- | --- |
| `tail=` | Integer | _Optional_ The number of recent entries that should be retrieved. All entries will be retrieved if this parameter is not specified. |
| `version=` | `true`  
`false` | _Optional_ Specifies whether to retrieve the CGI version. Defaults to `false` if the parameter is not specified. If it is set to `true`, it will take precedence over other parameters and only the version number will be retrieved. |

Invalid parameters will be ignored and the entire audit log will be returned if no other parameter is specified.

### Retrieve audit log

Request a list of the entire audit log, or the tail end of it.

-   Security level: Admin
-   Method: `GET`

**Request**

`http://<servername>/axis-cgi/auditlog.cgi[?tail=<value>]`

| Parameter | Valid value | Description |
| --- | --- | --- |
| `tail=` | Integer | _Optional_ The number of recent entries that should be retrieved. All entries will be retrieved if this parameter is not specified. |

The `<value>` specifies the number of recent entries that should be retrieved from the tail end of the audio log.

**Response - Success**

Returns the audit log entries.

-   HTTP Code: `200 OK`
-   Content-Type: `text/plain`

`audit log entries`

**Response - Error**

| HTTP code | Description |
| --- | --- |
| `400 Bad Request` | An invalid request method was provided. |
| `401 Unauthorized` | The user was unauthorized. |
| `500 Internal Server Error` | Some unexpected error occurred. |

### Retrieve the CGI version

Check the current CGI version.

-   Security level: Admin
-   Method: `GET`

**Request**

`http://<servername>/axis-cgi/auditlog.cgi?version=true`

| Parameter | Valid value | Description |
| --- | --- | --- |
| `version=` | `true`  
`false` | _Optional_ Specifies whether to retrieve the CGI version. Defaults to `false` if the parameter is not specified. If it is set to `true`, it will take precedence over other parameters and only the version number will be retrieved. |

**Response - Success**

Returns the CGI version.

-   HTTP Code: `200 OK`
-   Content-Type: `text/plain`

`CGI version number`

**Response - Error**

| HTTP code | Description |
| --- | --- |
| `400 Bad Request` | An invalid request method was provided. |
| `401 Unauthorized` | The user was unauthorized. |