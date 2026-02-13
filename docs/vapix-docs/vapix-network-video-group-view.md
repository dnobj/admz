---
title: Group View
url: "https://developer.axis.com/vapix/network-video/group-view/"
category: vapix
subcategory: network-video
sha256: b6408872c689ad3487fa064b291f03254111876295be9bad721f26fac5808fb7
scraped_at: "2026-01-09T15:19:53.357Z"
page_height: 21624
---

# Group View

The VAPIX® Group View API provides the information that makes it possible to configure the channel layout in a Group View configuration. A group view consists of multiple channels, most commonly in a quad (four channels) or dual (two channels) setup. The API is used when you want to configure or rearrange the layout of or the channels found in the group view.

## Overview

The API implements `/axis-cgi/groupview.cgi` as its communications interface and supports the following methods:

| Method | Description |
| --- | --- |
| [getLayout](#getlayout) | Request the layout for the channels in the group view. |
| [getAvailableLayout](#getavailablelayout) | Request possible layouts available to the group view. |
| [setLayout](#setlayout) | Set the layout for the channels in the group view. |
| [getSupportedVersions](#getsupportedversions) | List supported API versions. |

This diagram exemplifies how the group view layout can be changed. In this case, the API has been used to mirror the layout, so that the first channel starts in the top right corner instead of the top left.

![Changing the group view layout](data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz48c3ZnIGlkPSJMYXllcl8yIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzODAiIGhlaWdodD0iMTYwIiB2aWV3Qm94PSIwIDAgMzgwIDE2MCI+PGxpbmUgeDE9IjE3NC45MDQ1IiB5MT0iODAiIHgyPSIyMDMuMDk1MyIgeTI9IjgwIiBzdHlsZT0iZmlsbDpub25lOyBzdHJva2U6IzMzMzsgc3Ryb2tlLWxpbmVjYXA6cm91bmQ7IHN0cm9rZS1taXRlcmxpbWl0OjEwOyIvPjxwb2x5Z29uIHBvaW50cz0iMjAwLjcwNzUgODMuNDE3MyAyMDAuNzA3NSA4MCAyMDAuNzA3NSA3Ni41ODI3IDIwOS4wNjUgODAgMjAwLjcwNzUgODMuNDE3MyIgc3R5bGU9ImZpbGw6IzMzMzsgc3Ryb2tlLXdpZHRoOjBweDsiLz48cmVjdCB4PSIxMi4zNDIyIiB5PSIxMi44NjUxIiB3aWR0aD0iMTM0LjI2OTkiIGhlaWdodD0iMTM0LjI2OTkiIHN0eWxlPSJmaWxsOm5vbmU7IHN0cm9rZTojMzMzOyBzdHJva2UtbGluZWNhcDpyb3VuZDsgc3Ryb2tlLWxpbmVqb2luOnJvdW5kOyIvPjxsaW5lIHgxPSI3OS40NzcxIiB5MT0iMTIuODY1MSIgeDI9Ijc5LjQ3NzEiIHkyPSIxNDcuMTM0OSIgc3R5bGU9ImZpbGw6bm9uZTsgc3Ryb2tlOiMzMzM7IHN0cm9rZS1saW5lY2FwOnJvdW5kOyBzdHJva2UtbGluZWpvaW46cm91bmQ7Ii8+PGxpbmUgeDE9IjE0Ni42MTIiIHkxPSI4MCIgeDI9IjEyLjM0MjIiIHkyPSI4MCIgc3R5bGU9ImZpbGw6bm9uZTsgc3Ryb2tlOiMzMzM7IHN0cm9rZS1saW5lY2FwOnJvdW5kOyBzdHJva2UtbGluZWpvaW46cm91bmQ7Ii8+PHJlY3QgeD0iMjMzLjM4OCIgeT0iMTIuODY1MSIgd2lkdGg9IjEzNC4yNjk5IiBoZWlnaHQ9IjEzNC4yNjk5IiBzdHlsZT0iZmlsbDpub25lOyBzdHJva2U6IzMzMzsgc3Ryb2tlLWxpbmVjYXA6cm91bmQ7IHN0cm9rZS1saW5lam9pbjpyb3VuZDsiLz48bGluZSB4MT0iMzAwLjUyMjkiIHkxPSIxMi44NjUxIiB4Mj0iMzAwLjUyMjkiIHkyPSIxNDcuMTM0OSIgc3R5bGU9ImZpbGw6bm9uZTsgc3Ryb2tlOiMzMzM7IHN0cm9rZS1saW5lY2FwOnJvdW5kOyBzdHJva2UtbGluZWpvaW46cm91bmQ7Ii8+PGxpbmUgeDE9IjM2Ny42NTc4IiB5MT0iODAiIHgyPSIyMzMuMzg4IiB5Mj0iODAiIHN0eWxlPSJmaWxsOm5vbmU7IHN0cm9rZTojMzMzOyBzdHJva2UtbGluZWNhcDpyb3VuZDsgc3Ryb2tlLWxpbmVqb2luOnJvdW5kOyIvPjxwYXRoIGQ9Im0zMzQuOTc1Niw1My42MDE2aC0xLjEwNzR2LTcuMTIzYzAtLjU5MTguMDE4MS0xLjE1MjMuMDU0Ny0xLjY4MTYtLjA5NTcuMDk1Ny0uMjAyNi4xOTYzLS4zMjEzLjMwMDgtLjExODcuMTA1NS0uNjYwNi41NDk4LTEuNjI3LDEuMzMzbC0uNjAxNi0uNzc5MywyLjY0NTUtMi4wNDM5aC45NTd2OS45OTQxWiIgc3R5bGU9ImZpbGw6IzMzMzsgc3Ryb2tlLXdpZHRoOjBweDsiLz48cGF0aCBkPSJtMjcwLjIwNTYsNTMuNjAxNmgtNi41Njkzdi0uOTc3NWwyLjYzMTgtMi42NDU1Yy44MDIyLS44MTA1LDEuMzMwNi0xLjM4OTYsMS41ODU5LTEuNzM2My4yNTU0LS4zNDU3LjQ0NjgtLjY4MzYuNTc0Mi0xLjAxMTdzLjE5MTQtLjY4MDcuMTkxNC0xLjA1OTZjMC0uNTMzMi0uMTYxNi0uOTU2MS0uNDg1NC0xLjI2NzYtLjMyMzctLjMxMjUtLjc3MjUtLjQ2ODgtMS4zNDY3LS40Njg4LS40MTQ2LDAtLjgwNzYuMDY4NC0xLjE3OTIuMjA1MXMtLjc4NTIuMzg1Ny0xLjI0MDcuNzQ1MWwtLjYwMTYtLjc3MjVjLjkyMDQtLjc2NTYsMS45MjMzLTEuMTQ4NCwzLjAwNzgtMS4xNDg0LjkzOSwwLDEuNjc0OC4yNDAyLDIuMjA4LjcyMTcuNTMzMi40ODA1Ljc5OTgsMS4xMjcuNzk5OCwxLjkzNzUsMCwuNjMzOC0uMTc3NywxLjI2MDctLjUzMzIsMS44Nzk5LS4zNTU1LjYyMDEtMS4wMjEsMS40MDQzLTEuOTk2MSwyLjM1MTZsLTIuMTg3NSwyLjEzOTZ2LjA1NDdoNS4xNDA2djEuMDUyN1oiIHN0eWxlPSJmaWxsOiMzMzM7IHN0cm9rZS13aWR0aDowcHg7Ii8+PHBhdGggZD0ibTMzNi45NjQ4LDExMy4wOTQ3YzAsLjYzNzctLjE3ODcsMS4xNjAyLS41MzY2LDEuNTY1NHMtLjg2NDcuNjc2OC0xLjUyMS44MTM1di4wNTQ3Yy44MDIyLjEwMDYsMS4zOTcuMzU1NSwxLjc4NDIuNzY1NnMuNTgxMS45NDgyLjU4MTEsMS42MTMzYzAsLjk1MjEtLjMzMDYsMS42ODU1LS45OTEyLDIuMTk3My0uNjYwNi41MTM3LTEuNTk5Ni43Njk1LTIuODE2NC43Njk1LS41Mjg4LDAtMS4wMTI3LS4wNC0xLjQ1MjYtLjExOTEtLjQzOTktLjA4MDEtLjg2NzItLjIyMDctMS4yODE3LS40MjA5di0xLjA4MDFjLjQzMzEuMjEzOS44OTQ1LjM3NywxLjM4NDMuNDg5My40ODk3LjExMTMuOTUzNi4xNjcsMS4zOTExLjE2NywxLjcyNzEsMCwyLjU5MDgtLjY3NjgsMi41OTA4LTIuMDMwMywwLTEuMjExOS0uOTUyNi0xLjgxODQtMi44NTc0LTEuODE4NGgtLjk4NDR2LS45Nzc1aC45OThjLjc3OTMsMCwxLjM5Ny0uMTcxOSwxLjg1MjUtLjUxNjYuNDU1Ni0uMzQzOC42ODM2LS44MjEzLjY4MzYtMS40MzE2LDAtLjQ4NzMtLjE2NzUtLjg3MDEtLjUwMjQtMS4xNDg0cy0uNzg5Ni0uNDE3LTEuMzYzOC0uNDE3Yy0uNDM3NSwwLS44NTAxLjA1OTYtMS4yMzczLjE3NzdzLS44Mjk2LjMzNjktMS4zMjYyLjY1NjJsLS41NzQyLS43NjU2Yy40MTAyLS4zMjMyLjg4MjgtLjU3NzEsMS40MTg1LS43NjI3LjUzNTYtLjE4MzYsMS4wOTk2LS4yNzY0LDEuNjkxOS0uMjc2NC45NzA3LDAsMS43MjUxLjIyMTcsMi4yNjI3LjY2Ny41Mzc2LjQ0MzQuODA2NiwxLjA1MzcuODA2NiwxLjgyODFaIiBzdHlsZT0iZmlsbDojMzMzOyBzdHJva2Utd2lkdGg6MHB4OyIvPjxwYXRoIGQ9Im0yNzAuNjc3MiwxMTguNDQwNGgtMS40ODM0djIuMjk2OWgtMS4wODY5di0yLjI5NjloLTQuODYwNHYtLjk5MTJsNC43NDQxLTYuNzYwN2gxLjIwMzF2Ni43MTk3aDEuNDgzNHYxLjAzMjJabS0yLjU3MDMtMS4wMzIydi0zLjMyMjNjMC0uNjUxNC4wMjI5LTEuMzg3Ny4wNjg0LTIuMjA4aC0uMDU0N2MtLjIxODguNDM3NS0uNDIzOC43OTk4LS42MTUyLDEuMDg2OWwtMy4xMjQsNC40NDM0aDMuNzI1NloiIHN0eWxlPSJmaWxsOiMzMzM7IHN0cm9rZS13aWR0aDowcHg7Ii8+PHBhdGggZD0ibTQ2Ljc5NDQsNTMuNjAxNmgtMS4xMDc0di03LjEyM2MwLS41OTE4LjAxODEtMS4xNTIzLjA1NDctMS42ODE2LS4wOTU3LjA5NTctLjIwMjYuMTk2My0uMzIxMy4zMDA4LS4xMTg3LjEwNTUtLjY2MDYuNTQ5OC0xLjYyNywxLjMzM2wtLjYwMTYtLjc3OTMsMi42NDU1LTIuMDQzOWguOTU3djkuOTk0MVoiIHN0eWxlPSJmaWxsOiMzMzM7IHN0cm9rZS13aWR0aDowcHg7Ii8+PHBhdGggZD0ibTExNi4yOTQ0LDUzLjYwMTZoLTYuNTY5M3YtLjk3NzVsMi42MzE4LTIuNjQ1NWMuODAyMi0uODEwNSwxLjMzMDYtMS4zODk2LDEuNTg1OS0xLjczNjMuMjU1NC0uMzQ1Ny40NDY4LS42ODM2LjU3NDItMS4wMTE3cy4xOTE0LS42ODA3LjE5MTQtMS4wNTk2YzAtLjUzMzItLjE2MTYtLjk1NjEtLjQ4NTQtMS4yNjc2LS4zMjM3LS4zMTI1LS43NzI1LS40Njg4LTEuMzQ2Ny0uNDY4OC0uNDE0NiwwLS44MDc2LjA2ODQtMS4xNzkyLjIwNTFzLS43ODUyLjM4NTctMS4yNDA3Ljc0NTFsLS42MDE2LS43NzI1Yy45MjA0LS43NjU2LDEuOTIzMy0xLjE0ODQsMy4wMDc4LTEuMTQ4NC45MzksMCwxLjY3NDguMjQwMiwyLjIwOC43MjE3LjUzMzIuNDgwNS43OTk4LDEuMTI3Ljc5OTgsMS45Mzc1LDAsLjYzMzgtLjE3NzcsMS4yNjA3LS41MzMyLDEuODc5OS0uMzU1NS42MjAxLTEuMDIxLDEuNDA0My0xLjk5NjEsMi4zNTE2bC0yLjE4NzUsMi4xMzk2di4wNTQ3aDUuMTQwNnYxLjA1MjdaIiBzdHlsZT0iZmlsbDojMzMzOyBzdHJva2Utd2lkdGg6MHB4OyIvPjxwYXRoIGQ9Im00OC43ODM3LDExMy4wOTQ3YzAsLjYzNzctLjE3ODcsMS4xNjAyLS41MzY2LDEuNTY1NHMtLjg2NDcuNjc2OC0xLjUyMS44MTM1di4wNTQ3Yy44MDIyLjEwMDYsMS4zOTcuMzU1NSwxLjc4NDIuNzY1NnMuNTgxMS45NDgyLjU4MTEsMS42MTMzYzAsLjk1MjEtLjMzMDYsMS42ODU1LS45OTEyLDIuMTk3My0uNjYwNi41MTM3LTEuNTk5Ni43Njk1LTIuODE2NC43Njk1LS41Mjg4LDAtMS4wMTI3LS4wNC0xLjQ1MjYtLjExOTEtLjQzOTktLjA4MDEtLjg2NzItLjIyMDctMS4yODE3LS40MjA5di0xLjA4MDFjLjQzMzEuMjEzOS44OTQ1LjM3NywxLjM4NDMuNDg5My40ODk3LjExMTMuOTUzNi4xNjcsMS4zOTExLjE2NywxLjcyNzEsMCwyLjU5MDgtLjY3NjgsMi41OTA4LTIuMDMwMywwLTEuMjExOS0uOTUyNi0xLjgxODQtMi44NTc0LTEuODE4NGgtLjk4NDR2LS45Nzc1aC45OThjLjc3OTMsMCwxLjM5Ny0uMTcxOSwxLjg1MjUtLjUxNjYuNDU1Ni0uMzQzOC42ODM2LS44MjEzLjY4MzYtMS40MzE2LDAtLjQ4NzMtLjE2NzUtLjg3MDEtLjUwMjQtMS4xNDg0cy0uNzg5Ni0uNDE3LTEuMzYzOC0uNDE3Yy0uNDM3NSwwLS44NTAxLjA1OTYtMS4yMzczLjE3NzdzLS44Mjk2LjMzNjktMS4zMjYyLjY1NjJsLS41NzQyLS43NjU2Yy40MTAyLS4zMjMyLjg4MjgtLjU3NzEsMS40MTg1LS43NjI3LjUzNTYtLjE4MzYsMS4wOTk2LS4yNzY0LDEuNjkxOS0uMjc2NC45NzA3LDAsMS43MjUxLjIyMTcsMi4yNjI3LjY2Ny41Mzc2LjQ0MzQuODA2NiwxLjA1MzcuODA2NiwxLjgyODFaIiBzdHlsZT0iZmlsbDojMzMzOyBzdHJva2Utd2lkdGg6MHB4OyIvPjxwYXRoIGQ9Im0xMTYuNzY2MSwxMTguNDQwNGgtMS40ODM0djIuMjk2OWgtMS4wODY5di0yLjI5NjloLTQuODYwNHYtLjk5MTJsNC43NDQxLTYuNzYwN2gxLjIwMzF2Ni43MTk3aDEuNDgzNHYxLjAzMjJabS0yLjU3MDMtMS4wMzIydi0zLjMyMjNjMC0uNjUxNC4wMjI5LTEuMzg3Ny4wNjg0LTIuMjA4aC0uMDU0N2MtLjIxODguNDM3NS0uNDIzOC43OTk4LS42MTUyLDEuMDg2OWwtMy4xMjQsNC40NDM0aDMuNzI1NloiIHN0eWxlPSJmaWxsOiMzMzM7IHN0cm9rZS13aWR0aDowcHg7Ii8+PC9zdmc+)

### Identification

-   **API Discovery**: `id=groupview`

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## Common examples
### Request channel layout

This example will show you how to check the current channel layout in the group view.

1.  Check the channel layout of a specific group view. The id-number parameter is used to identify the channel.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getLayout",    "params": {        "id": 5    }}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getLayout",    "params": {        "id": 5    }}
```

2.  Parse the JSON response. The API will return a quad view that reads from top left to bottom right.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getLayout",    "data": {        "id": 5,        "layout": \[            \[{ "id": 1 }, { "id": 2 }\],            \[{ "id": 3 }, { "id": 4 }\]        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getLayout",    "error": {        "code": 2100,        "message": "API version not supported"    }}
```

See [getLayout](#getlayout) for additional details.

### Request potential channel layouts

This example will show you how to request the different ways to configure the channel layout for the group view. Different devices will have different available options for the group view.

1.  Check the channel layouts for a specific group view with an id-number.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getAvailableLayout",    "params": {        "id": 5    }}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getAvailableLayout",    "params": {        "id": 5    }}
```

2.  Parse the JSON response. The API will return possible layouts for the channels in the group view.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getAvailableLayout",    "data": \[        {            "id": 5,            "layout": \[                \[                    \[{ "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }\],                    \[{ "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }\]                \],                \[\[{ "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }\]\],                \[\[{ "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }\]\]            \]        }    \]}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getAvailableLayout",    "error": {        "code": 2100,        "message": "API version not supported"    }}
```

See [getAvailableLayout](#getavailablelayout) for additional details.

### Request all available channel layouts

This example will show you how to check every possible channel layout from the group view.

1.  Request all available channel layouts from the group view.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "getAvailableLayout",    "params": {}}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "getAvailableLayout",    "params": {}}
```

2.  Parse the JSON response. The API will return the possible layouts for all group view channels.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getAvailableLayout",    "data": \[        {            "id": 5,            "layout": \[                \[                    \[{ "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }\],                    \[{ "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }\]                \],                \[\[{ "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }\]\],                \[\[{ "id": \[1, 2, 3, 4\] }, { "id": \[1, 2, 3, 4\] }\]\]            \]        },        {            "id": 6,            "layout": \[\[\[{ "id": \[1, 2\] }, { "id": \[3, 4\] }\]\]\]        }    \]}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getAvailableLayout",    "error": {        "code": 2100,        "message": "API version not supported"    }}
```

See [getAvailableLayout](#getavailablelayout) for additional details.

### Set channel layouts for the group view

This example will show you how to rearrange the channel layout for the group view.

1.  Rearrange the channel layout for the group view.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{    "apiVersion": "1.0",    "context": "123",    "method": "setLayout",    "params": {        "id": 5,        "layout": \[            \[{ "id": 1 }, { "id": 3 }\],            \[{ "id": 4 }, { "id": 2 }\]        \]    }}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{    "apiVersion": "1.0",    "context": "123",    "method": "setLayout",    "params": {        "id": 5,        "layout": \[            \[{ "id": 1 }, { "id": 3 }\],            \[{ "id": 4 }, { "id": 2 }\]        \]    }}
```

2.  Parse the JSON response. The API will return the new group view layout.

Successful response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "setLayout",    "data": {        "id": 5,        "layout": \[            \[{ "id": 1 }, { "id": 3 }\],            \[{ "id": 4 }, { "id": 2 }\]        \]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "setLayout",    "error": {        "code": 1100,        "message": "Internal error"    }}
```

See [setLayout](#setlayout) for additional details.

### List supported API versions

This example will show you how to check the API versions supported by your device.

1.  Request a list of supported API versions.

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{    "context": "123",    "method": "getSupportedVersions"}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{    "context": "123",    "method": "getSupportedVersions"}
```

2.  Parse the JSON response.

Successfully response example

```bash
{    "context": "123",    "method": "getSupportedVersions",    "data": {        "apiVersions": \["1.4", "2.5"\]    }}
```

Error response example

```bash
{    "apiVersion": "1.0",    "context": "123",    "method": "getSupportedVersions",    "error": {        "code": 2100,        "message": "API version not supported"    }}
```

See [getSupportedVersions](#getsupportedversions) for additional details.

## API specifications
### getLayout

This should be used when you want to check the channel layout of a group view.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getLayout",  "params": {    "id": <int>  }}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getLayout",  "params": {    "id": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getLayout"` | The method that should be used. |
| `id=<integer>` | The ID of the group view that the user wants to check. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getLayout",  "data": {    "id": <int>,    "layout": \[      \[{"id": <int>}, {"id": <int>}\],      \[{"id": <int>}, {"id": <int>}\]    \]  }}
```

| Parameter | Sub-parameter | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version returned from the request. |
| `context=<string>` _Optional_ |  | The context set by the user in the request. |
| `method="getLayout` |  | The requested method. |
| `id=<integer>` |  | The ID of the group view returned by the request. |
| `layout=<list of rows>` |  | The current channel layout of the group view. Contains listings of layouts and columns. The first list is for the first row, the second list is for the second row and so on. |
|  | `<list of channels>` | List the rows in the group view. The first element contains information about the first channel, starting from the left, the second element contains the second channel and so on. Each channel element contains the information on how a specific channel in a specific location in the group view has been configured. |
|  | `id=<integer>` | Specifies the channel and its location in the group view. |

**Return value - Failure**

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getLayout",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getAvailableLayout

This method should be used when you want to check a list of possible layouts that are available for the group view.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAvailableLayout",  "params": {    "id": <int>  }}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAvailableLayout",  "params": {    "id": <int>  }}
```

| Parameter | Description |
| --- | --- |
| `apiVersion` | The API version that should be used. |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getAvailableLayout"` | The method that should be used. |
| `id=<integer>` _Optional_ | The ID for the group view that the user wants to check. Omitting this parameter will make the response contain possible layouts for every ID supporting group view. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "getAvailableLayout",  "data": \[    {      "id": <int>,      "layout": \[        \[          \[{"id": \[<int>, <int>, <int>, <int>\]}, {"id": \[<int>, <int>, <int>, <int>\]}\],          \[{"id": \[<int>, <int>, <int>, <int>\]}, {"id": \[<int>, <int>, <int>, <int>\]}\]        \],        \[          \[{"id": \[<int>, <int>, <int>, <int>\]}, {"id": \[<int>, <int>, <int>, <int>\]}\]        \]      \]    },    {      "id": <int>,      "layout": \[        \[          \[{"id": \[<int>, <int>\]}, {"id": \[<int>, <int>\]}\]        \]      \]    }  \]}
```

| Parameter | Sub-parameter | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version returned from the request. |
| `context=<string>` _Optional_ |  | The context set by the user in the request. |
| `method="getAvailableLayout` |  | The requested method. |
| `data=<list of data>` |  | Object list with ID and attributes. The list will contain one element if the ID was set in the request, as long as it supports group view. The request will fail if the ID does not support group view |
|  | `id=<integer>` | The ID of the group view layout returned by the request. |
|  | `layout=<list of layouts>` | List the layouts that can be set in the group view. Each layout contains different rows of channels that represents layouts and columns in the group view. The first list is for the initial row, the second for the next row and so on. The first element contains information about the first channel, starting from the left, the second element contains the next channel and so on. Each channel element also contains the information how a channel in a specific location in the group view can be configured. The channel element also has information about the channel ranges that can be set in a specific position. |
|  | `id=<list>` | Provides a list of channel IDs that are possible to set in a specific position. |

**Return value - Failure**

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getAvailableLayout",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

See [General error codes](#general-error-codes) for a complete list of potential errors.

### setLayout

This method should be used when you want to configure the channel layout in a group view.

**Request**

-   **Security level**: Administrator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{  "apiVersion": "1.0",  "context": "<string>",  "method": "setLayout",  "params": {    "id": <int>,    "layout": \[      \[{"id": <int>}, {"id": <int>}\],      \[{"id": <int>}, {"id": <int>}\]    \]  }}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{  "apiVersion": "1.0",  "context": "<string>",  "method": "setLayout",  "params": {    "id": <int>,    "layout": \[      \[{"id": <int>}, {"id": <int>}\],      \[{"id": <int>}, {"id": <int>}\]    \]  }}
```

| Parameter | Sub-parameters | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>` _Optional_ |  | The user sets this value and the application echoes it back in the response. |
| `method="setLayout"` |  | The method that should be used. |
| `id=<integer>` |  | The group view ID that the user wants to set the layout for. |
| `layout=<list of rows>` |  | Specifies the new channel layout that will be set in the group view. Contains both the layouts and columns in the group view. The first list is for the initial row, the seconds is for the next row and so on. |
|  | `<list of channels>` | Contains a list for a specific row in the group view. The first element contains information about the first channel, starting from the left, the second element contains the next channel and so on. Each channel element contains the information how a channel in a specific location in the group view can be configured. |
|  | `id=<integer>` | Specifies a channel location in the group view. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "apiVersion": "1.0",  "context": "<string>",  "method": "setLayout",  "data": {    "id": <int>,    "layout": \[      \[{"id": <int>}, {"id": <int>}\],      \[{"id": <int>}, {"id": <int>}\]    \]  }}
```

| Parameter | Sub-parameters | Description |
| --- | --- | --- |
| `apiVersion` |  | The API version that should be used. |
| `context=<string>` _Optional_ |  | The context set by the user in the request. |
| `method="setLayout"` |  | The requested method. |
| `id=<integer>` |  | The group view ID of the layout set by the request. |
| `layout=<list of rows>` |  | The new channel layout set in the group view. Contains both the layouts and columns in the group view. The first list is for the initial row, the seconds is for the next row and so forth. |
|  | `<list of channels>` | Contains a list for a specific row in the group view. The first element contains information about the first channel, starting from the left, the second element contains the next channel and so forth. Each channel element contains the information how a channel in a specific location in the group view can be configured. |
|  | `id=<integer>` | Specifies a channel location in the group view. |

**Return value - Failure**

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "setLayout",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

See [General error codes](#general-error-codes) for a complete list of potential errors.

### getSupportedVersions

This method should be used when you want to request a list of supported API versions.

**Request**

-   **Security level**: Operator

-   curl
-   HTTP

```bash
curl --request POST \\  --anyauth \\  --user "<username>:<password>" \\  --header "Content-Type: application/json" \\  "http://<servername>/axis-cgi/groupview.cgi" \\  --data '{  "context": "<string>",  "method": "setLayout",}'
```

```bash
POST /axis-cgi/groupview.cgiHost: <servername>Content-Type: application/json{  "context": "<string>",  "method": "setLayout",}
```

| Parameter | Description |
| --- | --- |
| `context=<string>` _Optional_ | The user sets this value and the application echoes it back in the response. |
| `method="getSupportedVersions"` | The method that should be used. |

**Return value - Success**

-   **HTTP Code**: `200 OK`
-   **Content-Type**: `application/json`

Response body syntax

```bash
{  "context": "<string>",  "method": "getSupportedVersions",  "data": {    "apiVersions": \["<Major1>.<Minor1>", "<Major2>.<Minor2>"\]  }}
```

| Parameter | Sub-parameters | Description |
| --- | --- | --- |
| `context=<string>` _Optional_ |  | The context set by the user in the request. |
| `method="getSupportedVersions"` |  | The requested method. |
| `data.apiVersions[]=<list of versions>` |  | List of all supported major API versions along with their highest supported minor version. |
|  | `<list of versions>` | List of "<Major>.<Minor>" versions e.g. \["1.4", "2.5"\] |

**Return value - Failure**

Response body syntax

```bash
{  "apiVersion": "<major>.<minor>",  "context": "<string>",  "method": "getSupportedVersions",  "error": {    "code": <integer error code>,    "message": <string>  }}
```

See [General error codes](#general-error-codes) for a complete list of potential errors.

| JSON code | HTTP code | Description |
| --- | --- | --- |
| `1200` | `500` | List does not match an allowed layout. |
| `2200` | `400` | Invalid value for ID in parameter layout. |

### General error codes

The following table consist of errors that may occur for any method. Errors specific to a method are listed under their separate API description. The error codes exist in the following ranges.

-   1100–1199
    
    Generic error codes common for many APIs and reserved for server errors such as "Maximum number of configurations reached". The actual cause can be seen in the server log and can sometimes be solved by restarting the device.
    
-   1200–1999
    
    API-specific server errors that may collide between different APIs.
    
-   2100–2199
    
    Generic error codes common to many APIs and reserved for client errors such as "Invalid parameter". These errors should be possible to solve by changing the input data to the API.
    
-   2200–2999
    
    API-specific client errors that may collide between different APIs.
    

info

The 4–digit error codes are returned in the JSON body when the service is executed, which means that the client must be prepared to handle transport-level errors codes with non-JSON responses. Specifically, HTTP error 401/403 will be emitted if either authentication or authorization fails.

| JSON code | HTTP code | Description |
| --- | --- | --- |
| `1100` | `500` | Internal error.([1](#user-content-fn-1)) |
| `2100` | `400` | API version not supported. |
| `2101` | `400` | Invalid JSON. |
| `2102` | `400` | Method not supported. |
| `2103` | `400` | Required parameter missing. |
| `2104` | `400` | Invalid parameter value specified. |
| `2105` | `403` | Authorization failed. |
| `2106` | `401` | Authentication failed. |
| `2107` | `4XX, 5XX` | Transport-level error. |

## Footnotes

1.  Out-of-memory errors will also be reported as 1100 Internal error. [↩](#user-content-fnref-1)