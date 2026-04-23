---
fip: 1
title: FIP Process
author: Dercio (@creedscode)
status: Draft
type: Process
created: 2026-04-22
---

# FIP-1 - FIP Process

## Abstract

This document defines the Federation Improvement Proposal (FIP) process: what a FIP is, how one is written, how it is reviewed, and how it becomes part of the protocol. It is itself a FIP, of category `Process`, and is the canonical reference for all subsequent FIPs.

## Motivation

The protocol described in `SPEC.md` is intentionally minimal. It defines the federation contract - identities, contexts, memberships, content base contract, JWT + RLS - but deliberately leaves provider adapters, content types, auth flows, and other extension points to be specified separately.

Without a written process for those specifications, implementers diverge. Two bots speak the same protocol but disagree on what a workshop code is. Two frontends render profiles differently because no document pins down what fields exist. The FIP process exists to prevent that drift.

The process is modeled on Ethereum's EIP system and Python's PEP system, both of which have demonstrated that lightweight, written, reviewable proposals scale to large communities without becoming bureaucratic.

## Specification

### What a FIP is

A FIP is a markdown document that:

- Has a unique number, assigned in order of submission
- Has a title in the form `FIP-N - Title`
- Belongs to exactly one category (see §Categories)
- Has a status reflecting its current lifecycle stage (see §Statuses)
- Follows the template defined in this document
- Lives in the `fips/` directory of the protocol repository

A FIP is the unit of protocol evolution. Implementations declare which FIPs they support; users and other implementers can read FIPs to understand exactly what behavior is expected.

### Categories

Every FIP MUST declare exactly one category in its header.

- **Core** - changes to `SPEC.md` itself: data model, address format, JWT contract, RLS conventions, authorization model. Highest review bar.
- **Auth** - provider adapters, authentication flows, identity-related primitives that don't change the core model.
- **Content** - content type definitions. New tables, schemas, RLS templates for specific kinds of user-generated content.
- **Bot** - bot-proxy authentication, bot-side conventions, integration patterns for third-party bots.
- **Process** - meta-changes to the FIP process itself, governance, repository structure. This FIP is one.

A FIP MAY span concerns but MUST pick the dominant category. A FIP that defines a new content type AND requires a JWT claim addition is `Core` (the JWT change has higher bar) and SHOULD be split.

### Statuses

A FIP progresses through statuses in order. Backwards transitions are allowed only for `Withdrawn`.

- **Draft** - author is actively writing. Open to fundamental restructuring. May be incomplete.
- **Review** - author considers the FIP complete and is soliciting community feedback. Minimum 14-day review period before advancing.
- **Accepted** - review period closed, no blocking objections, at least one reference implementation exists or is committed. Implementations MAY begin building against the FIP.
- **Final** - FIP is implemented in the reference deployment and considered stable. Breaking changes require a new FIP that supersedes this one.
- **Withdrawn** - author has retracted the FIP. May be reopened but only by re-numbering as a new FIP.
- **Rejected** - community consensus is against the FIP. Should not be re-submitted without substantive changes.

### Numbering

FIPs are numbered sequentially in order of first PR submission, regardless of category or eventual status. Numbers are not reserved.

A withdrawn or rejected FIP retains its number; that number is not reused.

This FIP is **FIP-1** by virtue of being the first written.

### Required sections

Every FIP MUST contain the following sections in order:

1. **Header** (YAML frontmatter) - fip, title, author, status, type, created
2. **Abstract** - one paragraph, plain English, what this FIP changes or adds
3. **Motivation** - why this needs to exist; what breaks or is missing without it
4. **Specification** - the normative content. Use RFC 2119 keywords (MUST, SHOULD, MAY) for requirements
5. **Rationale** - why this design? what alternatives were considered and rejected?
6. **Backwards Compatibility** - does this break existing implementations? migration path?
7. **Reference Implementation** - link to a PR or commit demonstrating the FIP in working code; required to advance from Review to Accepted
8. **Security Considerations** - attack vectors, trust assumptions, abuse potential
9. **Copyright** - typically `CC0` for spec work

Optional sections (used when relevant):

- **Requires** - list of FIP numbers this depends on
- **Supersedes** - list of FIP numbers this replaces
- **Test Vectors** - concrete examples for implementers to verify against

### Header format

YAML frontmatter at the top of the file:

```yaml
---
fip: <number>
title: <title without "FIP-N - " prefix>
author: <name> (@<github-handle>)
status: Draft | Review | Accepted | Final | Withdrawn | Rejected
type: Standards | Informational | Process
category: Core | Auth | Content | Bot | Process
created: YYYY-MM-DD
requires: FIP-N, FIP-M    # optional
supersedes: FIP-N         # optional
---
```

`type` distinguishes:
- **Standards** - defines normative protocol behavior (most FIPs)
- **Informational** - provides guidance, recommendations, or analysis without normative requirements
- **Process** - defines or changes the FIP process itself (rare)

