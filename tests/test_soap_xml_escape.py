"""Issue #144: caller params must not escape their element in a SOAP envelope.

The house pattern from #10 / PR #146 is a parametrized table with a ``reason``
per case, **paired with an accept table** — a guard that passes by refusing
everything is not a guard. Here the reject table becomes an *escape* table,
because the settled fix escapes rather than rejects: a legitimate recipient
value is ``camera=entrance&event=motion``, and ``&amp;`` decodes back to ``&``
at the device where a reject-list would break a real operation.

Templates below are synthetic on purpose. The pinned atlas SHA carries 30
``ws/`` ops and a developer's local checkout may carry a different set (the
recipient ops landed in the pinned commit itself), so a test keyed to a real
catalog entry would pass in CI and fail locally, or the reverse. The real
catalog is exercised separately, defensively, at the bottom of this file.
"""

import pytest
from xml.etree import ElementTree

from admz.executor.vapix import VapixExecutor, _xml_escape_param


# A placeholder in element text — the shape every one of the 30 catalogued
# ``ws/`` templates uses (verified mechanically against the pinned SHA; not a
# single placeholder sits inside an attribute value). Namespaces are omitted
# so the structural assertions stay readable; a namespaced real-catalog
# template is covered by TestRealCatalogTemplates.
SOAP_TEMPLATE = """<Envelope>
 <Body>
  <GetDoorState>
   <Token>{token}</Token>
  </GetDoorState>
 </Body>
</Envelope>
"""


def soap_op(body_xml=SOAP_TEMPLATE):
    return {
        "id": "door-control-service:GetDoorState",
        "_generation": "soap",
        "method": "POST",
        "soap_action": "http://www.axis.com/vapix/ws/door-control/GetDoorState",
        "request": {"body_xml": body_xml},
    }


@pytest.fixture
def executor():
    return VapixExecutor(timeout=2.0)


class TestEscapeTable:
    """Every XML metacharacter is neutralised before it reaches the body."""

    @pytest.mark.parametrize(
        "value,expected,reason",
        [
            ("&", "&amp;", "bare-ampersand"),
            ("<", "&lt;", "open-angle"),
            (">", "&gt;", "close-angle"),
            ('"', "&quot;", "double-quote"),
            ("'", "&apos;", "single-quote"),
            # The ordering canary. If "&" were replaced anywhere but FIRST,
            # "<" would already have become "&lt;" and its ampersand would be
            # re-escaped to "&amp;lt;". This row is the only thing that
            # distinguishes a correct escaper from that classic bug.
            ("<&>", "&lt;&amp;&gt;", "ampersand-replaced-first"),
            # A value that is *already* an entity must be escaped again, so it
            # decodes back to the literal text the caller sent.
            ("&amp;", "&amp;amp;", "pre-escaped-entity-not-passed-through"),
            ("&lt;", "&amp;lt;", "pre-escaped-angle-not-passed-through"),
            # The breakout attempts this issue exists to stop.
            (
                "x</Token><Injected/>",
                "x&lt;/Token&gt;&lt;Injected/&gt;",
                "sibling-element-injection",
            ),
            (
                "</Token></GetDoorState><LockDownDoor><Token>t",
                "&lt;/Token&gt;&lt;/GetDoorState&gt;&lt;LockDownDoor&gt;"
                "&lt;Token&gt;t",
                "cross-operation-pivot",
            ),
            ("]]><!--", "]]&gt;&lt;!--", "cdata-and-comment-punctuation"),
            ("<![CDATA[x]]>", "&lt;![CDATA[x]]&gt;", "cdata-open"),
        ],
    )
    def test_metacharacters_are_escaped(self, value, expected, reason):
        assert _xml_escape_param(value) == expected

    def test_non_string_values_are_coerced_then_escaped(self):
        """The MCP surface passes real ints/bools, not just strings."""
        assert _xml_escape_param(100) == "100"
        assert _xml_escape_param(True) == "True"
        assert _xml_escape_param(None) == "None"


