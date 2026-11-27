"""Installing and upgrading an instance (ADR-0075).

Until this package, an upgrade was a checklist a person typed: check the tree,
import every module, check out, restart, wait for health, and roll back by hand
if it did not come up. It was done four times and recorded only in issue
comments. ADR-0054 asked for a script and a host log in August; neither was
built (#426, #377).

The pieces here are small on purpose, and each is tested alone:

``walk``       import every module on the interpreter that will run them.
``backup``     a consistent copy of the database and its key, with a manifest.
``service``    stop, start and state of the Windows service, behind one shape.
``health``     wait for a healthy answer, and say which build gave it.
``deploylog``  one line per attempt, kept on the host.
``upgrade``    the order they run in, and the rollback.

Nothing here reads ``ADMZ_HOME`` from the environment. An upgrade is told which
data folder it is working on. The ambient variable belongs to whoever opened the
shell, and on the development machine that is the lab instance.
"""
