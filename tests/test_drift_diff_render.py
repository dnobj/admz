"""Drift diff rendering — per-rule subgroup collapse (#263, follows #230/#247).

#247 grouped `action_rules` drift per rule and shipped headers + counts, but the
headers were inert labels: `toggleDriftGroup` matches only `tr.drift-field-row`
(the *revertable* rows), and rule rows are `row-readonly`, so nothing could ever
toggle them. The block was collapsed by default — so it looked fixed — and the
first click dumped all 36 rows at once. **That defect was invisible in the diff
and is the reason these tests execute the renderer instead of reading it.**

The renderer is client-side JS inside `index.html`, so there is nothing Jinja can
render and nothing Python can import. These tests therefore run the REAL
`renderDiff` source — sliced verbatim out of the template by brace matching, never
copied — under Node with a deliberately tiny DOM shim, and assert on the HTML it
actually emits and on what the real toggles actually do to it.

The shim **throws on any selector it does not implement**, so production code that
outgrows it fails loudly here rather than passing against a fake.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[1] / "admz" / "api" / "templates" / "index.html"

# GitHub-hosted runners (ubuntu-latest / windows-latest) ship Node, so this runs
# on both CI legs. Skipping locally is acceptable; skipping in CI would not be.
pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is required to execute the template's JS")


HARNESS = r"""
'use strict';
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync(process.argv[2], 'utf8');

// ---- slice the real functions out of the template (never copy them) --------
function extract(name, optional) {
  const i = src.indexOf('function ' + name + '(');
  if (i < 0) {
    // Optional so that reverting the fix leaves the BEHAVIOURAL assertions
    // runnable. If a missing function aborted the harness, every test would go
    // red for one incidental reason and the mutation check would prove nothing.
    if (optional) return 'function ' + name + '() { /* absent in template */ }';
    throw new Error('function not found in template: ' + name);
  }
  let depth = 0, started = false;
  for (let j = i; j < src.length; j++) {
    const ch = src[j];
    if (ch === '{') { depth++; started = true; }
    else if (ch === '}') { depth--; if (started && depth === 0) return src.slice(i, j + 1); }
  }
  throw new Error('unbalanced braces extracting: ' + name);
}
const CODE = [['esc', false], ['renderDiff', false], ['toggleReadOnly', false],
              ['toggleDriftGroup', false], ['toggleRoGroup', true]]
  .map(([n, opt]) => extract(n, opt)).join('\n\n');

// ---- tiny DOM shim: fails loudly rather than faking ------------------------
function stub() { return { style: {}, classList: mkClassList(''), querySelector: () => stub() }; }
function mkClassList(cls) {
  const set = new Set(String(cls).split(/\s+/).filter(Boolean));
  return {
    contains: (c) => set.has(c),
    add: (c) => set.add(c),
    remove: (c) => set.delete(c),
    toggle: (c) => (set.has(c) ? (set.delete(c), false) : (set.add(c), true)),
    _all: () => Array.from(set),
  };
}
function selectClass(sel) {
  const m = /^(?:tr)?\.([A-Za-z0-9_-]+)$/.exec(String(sel).trim());
  if (!m) throw new Error('DOM shim: unsupported selector ' + JSON.stringify(sel));
  return m[1];
}

function buildTable(html) {
  const rows = [];
  const re = /<tr\b([^>]*)>/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    const attrs = m[1];
    const cls = (/class="([^"]*)"/.exec(attrs) || [, ''])[1];
    const dg = (/data-group="([^"]*)"/.exec(attrs) || [, null])[1];
    const style = (/style="([^"]*)"/.exec(attrs) || [, ''])[1];
    const tr = {
      _cls: cls,
      classList: mkClassList(cls),
      style: { display: /display:\s*none/.test(style) ? 'none' : '' },
      getAttribute: (n) => (n === 'data-group' ? dg : null),
    };
    tr.cell = {
      closest: (s) => (s === 'tr' ? tr : (s === 'table' ? table : null)),
      querySelector: () => stub(),
    };
    rows.push(tr);
  }
  const qsa = (sel) => { const c = selectClass(sel); return rows.filter(r => r.classList.contains(c)); };
  const tbody = { querySelectorAll: qsa };
  rows.forEach(r => { r.parentElement = tbody; });
  const table = { querySelectorAll: qsa, _rows: rows };
  return { table, tbody, rows };
}

