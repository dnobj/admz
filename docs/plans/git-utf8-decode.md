# Plan: fix config-history mojibake — git output decoded as cp1252 on Windows

Status: **✅ implemented** (GH #112; fix + regression test shipped via `fix/git-utf8-decode`).

## Symptom

The config history (device-detail timeline, `/api/config/history`, demos changelog)
renders non-ASCII characters from commit messages as mojibake. Observed live on the
P3288's history:

```
Accept baseline: 4 devices â€” Part of new BIOE demo
```

The operator typed an em dash (`—`) in the accept-baseline note; the UI shows `â€”`.

## Root cause

The bytes **stored in git are correct UTF-8** — the same commits render perfectly in a
UTF-8 terminal (`git log` in git-bash shows `… 4 devices — Part of new BIOE demo`).
The corruption happens on **read**:

- `GitRepo._run_git` (`admz/snapshot/git_repo.py`, the `popen_kwargs` block) sets
  `text=True` **without** `encoding=`. On Windows, `subprocess.Popen(text=True)` decodes
  the child's stdout with `locale.getpreferredencoding(False)` — cp1252 on this
  deployment — while git emits UTF-8. The em dash `E2 80 94` decodes to `â€”`.
- Every git read funnels through this single helper (`log`, diffs, `get_file`,
  status), so any non-ASCII commit message, note, or tracked file content mis-renders
  on every surface that shows history.
- Writes are unaffected: commit messages pass as argv elements through the Windows
  wide-char process API, which is why the stored bytes are clean. **No git history
  rewrite is needed.**

One more same-class call site: `admz/components.py` (`git remote get-url origin`,
`text=True`, no encoding). Harmless in practice (remote URLs are ASCII) but should be
fixed for consistency.

**Deliberately not touched:** `admz/discovery/arp_scanner.py` also uses `text=True` —
but Windows `arp -a` emits the OEM codepage (not UTF-8), and only ASCII IPs/MACs are
parsed from it. Forcing UTF-8 there would be wrong.

## Changes

1. `admz/snapshot/git_repo.py` — add `encoding="utf-8", errors="replace"` to
   `_run_git`'s `popen_kwargs`. (`replace`, not strict: a stray invalid byte in some
   diff/file read must degrade to a replacement character, never crash a history
   endpoint.)
2. `admz/components.py` — same two kwargs on the `git remote get-url` `subprocess.run`.
3. Regression test in `tests/test_config_history.py` (reuse the existing
   `GitRepo(tmp_path)` + `_init_git` helpers): commit with a non-ASCII message
   (`"Accept baseline: 4 devices — Part of new BIOE demo"`, plus a `ü` and a CJK
   character) → `repo.log()` must return the message byte-identical, with no `â€`
   sequence. On Windows (locale cp1252) this test fails before the fix and passes
   after — run it standalone first to confirm red-before/green-after.

## Verification

- New unit test red-before/green-after; full suite green.
- Live after deploy: `GET /api/config/history?device_id=<P3288>` — the BIOE commit
  subject must read `… 4 devices — Part of new BIOE demo` with a real em dash;
  spot-check the device-detail timeline. Because the stored bytes were always correct,
  the fix repairs the display of **all existing** history retroactively.
