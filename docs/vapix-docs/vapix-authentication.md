---
title: Authentication
url: "https://developer.axis.com/vapix/authentication/"
category: vapix
sha256: 095d8a7dd45ecd66249cf745aec8c35b1a86990d1030ca396b62535b2b94fdac
scraped_at: "2026-01-09T14:54:15.449Z"
---

# Authentication

VAPIX® supports several authentication methods to secure access to devices and their resources. The method you should use depends on your connection type (protocol).

Authentication differs from authorization. Authentication verifies who you are, while authorization determines what you can access. You must authenticate first before the system can check your permissions. In VAPIX, authentication uses [user accounts](/vapix/network-video/system-settings/#add-modify-and-delete-user-accounts) on the device. Authorization depends on the privileges (Administrator, Operator, Viewer) assigned to those user accounts.

## Authentication methods

Authentication methods may vary by device, model, and AXIS OS version. When you make your first request, send it without authentication information. If the device requires authentication, it responds with a `401 Unauthorized` HTTP status code and a `WWW-Authenticate` header that details the supported authentication method. You can then retry the request with the appropriate authentication.

### Basic access authentication

[Basic access authentication](https://wikipedia.org/wiki/Basic_access_authentication) is a simple authentication scheme that encodes credentials instead of encrypting them. The encoding isn't cryptographically secure, and anyone intercepting the request can easily decode the credentials to get the username and password. This makes basic authentication unsuitable for HTTP connections, however you can use this authentication method safely with HTTPS, which encrypts the entire communication channel and protects your credentials from being intercepted.

### Digest access authentication

[Digest access authentication](https://wikipedia.org/wiki/Digest_access_authentication) is more secure than basic access authentication for unencrypted connections. It uses a challenge-response mechanism to ensure that your credentials aren't sent in plaintext over the network. Instead of sending the username and password directly, your client sends a hashed version of the credentials along with a unique nonce value from the device.

Axis added support for digest access authentication when HTTPS wasn't as common as it is today. It was a way to enhance authentication security without requiring HTTPS, at a time when tooling, support, and hardware performance were limited.

### Choose the right authentication method

Use the following authentication methods for different connection types when communicating with Axis devices:

| Connection type (protocol) | Recommended authentication method |
| --- | --- |
| HTTP | Digest access authentication |
| HTTPS | Basic access authentication |
| RTSP | Digest access authentication |

See [`Network.HTTP.AuthenticationPolicy`](/vapix/network-video/network-settings/#networkhttpauthenticationpolicy) for more information about configuring the authentication policy on Axis devices.

## Code examples

Replace `<username>`, `<password>`, and `<servername>` in the following code examples with your own values. For details about the commands, see the [command-line interface reference](/references/command-line-interface/).

### curl

[curl](https://curl.se/) is a popular command-line tool for making HTTP requests that's supported on most operating systems. The `--anyauth` option tells curl to automatically select the most secure authentication method supported by the device.

Get basic device information

```bash
curl --request POST \\    --anyauth \\    --user "<username>:<password>" \\    "http://<servername>/axis-cgi/basicdeviceinfo.cgi" \\    --data '{ "apiVersion": "1.0", "method": "getAllProperties" }'
```

The following arguments might be useful when using curl:

-   `-i`, `--include`: Include HTTP response headers in the output along with the response body. This helps you debug API calls by showing status codes, content types, and other header information returned by the device.
-   `--noproxy`: Bypass the proxy for the specified host(s). Use `--noproxy "*"` to disable the proxy for all hosts. This is useful when accessing local devices that shouldn't go through a proxy server.
-   `--libcurl`: Generate C code that uses libcurl to perform the same request. This is helpful if you're developing a C application and want to see how to implement the request using libcurl.

## Device hardening

Device hardening is the process of securing a system by reducing its attack surface and minimizing potential vulnerabilities. AXIS OS provides built-in security features and configuration options that help you harden your Axis devices. For detailed instructions and specific hardening recommendations, see the [AXIS OS Hardening Guide](https://help.axis.com/en-us/axis-os-hardening-guide).