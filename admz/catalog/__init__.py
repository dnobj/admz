"""
Operations catalog — the source of truth for what ADMZ can do to a device.

The catalog is a tree of YAML files describing each API operation:

- ``cgi/<cgi-name>/_cgi.yaml``     — endpoint metadata (auth, generation)
- ``cgi/<cgi-name>/<op>.yaml``     — one file per operation
- ``cgi/param.cgi/groups/*.yaml``  — param.cgi parameter group docs
- ``index/by-task.yaml``           — task-to-operation routing
- ``index/by-risk.yaml``           — risk-level index

Two main classes:

- :class:`admz.catalog.loader.CatalogLoader` reads YAML from disk.
- :class:`admz.catalog.resolver.CatalogResolver` maps a (device, intent)
  pair to the relevant operations and parameter groups for the LLM.
"""