// ---- run the real renderDiff ----------------------------------------------
const payload = JSON.parse(process.argv[3]);
let captured = '';
const el = () => ({
  style: {},
  classList: { remove: () => {}, add: () => {} },
  set innerHTML(v) { captured = v; },
  get innerHTML() { return captured; },
  querySelector: () => null,
  querySelectorAll: () => [],
});
const diffEl = el();
const sandbox = {
  console,
  window: {},
  document: {
    getElementById: (id) => (id.startsWith('diff-') ? diffEl : { style: {} }),
    querySelectorAll: () => [],
  },
  updateRevertBtn: () => {},
  openIgnoreMenu: () => {},
  refreshDiff: () => {},
  driftFreshBanner: () => '',
  __payload: payload,
  __out: null,
  buildTable,
  selectClass,
};
vm.createContext(sandbox);
vm.runInContext(CODE + "\n;__out = (function(){ renderDiff('d1', __payload); return null; })();",
                sandbox, { filename: 'index.html:extracted' });

const html = captured;
const { table, rows } = buildTable(html);
const snap = () => rows.map(r => ({ cls: r._cls, group: r.getAttribute('data-group'),
                                    shown: r.style.display !== 'none' }));

const states = { initial: snap() };

// Open the read-only block, the way the operator does.
const roHead = rows.find(r => r.classList.contains('ro-group-head'));
sandbox.toggleReadOnly(roHead.cell);
states.block_open = snap();

// Open ONE rule.
const sub = rows.filter(r => r.classList.contains('ro-subgroup-head'));
sandbox.toggleRoGroup(sub[0].cell);
states.rule_open = snap();
states.opened_group = sub[0].getAttribute('data-group');

// Close the block again while that rule is still expanded.
sandbox.toggleReadOnly(roHead.cell);
states.block_closed = snap();
states.subgroup_open_flags = sub.map(s => s.classList.contains('grp-open'));

