---
title: Entry service API
url: "https://developer.axis.com/vapix/network-video/entry-service-api/"
category: vapix
subcategory: network-video
sha256: e5656d12b3fb61d9105bf95a2d008b2af0d7e6f27485b527b47d1ae593ef485c
scraped_at: "2026-01-09T15:19:38.625Z"
page_height: 3582
---

# Entry service API

VAPIX® Entry service API is a web services API used to query the Axis product for supported services, service capabilities and their versions.

Supported operations:

-   `GetServices` — Returns information about the services available in the Axis product. The response is untyped.
-   `GetServiceCapabilities` — Returns the capabilities supported by the entry service.

## Prerequisites
### Identification

VAPIX® Entry service API is supported if:

-   **Property**: `Properties.API.WebService.EntryService=yes`
-   **AXIS OS**: 5.60 and later

## Authentication

For detailed information on how to authenticate requests to this API, please refer to [Authentication](/vapix/authentication/).

## API specification

The API specification is available as an WSDL file at [http://www.axis.com/vapix/ws/EntryService.wsdl](http://www.axis.com/vapix/ws/EntryService.wsdl)

## Using entry service
### Get services

The `GetServices` request returns a list of supported services. For each service, the following information is listed: namespace, port type, XAddr, version and, if requested, the capabilities of the service.

`GetServices` can be requested with or without capabilities:

-   Use `GetServices(false)` to list services without their capabilities.
-   Use `GetServices(true)` to list services with their capabilities.

A service can have any number of capabilities or no capabilities at all. Capabilities are static and do not change during runtime.

### Get service capabilities

Use `GetServiceCapabilities` to list the capabilities provided by the entry service.

### Example

The example outlined in this section shows how to check if the Axis product supports a certain service.

Start by defining the IP address, user name and password for the Axis product and the namespace of the service to look for. In this example we will check if the product supports the light control service.

```bash
/\* Define the address, user name and password for the Axis product. <servername> is an IP address or host name.\*/string address="<servername>";string username="<user name>";string password="<password>";/\* Define the namespace of the service to look for.\*/string lightTargetNamespace = "http://www.axis.com/vapix/ws/light";
```

Next, use the function `CreateEntryServiceClient()` to create an entry service client. This function is defined in the sample code and is not part of the API.

```bash
/\* Create an entry service client.\*/EntryClient myEntryService = CreateEntryServiceClient(address, username, password);
```

Use the entry service client and `GetServices` to get a list of all services in the Axis product. We use the argument `false` to list the services without their capabilities.

```bash
/\* Get a list of all services.\*/Service\[\] serviceList = myEntryService.GetServices(false);
```

To check if the Axis product supports the light control service, search the list of services. If the service is found, retrieve the service address and create a service client. The client is created using the function `CreateLightServiceClient()` which is defined in the same way as `CreateEntryServiceClient()`.

info

The Xaddr returned by GetServices is an absolute URL. Modify as required to support NAT (Network Address Translation) and similar.

```bash
/\* Get a list of all services.\*/Service\[\] serviceList = myEntryService.GetServices(false);/\* Check if light control service is supported. \*/for (i = 0; i < serviceList.count; i++){  if (serviceList\[i\].Namespace == lightTargetNamespace)  {    /\* Get the service address.\*/    string lightXaddr = serviceList\[i\].Xaddr;    /\* Create a light client.\*/     LightClient myLightService=CreateLightServiceClient(lightXaddr, username, password);    break;  }}
```

info

The examples in this document are written using pseudocode.