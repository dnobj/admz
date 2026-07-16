"""GitHub App integration for config-repo backup.

Lets the LocalSystem service push the config-repo to a GitHub mirror using
short-lived, auto-rotated, repo-scoped **installation tokens** — set up through a
streamlined "Connect GitHub" flow (GitHub App manifest → install), rather than a
long-lived PAT or an SSH deploy key. See ADR-0045 and [[project-admz-home-service]].
"""