process.stdout.write(JSON.stringify({ html, states }));
"""


def _fields():
    """Three action rules x 4 keys (12 read-only rule rows), one ungrouped
    read-only row, one revertable row — the shape that produced "36 changes"."""
    out = []
    for rid, name in (("9", "Door held"), ("175", "Motion record"), ("194", "")):
        for leaf in ("name", "enabled", "actionConfig.template", "conditions.0.topic"):
            out.append({
                "facet": "action_rules", "path": f"{rid}.{leaf}",
                "expected": "old", "actual": "new",
                "canonical_key": f"action_rules:{rid}.{leaf}",
                "bucket": "unclaimed", "revertable": False,
            })
            if leaf == "name" and name:
                out[-1]["actual"] = name
    out.append({"facet": "applications", "path": "acap.state", "expected": "a",
                "actual": "b", "canonical_key": "applications:acap.state",
                "bucket": "unclaimed", "revertable": False})
    out.append({"facet": "params", "path": "root.Image.Name", "expected": "x",
                "actual": "y", "canonical_key": "root.Image.Name",
                "bucket": "unclaimed", "revertable": True})
    return out


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    harness = tmp_path_factory.mktemp("js") / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    payload = json.dumps({"drifted_fields": _fields()})
    proc = subprocess.run(
        ["node", str(harness), str(TEMPLATE), payload],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail("node harness failed:\n" + proc.stdout[-2000:] + "\n" + proc.stderr[-4000:])
    return json.loads(proc.stdout)


class TestPerRuleSubgroupWiring:
    """The markup half: #263 was exactly a missing attribute and a missing handler."""

    def test_subgroup_headers_carry_the_toggle_wiring(self, rendered):
        html = rendered["html"]
        for rid in ("9", "175", "194"):
            head = f'<tr class="ro-subgroup-head ro-collapsed" data-group="action_rules/{rid}"'
            assert head in html, f"rule {rid} header missing data-group wiring"
        assert html.count('onclick="toggleRoGroup(this)"') == 3
        assert html.count('class="grp-chev"') >= 3          # a chevron per rule
        assert "Rule 175" in html and "Motion record" in html   # named rule
        assert "Rule 194" in html                               # unnamed degrades cleanly

    def test_rule_rows_carry_the_matching_group_and_start_collapsed(self, rendered):
        initial = rendered["states"]["initial"]
        grouped = [r for r in initial if "ro-grouped" in r["cls"]]
        assert len(grouped) == 12                            # 3 rules x 4 keys
        assert {r["group"] for r in grouped} == {
            "action_rules/9", "action_rules/175", "action_rules/194"}
        # Every read-only row starts hidden. (Revertable rows are a separate
        # table section and are legitimately visible — not this block's concern.)
        readonly = [r for r in initial if "row-readonly" in r["cls"]
                    or "ro-subgroup-head" in r["cls"] or "ro-group-head" in r["cls"]]
        assert not any(r["shown"] for r in readonly if "ro-group-head" not in r["cls"])

    def test_ungrouped_readonly_rows_keep_the_old_shape(self, rendered):
        """The constraint: rows that aren't rule-grouped stay all-or-nothing."""
        initial = rendered["states"]["initial"]
        ungrouped = [r for r in initial
                     if "row-readonly" in r["cls"] and "ro-grouped" not in r["cls"]]
        assert len(ungrouped) == 1                           # the applications row
        assert "ro-collapsed" in ungrouped[0]["cls"]
        assert not ungrouped[0]["group"]


class TestPerRuleCollapseBehaviour:
    """The half that reading the diff cannot establish: what the toggles DO."""

    def test_opening_the_block_shows_rules_not_rows(self, rendered):
        """The #263 regression itself — one click used to reveal all 36 rows.

        Counted, not quantified over a set that is empty pre-fix: "no ro-grouped
        row is visible" passes vacuously against the old code, where no row is
        ro-grouped at all. The visible-row COUNT cannot pass vacuously.
        """
        st = rendered["states"]["block_open"]
        heads = [r for r in st if "ro-subgroup-head" in r["cls"]]
        assert len(heads) == 3 and all(h["shown"] for h in heads)

        # 13 read-only field rows exist (12 rule + 1 ungrouped). Opening the block
        # must reveal exactly the ungrouped one; the rule rows stay behind their
        # own headers. Pre-fix this is 13.
        shown_rows = [r for r in st if "row-readonly" in r["cls"] and r["shown"]]
        assert len(shown_rows) == 1, (
            f"opening the block revealed {len(shown_rows)} read-only rows; "
            "expected only the ungrouped one")
        assert "ro-grouped" not in shown_rows[0]["cls"]       # all-or-nothing preserved

    def test_opening_one_rule_shows_only_that_rule(self, rendered):
        st = rendered["states"]["rule_open"]
        opened = rendered["states"]["opened_group"]
        shown = {r["group"] for r in st if "ro-grouped" in r["cls"] and r["shown"]}
        assert shown == {opened}

    def test_closing_the_block_closes_the_expanded_rule(self, rendered):
        """No orphaned visible rows under a collapsed block."""
        st = rendered["states"]["block_closed"]
        readonly = [r for r in st if "row-readonly" in r["cls"]
                    or "ro-subgroup-head" in r["cls"]]
        assert not any(r["shown"] for r in readonly)
        assert not any(rendered["states"]["subgroup_open_flags"])