class TestAcceptTable:
    """The paired half: every legitimate shape survives verbatim.

    Without this class the escape table could be satisfied by rejecting or
    stripping, which would break real fleet operations — the failure mode that
    gets a security fix reverted.
    """

    LEGITIMATE = [
        ("Axis-00408c184bdb:1352121495.979065000", "door-token-colon-dot"),
        ("tns1:Device/tnsaxis:IO/VirtualInput", "topic-colons-and-slashes"),
        ('boolean(//SimpleItem[@Name="port" and @Value="1"])', "xpath-filter"),
        ("Rule active", "name-with-space"),
        ("com.axis.action.fixed.ledcontrol", "dotted-template-token"),
        ("com.axis.recipient.networkshare", "dotted-recipient-template"),
        ("2024-01-01T00:00:00", "iso-8601"),
        # The single strongest argument for escape-over-reject.
        ("camera=entrance&event=motion", "query-string-with-ampersand"),
        ('{"event":"triggered"}', "json-payload"),
        ("http://10.0.0.1/notify", "url"),
        ("/etc/audioclips/alarm.mp3", "absolute-posix-path"),
        ("#ffffff", "hex-colour"),
        ("amber,none", "comma-joined-enum"),
        ("standard_office_hours", "snake-case-schedule-id"),
        ("Content-Type: application/json", "header-literal"),
        ("axis/event", "mqtt-topic"),
        ("SIP", "bare-profile-name"),
        ("100", "numeric-limit"),
        ("", "empty-string"),
    ]

    @pytest.mark.parametrize("value,reason", LEGITIMATE)
    def test_round_trips_verbatim_through_a_parser(
        self, executor, value, reason
    ):
        """Build the body, parse it, and get the caller's exact bytes back."""
        req = executor._build_soap(soap_op(), {"token": value})

        root = ElementTree.fromstring(req.raw_body)
        token_el = root.find("Body/GetDoorState/Token")

        assert token_el is not None, f"{reason}: element vanished"
        # ElementTree reports an empty element's text as None.
        assert (token_el.text or "") == value, f"{reason}: value not verbatim"

    @pytest.mark.parametrize("value,reason", LEGITIMATE)
    def test_body_remains_well_formed(self, executor, value, reason):
        req = executor._build_soap(soap_op(), {"token": value})
        ElementTree.fromstring(req.raw_body)  # raises if malformed


class TestCannotEscapeItsElement:
    """The end-to-end assertion: crafted input adds no structure."""

    def test_sibling_injection_yields_no_extra_elements(self, executor):
        hostile = "x</Token><Injected/>"
        req = executor._build_soap(soap_op(), {"token": hostile})

        root = ElementTree.fromstring(req.raw_body)
        op_el = root.find("Body/GetDoorState")

        assert len(list(op_el)) == 1, "injection added a sibling element"
        assert op_el[0].tag == "Token"
        assert root.find(".//Injected") is None
        assert op_el[0].text == hostile, "hostile value must survive as text"

    def test_cross_operation_pivot_is_not_reachable(self, executor):
        """The severity claim in #144: a read-only op's ungated envelope must
        not be able to name an operation whose risk demands a password."""
        hostile = "</Token></GetDoorState><LockDownDoor><Token>d"
        req = executor._build_soap(soap_op(), {"token": hostile})

        root = ElementTree.fromstring(req.raw_body)
        assert root.find(".//LockDownDoor") is None
        assert len(list(root.find("Body"))) == 1

    def test_only_the_body_is_caller_influenced(self, executor):
        """Method and path are fixed by the builder, never by a param.

        Note for anyone reading this while assessing severity: ``_build_soap``
        computes a ``headers_extra`` dict containing ``SOAPAction`` and then
        never passes it to ``ExecutionRequest`` (which has no such field) —
        those two lines are its only references in the entire codebase, so
        **no SOAP request carries a SOAPAction header at all**. That is a
        pre-existing wire-behaviour defect, deliberately left alone here
        because fixing it changes what all 30 SOAP ops send and needs its own
        device testing. It is recorded because it *removes* a mitigating
        factor: with no dispatch header, the device has only the body element
        to dispatch on, so escaping the body is the whole defence rather than
        a second layer behind the header.
        """
        req = executor._build_soap(
            soap_op(), {"token": "</Token><LockDownDoor/>", "path": "/evil"}
        )
        assert req.method == "POST"
        assert req.path == "/vapix/services"
        assert req.content_type == "application/xml"


class TestTrustedContentIsNotEscaped:
    """Only caller values are escaped — authored template content is live XML."""

    def test_template_markup_stays_live(self, executor):
        req = executor._build_soap(soap_op(), {"token": "t"})
        assert "<Envelope>" in req.raw_body
        assert "&lt;Envelope&gt;" not in req.raw_body

    def test_authored_default_is_not_escaped(self, executor):
        """``{limit=100}`` defaults come from the catalog, not the caller.

        The param supplied here is a different one, so ``limit`` falls back to
        its authored default and must not be routed through the escaper.
        """
        body = "<Envelope><Body><Get><Limit>{limit=100}</Limit>" \
               "<Tok>{token}</Tok></Get></Body></Envelope>"
        req = executor._build_soap(soap_op(body), {"token": "a&b"})

        root = ElementTree.fromstring(req.raw_body)
        assert root.find("Body/Get/Limit").text == "100"
        assert root.find("Body/Get/Tok").text == "a&b"

    def test_unresolved_placeholder_is_left_alone(self, executor):
        """A template slot with no param and no default stays literal rather
        than collapsing the element."""
        req = executor._build_soap(soap_op(), {"unrelated": "x"})
        assert "{token}" in req.raw_body


