"""
API executors — turn a catalog operation into a real network call.

One executor per API family. Each implements
:class:`admz.executor.base.BaseExecutor` and is responsible for building
the HTTP request, handling authentication, and parsing the response.

Current executors:

- :class:`admz.executor.vapix.VapixExecutor` — VAPIX (legacy-cgi,
  json-rpc, and config-rest generations all supported).
"""
