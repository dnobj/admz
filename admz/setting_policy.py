"""Which fleet settings the chat model may write — the allow-set (ADR-0053).

**Deny by default.** A fleet setting is not writable by the LLM through the
generic MCP ``set_fleet_setting`` tool unless its key appears in
:data:`LLM_WRITABLE_SETTING_KEYS` below. This inverts ADR-0020's enumerated
deny-list, which made a new setting writable the moment it existed and
protected only if its author remembered — a default that failed four times in
the same direction (#152, #168, #195, #203).

The argument for inverting rather than patching a fifth time is not the four
failures; it is that three independent enumerations of what the deny-list
missed returned **8, 10 and 18 keys**, each missing keys the others found.
Every enumeration method inherits its author's blind spot: #212's regex
required ``[A-Z]`` at position 0 and so never saw ``_TOKEN_KEY``
(``acs_webhook_token``); a literal-grep missed keys read through a
module-local ``_settings()`` helper. You cannot enumerate your way out of
this. You can only change which way the default fails.

**Why this is a leaf.** It imports nothing from ``admz``, the same placement
and the same reason as :mod:`admz.confirm_policy`: ``admz.api.confirm_store``
already imports ``admz.fleet_settings`` at module scope, so vocabulary that
``fleet_settings`` needs has to live *below* it. It also keeps the stdio MCP
subprocess able to answer "may I write this?" without importing FastAPI.

See ADR-0053, ADR-0020, and ``docs/plans/invert-setting-allowlist.md``.
"""

from typing import FrozenSet

# ---------------------------------------------------------------------------
# The allow-set — the whole point of this module
# ---------------------------------------------------------------------------

#: The ONLY fleet-setting keys the chat model may write through the generic
#: MCP ``set_fleet_setting`` tool. Everything else is refused.
#:
#: **Adding a key here grants the LLM write access to it.** That is why the
#: list is named for what it grants rather than for what it withholds: a
#: contributor blocked by the guard test in ``tests/test_setting_policy.py``
#: takes the shortest path out, and "add my key to the not-protected list"
#: reads as bookkeeping, while "add my key to LLM_WRITABLE_SETTING_KEYS" reads
#: as a grant and invites a reviewer to ask why.
#:
#: These two are not a judgement call — they are what the system already
#: documents. ``admz/mcp/tools/fleet.py`` advertises exactly one key to the
#: model (``default_password``); ``default_username`` is its documented other
#: half, written beside it by the capture form
#: (``admz/api/routes/capture.py:325-326``) and read beside it during
#: onboarding (``admz/onboarding.py:149-151``). An exhaustive search of the
#: demos subsystem, the system prompt, module prompt sections, every MCP tool
#: module, the user stories and every test found no evidence of the model
#: writing, or being told to write, any third key.
LLM_WRITABLE_SETTING_KEYS: FrozenSet[str] = frozenset({
    "default_password",
    "default_username",
})

#: Allow-listed keys whose **value** may still never come from the model.
#:
#: ``default_password`` is set through the out-of-band capture URL (ADR-0009):
#: the model asks for a session, a human types the password into a browser,
#: and it never enters LLM context. FR-MCP-008 and two user stories already
#: require this — ``device-onboarding.md:84`` says "never typed into the LLM
#: chat" — but the code accepted a supplied value anyway. It no longer does.
#:
#: A side effect worth naming: with no value in the tool call, no password can
#: reach the audit row that #217 records in cleartext. That does not fix #217,
#: which is a general blindness in ``redact_structure`` to every
#: ``{key, value}``-shaped tool; it removes this tool from its blast radius.
CAPTURE_ONLY_SETTING_KEYS: FrozenSet[str] = frozenset({
    "default_password",
})


# ---------------------------------------------------------------------------
# The inventory — every fleet-setting key that exists, so the guard can check
# ---------------------------------------------------------------------------