class TestRunnerOverridePathUnaffected:
    """``rules/runner.py`` pre-renders the body and forces ``params={}``.

    That path must stay byte-identical: the atlas already escaped what needed
    escaping, and the fragment it emits is deliberately live XML. See
    runner.py:180-185 and tests/test_rule_runner.py:117-119 for the other half.
    """

    PRE_RENDERED = (
        '<Envelope><Body><aa:AddActionConfiguration>'
        '<aa:Parameters><aa:Parameter Name="led" Value="amber,none"/>'
        "</aa:Parameters>"
        "</aa:AddActionConfiguration></Body></Envelope>"
    )

    def test_empty_params_leaves_body_byte_identical(self, executor):
        req = executor._build_soap(soap_op(self.PRE_RENDERED), {})
        assert req.raw_body == self.PRE_RENDERED

    def test_pre_rendered_parameter_markup_stays_live(self, executor):
        req = executor._build_soap(soap_op(self.PRE_RENDERED), {})
        root = ElementTree.fromstring(
            req.raw_body.replace("aa:", "")  # strip the undeclared prefix
        )
        assert root.find("Body/AddActionConfiguration/Parameters/Parameter") \
            is not None


class TestNoOperationIsExempt:
    """The carve-out for the raw-fragment params was measured away (#144).

    No in-repo caller reaches ``AddActionConfiguration.parameters`` through the
    placeholder path — the only consumer uses ``body_override``. So the sole
    route that reaches it is the untrusted generic execute surface, and it is
    escaped like everything else. This test is the regression lock on that
    decision: if someone reintroduces an exemption, it fails.
    """

    ADD_CONFIG = (
        "<Envelope><Body><AddActionConfiguration><NewActionConfiguration>"
        "<TemplateToken>{template_token}</TemplateToken>"
        "<Name>{name}</Name>"
        "<Parameters>{parameters}</Parameters>"
        "</NewActionConfiguration></AddActionConfiguration></Body></Envelope>"
    )

    def test_parameters_param_is_escaped_like_any_other(self, executor):
        req = executor._build_soap(
            soap_op(self.ADD_CONFIG),
            {
                "template_token": "com.axis.action.fixed.ledcontrol",
                "name": "Rule active",
                "parameters": '<Parameter Name="x" Value="1"/>',
            },
        )

        root = ElementTree.fromstring(req.raw_body)
        params_el = root.find(
            "Body/AddActionConfiguration/NewActionConfiguration/Parameters"
        )
        # The fragment arrives as TEXT, not as structure.
        assert len(list(params_el)) == 0
        assert params_el.text == '<Parameter Name="x" Value="1"/>'
        # And the ops's own trusted markup is untouched.
        assert root.find(
            "Body/AddActionConfiguration/NewActionConfiguration/Name"
        ).text == "Rule active"


class TestRealCatalogTemplates:
    """Exercise a genuine, namespaced catalog template if atlas is installed.

    Defensive by design: the catalogued op set differs between the pinned SHA
    and a local checkout, so a missing op skips rather than fails.
    """

    def _get_op(self, op_id):
        try:
            from axis_api_atlas import Atlas, default_data_path

            op = Atlas(default_data_path()).operation(op_id, "vapix")
        except Exception as exc:  # pragma: no cover - environment-dependent
            pytest.skip(f"atlas catalog unavailable: {exc}")
        if op is None:
            pytest.skip(f"{op_id} not in the installed atlas")
        return op.to_executor_dict()

    def test_real_getdoorstate_template_escapes_a_breakout(self, executor):
        op = self._get_op("door-control-service:GetDoorState")
        hostile = "</Token><LockDownDoor/>"

        req = executor._build_soap(op, {"token": hostile})

        assert "<LockDownDoor/>" not in req.raw_body
        assert "&lt;/Token&gt;&lt;LockDownDoor/&gt;" in req.raw_body
        root = ElementTree.fromstring(req.raw_body)  # still well-formed
        assert root.find(".//LockDownDoor") is None

    def test_real_template_round_trips_a_legitimate_token(self, executor):
        op = self._get_op("door-control-service:GetDoorState")
        token = "Axis-00408c184bdb:1352121495.979065000"

        req = executor._build_soap(op, {"token": token})

        root = ElementTree.fromstring(req.raw_body)
        texts = [el.text for el in root.iter() if el.text and el.text.strip()]
        assert token in texts, "legitimate door token did not survive verbatim"
