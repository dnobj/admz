"""The checker flags a production tree that broad groups can write (#442).

Production's code and interpreter run as LocalSystem. Every folder created under
``C:\\`` inherits "Authenticated Users: Modify" from the drive root, so
``C:\\admz\\admz-prod`` did, and any account on the box — including the two
non-administrative sandbox accounts — could change what SYSTEM runs next.

These run on any platform. They parse SDDL strings; nothing reads a real
security descriptor (the checker itself does that on the live machine).
"""

from tools.environments import broad_writers, load_declaration, restricted_problems

#: Production's folder as it was on 2026-09-23, verbatim from Get-Acl.
BEFORE_DIR = (
    "O:S-1-5-21-1363114385-1323635173-1882264784-1001"
    "G:S-1-5-21-1363114385-1323635173-1882264784-1001"
    "D:AI(A;OICIID;FA;;;BA)(A;OICIID;FA;;;SY)(A;OICIID;0x1200a9;;;BU)"
    "(A;ID;0x1301bf;;;AU)(A;OICIIOID;SDGXGWGR;;;AU)"
)
#: Its interpreter, same day.
BEFORE_EXE = (
    "O:S-1-5-21-1363114385-1323635173-1882264784-1001"
    "G:S-1-5-21-1363114385-1323635173-1882264784-1001"
    "D:AI(A;ID;FA;;;BA)(A;ID;FA;;;SY)(A;ID;0x1200a9;;;BU)(A;ID;0x1301bf;;;AU)"
)
#: What the #442 fix leaves: SYSTEM and Administrators full, the operator
#: modify, Users read and execute, nothing inherited from C:\admz.
AFTER_DIR = (
    "O:S-1-5-21-1363114385-1323635173-1882264784-1001"
    "G:S-1-5-21-1363114385-1323635173-1882264784-1001"
    "D:PAI(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"
    "(A;OICI;0x1301bf;;;S-1-5-21-1363114385-1323635173-1882264784-1001)"
    "(A;OICI;0x1200a9;;;BU)"
)


class TestBroadWriters:
    def test_the_state_442_found(self):
        assert broad_writers(BEFORE_DIR) == ["Authenticated Users"]
        assert broad_writers(BEFORE_EXE) == ["Authenticated Users"]

    def test_the_state_the_fix_leaves(self):
        assert broad_writers(AFTER_DIR) == []

    def test_read_and_execute_is_not_write(self):
        assert broad_writers("D:(A;;0x1200a9;;;BU)(A;;FRFX;;;WD)") == []

    def test_an_inherit_only_entry_counts(self):
        """It is how everything below a folder becomes writable."""
        assert broad_writers("D:(A;OICIIO;GW;;;AU)") == ["Authenticated Users"]

    def test_every_write_shaped_right_counts(self):
        for rights in ("FA", "FW", "GA", "GW", "SD", "WD", "WO",
                       "0x2", "0x10000", "0x40000000"):
            assert broad_writers(f"D:(A;;{rights};;;S-1-1-0)") == ["Everyone"], rights

    def test_everyone_as_a_trustee_is_not_confused_with_the_write_dac_right(self):
        assert broad_writers("D:(A;;FR;;;WD)") == []
        assert broad_writers("D:(A;;WD;;;BA)") == []

    def test_a_deny_entry_grants_nothing(self):
        assert broad_writers("D:(D;;FA;;;AU)") == []

    def test_a_named_account_is_not_broad(self):
        """The operator's own write is expected; only groups meaning 'anyone
        who can sign in' are flagged."""
        assert broad_writers("D:(A;;FA;;;S-1-5-21-1-2-3-1001)") == []


class TestTheCheck:
    SPEC = {"restricted": True, "checkout": r"C:\admz\admz-prod",
            "venv": r"C:\admz\admz-prod\.venv"}

    def test_it_reports_the_tree_and_the_interpreter(self):
        read = {r"C:\admz\admz-prod": BEFORE_DIR,
                r"C:\admz\admz-prod\.venv\Scripts\python.exe": BEFORE_EXE}.get
        problems = restricted_problems("production", self.SPEC, read=read)
        assert len(problems) == 2
        assert all("Authenticated Users" in p and "#442" in p for p in problems)

    def test_the_fixed_tree_passes(self):
        problems = restricted_problems("production", self.SPEC,
                                       read=lambda path: AFTER_DIR)
        assert problems == []

    def test_an_unreadable_descriptor_fails_closed(self):
        problems = restricted_problems("production", self.SPEC, read=lambda path: None)
        assert len(problems) == 2 and all("could not be read" in p for p in problems)

    def test_an_environment_not_declared_restricted_is_not_checked(self):
        assert restricted_problems("dev", {"checkout": r"C:\x"},
                                   read=lambda path: BEFORE_DIR) == []


def test_production_is_declared_restricted():
    assert load_declaration()["production"].get("restricted") is True
