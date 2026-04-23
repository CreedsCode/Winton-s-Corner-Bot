# Federation Improvement Proposals

This directory contains the FIPs that define the protocol's behavior beyond the core specification (`../spec/SPEC.md`).

The FIP process itself is defined in [FIP-1 - FIP Process](FIP-1-fip-process.md).

## Index

| Number | Title | Category | Status |
|---|---|---|---|
| FIP-1 | [FIP Process](FIP-1-fip-process.md) | Process | Draft |
| FIP-2 | [Discord Provider Adapter](FIP-2-discord-adapter.md) | Auth | Draft |
| FIP-3 | [Profile](FIP-3-profile.md) | Content | Draft |
| FIP-4 | [Workshop Codes](FIP-4-workshop-codes.md) | Content | Draft |
| FIP-5 | [Context Registration](FIP-5-context-registration.md) | Auth | Draft |
| FIP-6 | [Bot-Proxy Authentication](FIP-6-bot-proxy-auth.md) | Bot | Draft |

## Reading order for new implementers

If you are implementing this protocol from scratch, read in this order:

1. `../spec/SPEC.md` - the protocol foundation
2. **FIP-1** - how this FIP system works
3. **FIP-2** - Discord provider, the primary identity source
4. **FIP-3** - Profile, the privileged cross-community content type
5. **FIP-4** - Workshop Codes, the first non-profile content type
6. **FIP-5** - Context Registration, multi-tenant onboarding
7. **FIP-6** - Bot-Proxy Authentication, low-friction integration

## Categories

- **Core** - changes to `SPEC.md` itself
- **Auth** - provider adapters, authentication flows
- **Content** - content type definitions
- **Bot** - bot integration patterns
- **Process** - FIP process meta-changes

## Status definitions

- **Draft** - author actively writing, open to fundamental change
- **Review** - author considers complete, soliciting feedback (14-day minimum)
- **Accepted** - review closed, reference implementation exists, ready to build against
- **Final** - implemented in reference deployment, frozen
- **Withdrawn** - author retracted
- **Rejected** - community consensus against

See FIP-1 for full lifecycle details.

## Contributing a new FIP

1. Read FIP-1
2. Open a GitHub Discussion to gauge interest before drafting
3. Fork, copy the template from any existing FIP, write your draft
4. Open a PR. Editors will assign your FIP number and review template compliance
5. Once merged as `Draft`, iterate based on community feedback
6. When ready, move to `Review` (14-day minimum)
7. After Review with reference implementation, move to `Accepted`

## Editors

- Dercio (`@creedscode`) - initial editor