#: Every concrete fleet-setting key the codebase reads or writes.
#:
#: This is **documentation with a test attached**, not a security boundary —
#: the boundary is :func:`is_llm_writable` alone, and a key missing from this
#: inventory is still refused. Its job is to make adding a setting a
#: *conscious* act: ``tests/test_setting_policy.py`` walks ``admz/`` with
#: ``ast``, resolving module-level constants bound to string literals, and
#: fails until every key it finds appears here. At that point the author has
#: to decide whether the key belongs in the allow-set above, which is the
#: one-line reviewed decision #212 asked for.
#:
#: The ``confirm_level_*`` keys are deliberately absent: they are generated per
#: risk class from ``admz.confirm_policy`` and covered by a namespace rule, not
#: by enumeration. That is also the guard's known limit — a key built at
#: runtime is invisible to a static scan — and the reason the namespace rule
#: in :func:`admz.fleet_settings.is_protected_setting` survives the inversion.
KNOWN_SETTING_KEYS: FrozenSet[str] = frozenset({
    # --- the fleet credential pair (the allow-set) -------------------------
    "default_password",
    "default_username",
    # The entry-credential LIST (FR-CRED-011, ADR-0061). The pair above stays:
    # it is still what provision_factory_default writes to a factory-defaulted
    # device, and it is read as entry #1 so an existing install keeps working
    # with no migration step. Deliberately NOT LLM-writable — it holds
    # passwords, and widening it widens what ADMZ tries against every device.
    "entry_credentials",
    # FR-CRED-013 posture: store none, prompt every time. A boolean, not a
    # secret — declared here so it is a known key, and deliberately not
    # LLM-writable, since turning it OFF would re-enable stored credentials.
    "entry_credentials_prompt_always",
    # --- confirmation / credential gates (ADR-0006, ADR-0020) -------------
    "confirm_password_hash",
    # Who may APPROVE a confirmation session (GH #178). Deliberately absent
    # from the LLM-writable allow-set above: a model that could widen this
    # could authorize its own pending actions.
    "confirm_approver_groups",
    # `tool_get_credentials_enabled` is deliberately NOT here anymore: the
    # flag was removed (#151) when its last live effect turned out to be an
    # anonymous bypass of the reveal gate. A stale row in an upgraded
    # install is inert, and — like any unknown key — still refuses LLM
    # writes under ADR-0053's deny-by-default.
    # --- chatbot (ADR-0025) ------------------------------------------------
    "gemini_api_key",
    "gemini_default_model",
    "chat_daily_token_budget",
    # --- fleet health ------------------------------------------------------
    "health_monitor_enabled",
    "health_check_interval_seconds",
    "health_check_timeout_seconds",
    # #168: switching this off makes a stale password report healthy.
    "health_verify_credentials",
    # --- survey / contributor mode (ADR-0030) -----------------------------
    "survey_mode_enabled",
    "survey_github_pat",
    "survey_repo",
    "survey_redaction_profile",
    "survey_validation_tier",
    "survey_schedule_seconds",
    "survey_contributor",
    # --- local capability survey (ADR-0063 — for everyone, no contribution)
    "capability_survey_interval_seconds",
    # --- advanced capability switches (ADR-0052) --------------------------
    "event_ingest_enabled",
    "acs_event_ingest_enabled",
    "acs_firebird_enabled",
    # --- event ingest behaviour (admz/events/config.py) -------------------
    # The switch above was protected; these decide what it actually records,
    # and were not. Setting retention to 0 discards the event history.
    "event_topic_filters",
    "event_ingest_tag",
    "event_store_max_rows",
    "event_store_retention_days",
    # --- drift suppression (admz/snapshot/ignore.py) ----------------------
    # #203: a single '*' pattern makes is_ignored() true for every config key.
    "config_ignore_patterns",
    "config_ignore_rules",
    "config_ignore_seed_version",
    # --- snapshot GC (admz/snapshot/maintenance.py) -----------------------
    # Inert today: setters and readers both have zero production callers
    # (docs/specification/review-2026-06-10.md:221). Listed so they cannot
    # become live and unprotected at the same time.
    "snapshot_gc_enabled",
    "snapshot_gc_aggressive",
    # --- ACS Pro module (ADR-0040) ----------------------------------------
    # #195: the master switch and server_url. Its two child flags were
    # protected; the parent was not.
    "acs_pro",
    # Secret guarding the auth-exempt /api/acs/rule-fired endpoint.
    "acs_webhook_token",
    # The Firebird reader's switch is protected; these are its inputs —
    # acs_fb_fbclient becomes the native library the driver loads, once an
    # operator enables the protected capability. Latent, not live.
    "acs_fb_fbclient",
    "acs_fb_install",
    "acs_fb_data_dir",
    # --- GitHub App config backup (ADR-0045) ------------------------------
    "github_app_id",
    "github_app_slug",
    "github_app_private_key",
    # Retired (#172): no longer written, and purged at startup. It stays
    # declared here so that until every install has started once, the value
    # some of them still hold is a *known* key — classified, masked, and
    # (being absent from LLM_WRITABLE) protected by deny-by-default. Dropping
    # it would make it an unknown key holding a live credential.
    "github_app_client_secret",
    "github_app_installation_id",
    "github_config_repo",
})