The `category` field is omitted for `Process` FIPs.

### Lifecycle

```
[Draft]                  ← author writes, iterates
   ↓ author opens PR
[Draft] (in PR review)   ← editors review template compliance
   ↓ editors merge as Draft
[Draft]                  ← lives in repo, can still be edited freely
   ↓ author advances when complete
[Review]                 ← 14-day minimum, community feedback
   ↓ no blocking objections + reference impl exists
[Accepted]               ← implementations begin building
   ↓ deployed to reference platform, observed stable
[Final]                  ← canonical, frozen
```

Advancement from one status to the next is initiated by the FIP author and ratified by an editor. Editors verify procedural compliance (template followed, review period observed, reference implementation linked); they do not adjudicate technical merit, which is the community's role during review.

### Editors

A small group of editors maintains the FIPs repository. Editors:

- Verify FIPs follow the template
- Assign FIP numbers
- Merge PRs that meet procedural requirements
- Update statuses as FIPs advance
- Do NOT decide whether a FIP is technically correct - that emerges from community review and implementation experience

Editorship is initially held by Dercio (`@creedscode`). New editors are added by consensus of existing editors. The editor list is maintained in `EDITORS.md` at the root of the FIPs repository.

### Repository structure

```
spec/
  SPEC.md                    ← living protocol specification
fips/
  README.md                  ← index of all FIPs with status
  EDITORS.md                 ← current editors
  FIP-1-fip-process.md       ← this document
  FIP-2-discord-adapter.md
  FIP-3-profile.md
  ...
```

Filename convention: `FIP-<N>-<kebab-case-title>.md`. The number in the filename matches the `fip` field in the header.

### Discussion

Substantive discussion happens in the GitHub PR for the FIP. Each status change SHOULD reference the PRs and issues where the discussion occurred.

For pre-FIP brainstorming, GitHub Discussions on the protocol repository is the recommended venue. The bar to open a discussion is zero; the bar to open a FIP PR is "this idea is worth writing down precisely."

### Amendments

Once a FIP reaches `Final`, its content is frozen. Changes require either:

- A new FIP that supersedes it (declared via the `supersedes:` header field), OR
- An editorial PR for purely non-normative corrections (typos, formatting, broken links). Editorial PRs MUST NOT change technical meaning.

Pre-Final FIPs MAY be edited freely by their author.

## Rationale

### Why model on EIPs/PEPs

Both ecosystems have demonstrated that:

- Lightweight written proposals scale to large, distributed communities
- Status fields provide clear "what is the state of this idea" signals
- Editors-as-process-not-judges keeps technical authority distributed
- Numbered references (`EIP-1559`, `PEP-8`) become durable cultural artifacts that outlast any single document

Adopting their conventions reduces invention; FIP authors familiar with EIPs/PEPs can contribute immediately.

### Why categories matter

Different kinds of changes warrant different review intensity. A new content type (Content) affects only nodes that opt in; a JWT claim change (Core) affects every implementation forever. Categorizing up front sets reviewer expectations and prevents low-stakes proposals from drowning in process.

### Why a 14-day review minimum

Long enough for asynchronous global review; short enough to maintain momentum. Mirrors EIP "Last Call" period. Authors may extend voluntarily.

### Why editors don't decide technical merit

The protocol is permissionless to extend (anyone can write a FIP) but not permissionless to standardize (community consensus required). Concentrating technical authority in editors creates bottlenecks and grudges. Distributing it across reviewers and implementations creates organic legitimacy: a FIP becomes "real" by being implemented and used, not by being blessed.

### Why filenames include both number and title

`FIP-1-fip-process.md` is more useful than `1.md` when listed in a directory. The title in the filename is convenience, not authority - the `title:` field in the header is canonical.

## Backwards Compatibility

This is the first FIP. Nothing to break.

## Reference Implementation

The reference implementation of this FIP is the existence of the `fips/` directory with this document at `fips/FIP-1-fip-process.md` in the protocol repository.

## Security Considerations

The FIP process itself has minimal security surface. Two considerations worth noting:

**Editor compromise.** A malicious editor could merge non-conformant FIPs, advance Drafts to Final without review, or assign duplicate numbers. Mitigations: multiple editors required for non-trivial decisions once the editor list grows beyond one; Git history provides a tamper-evident audit log.

**Author impersonation.** A FIP could be submitted in someone else's name. Mitigations: PRs require GitHub account ownership; the `author` field SHOULD include a verifiable handle (GitHub, email).

Neither risk is significant at current scale. Both deserve revisiting if the editor pool or proposal volume grows substantially.

## Copyright

This document and all FIPs published under this process are licensed CC0 1.0 Universal (Public Domain Dedication) unless otherwise noted in the FIP itself.