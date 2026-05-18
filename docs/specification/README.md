# ADMZ Specification

This directory holds the **specification of record** for ADMZ — the Axis Device Management Zone.

It is the answer to questions like: *what is this project supposed to do, for whom, and under what constraints?*

## Who this is for

- **Operators and users** of ADMZ who want to understand what the system promises.
- **Developers** adding features — to know which existing requirements they must not violate.
- **External contributors** writing catalog entries, discovery protocols, snapshot facets, or registry backends — to understand the contracts they need to satisfy.
- **Reviewers** evaluating proposed changes — to check that they fit the spec.

## How to read it

Start with **[INDEX.md](INDEX.md)** for the full table of contents.

If you're new to ADMZ:

1. Read **[00-overview.md](00-overview.md)** for mission, scope, and non-goals.
2. Skim the **[personas/](personas/)** to learn who ADMZ is built for.
3. Skim the **[user-stories/](user-stories/)** to see the workflows it must support.
4. Dive into **[requirements/](requirements/)** for the per-capability detail.
5. Refer to **[decisions/](decisions/)** when you need the *why* behind a design choice.
6. Use **[glossary.md](glossary.md)** when you hit unfamiliar terms.

## What this is *not*

- **Not a tutorial.** For "how do I use ADMZ to do X," see the top-level `docs/` guides (e.g. `MCP_INTEGRATION.md`, `VAULT_SETUP.md`).
- **Not an API reference.** For per-tool / per-endpoint detail, see `docs/MCP_TOOLS_REFERENCE.md` and the OpenAPI doc served at `/api/docs`.
- **Not the design history.** Design docs like `ARCHITECTURE.md`, `VAPIX_CATALOG_DESIGN.md`, and `EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md` capture the thinking that led here. This spec captures the conclusions.
- **Not a code review.** Where the spec and the code disagree, the spec wins — but those gaps are flagged as known issues, not silently papered over.

## Status

This is a living document. The current snapshot was generated 2026-05-17 from a thorough review of the codebase (committed plus 158 files of WIP) and the existing design docs. Sections are tagged with status hints (✅ implemented, 🚧 partial, 📋 planned) where relevant.

Edit freely. When the code changes, the spec should change with it. When the spec changes, callers should be able to find the *why* in a decision record.