# ---------------------------------------------------------------------------
# Encryption at rest (GH #296 part 1)
# ---------------------------------------------------------------------------
#
# Every device-account credential ADMZ stores goes through Fernet — that is what
# ``admz.key`` exists for and what #252's DACL protects. Some fleet settings hold
# secrets too, and they were not all covered.
#
# The three sets below partition **every** sensitive key. That partition is
# enforced by a test, and the test is the point: a new secret added to
# ``KNOWN_SETTING_KEYS`` and declared in none of them fails CI rather than
# sitting in plaintext until somebody notices. Fixing one key and calling it
# done is the shape that left three of four subresources unpinned in #200.

#: Encrypted transparently by the ``fleet_settings`` store itself.
#:
#: Keyed on the store rather than on each caller deliberately. ``default_password``
#: alone has three readers (``mcp/server.py``, ``onboarding.py``,
#: ``provisioning.py``) and no dedicated accessor between them; they already
#: share exactly one path — ``fleet_settings.get`` — so encryption belongs
#: there. Patching three call sites instead would be the divergence of #255.
STORE_ENCRYPTED_SETTING_KEYS: FrozenSet[str] = frozenset({
    "default_password",
    # The entry-credential list (FR-CRED-011). ADR-0061 makes these the only
    # route back into a fleet after a database loss, so they are recovery
    # material rather than merely sensitive.
    "entry_credentials",
    "gemini_api_key",
    "acs_webhook_token",
})

#: Already encrypted by their owning module, which called Fernet itself before
#: the store could. Excluded from the store layer so they are not encrypted
#: TWICE — see ``admz/survey/secrets.py`` and ``admz/github_app/secrets.py``,
#: which now share the store's ``encrypt``/``decrypt`` rather than keeping
#: their own copies.
#:
#: Two tiers is not the end state; unifying them means migrating live
#: ciphertext, which is a separate change from making plaintext stop.
MODULE_ENCRYPTED_SETTING_KEYS: FrozenSet[str] = frozenset({
    "survey_github_pat",
    "github_app_private_key",
    "github_app_client_secret",  # legacy leftovers only (#172) — see above
})

#: Sensitive-looking, deliberately NOT encrypted. Both need a reason on record,
#: because "why is this one plaintext?" is exactly the question the partition
#: test provokes.
NOT_ENCRYPTED_SENSITIVE_KEYS: FrozenSet[str] = frozenset({
    # A password HASH, never recovered — only compared. Encrypting it would buy
    # nothing and put the confirmation gate behind key availability. #296 warns
    # specifically against copying this pattern for ``default_password``, which
    # must stay recoverable because ADMZ sends it to a device.
    "confirm_password_hash",
    # A NUMBER. It is only in this list at all because ``redact.is_sensitive_key``
    # matches the token "token"; there is no secret here. (It is consequently
    # also masked in the settings UI, which is cosmetic and pre-existing.)
    "chat_daily_token_budget",
    # A BOOLEAN — whether health checks verify credentials, not a credential.
    # Here for the same reason as the line above: ``redact.is_sensitive_key``
    # gained "credential" in #411 so that ``entry_credentials`` could not sit in
    # plaintext, and this key contains the word. Masking a flag in the settings
    # UI is the cheap side of that trade; the expensive side would be a list of
    # passwords the predicate did not recognise.
    "health_verify_credentials",
    # Also a BOOLEAN — the FR-CRED-013 posture flag ("store none, prompt every
    # time"), not a credential. Second false positive from the same substring.
    # Worth noting rather than absorbing: if a third arrives, "credential"
    # should become a delimiter-bounded match like `pat`/`pwd`/`pass` instead
    # of this list growing. The trade still favours the substring today — a
    # missed list of passwords costs more than a masked flag.
    "entry_credentials_prompt_always",
})


def is_store_encrypted(key: str) -> bool:
    """True iff ``fleet_settings`` encrypts this key's value at rest itself."""
    return key in STORE_ENCRYPTED_SETTING_KEYS


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def is_llm_writable(key: str) -> bool:
    """True iff the chat model may write ``key`` via ``set_fleet_setting``.

    Deny by default: an unknown key — including one added tomorrow and never
    declared anywhere — returns False.
    """
    return key in LLM_WRITABLE_SETTING_KEYS


def is_capture_only(key: str) -> bool:
    """True iff ``key`` is allow-listed but its value may not come from chat.

    Callers must refuse a supplied value and issue an out-of-band capture URL
    instead. See :data:`CAPTURE_ONLY_SETTING_KEYS`.
    """
    return key in CAPTURE_ONLY_SETTING_KEYS
