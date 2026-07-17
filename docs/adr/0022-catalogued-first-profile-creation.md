# ADR 0022: Catalogued first-profile creation

- Status: Accepted
- Date: 2026-07-17

## Context

The first-profile journey previously mixed protocol definitions, form widgets,
validation prose, draft persistence, host apply, and terminal navigation inside
the application composition root. Application validation returned localized
messages, so policy identity and presentation were inseparable. Several
terminal screens also treated `Esc` as a stack pop, exposing already-consumed
plans and confirmations after a write or host transaction.

This made the journey difficult to extend safely: every new protocol or outcome
expanded one large file, locale completeness could not be proven, and stale
navigation encouraged unsafe repetition after an unknown result.

## Decision

Place the complete journey in one deep `profile_creation` module. Its external
interface exports only the exact variant catalog, guided creation screen, and
saved-draft apply-confirmation screen used by the root application. Protocol
form composition, validation rendering, plan preview, persistence result,
confirmed apply, and every terminal screen remain implementation details.

Application validation exposes stable `ValidationIssueCode` identities with
optional structured context. The presentation adapter maps those identities and
all journey policy text through the validated interface copy catalog. Operator
values, typed diagnostics, and recovery instructions remain literal evidence
with markup disabled.

Treat revision conflict as a typed stale-plan rejection. Treat any other draft
write exception as an unknown desired-state result without disclosing the
exception. After apply confirmation, suppress duplicate confirmation and return
until a terminal result exists. Every successful, rejected, rolled-back,
operational-error, or unknown terminal screen offers one dashboard action, and
`Esc` invokes the same action: clear stale workflow screens and recompose the
dashboard from current state.

## Consequences

- The root application learns three names while the full journey remains local.
- Adding a protocol variant reuses one form/plan/persistence/apply policy instead
  of adding another parallel workflow.
- Locale completeness and placeholder compatibility are validated centrally.
- Tests continue through the Textual Pilot and existing `Manager`/
  `ProfileApplier` seams, so the module can be reorganized without changing the
  acceptance interface.
- Unknown persistence or host results require reinspection before retry and
  cannot navigate back to a consumed confirmation.

## Rejected alternatives

### Keep extending the root application module

Rejected because the composition root would continue accumulating unrelated
journey implementation and every maintenance change would have a larger blast
radius.

### Translate application validation messages directly

Rejected because localized application strings cannot provide stable policy
identity or prove catalog coverage.

### Pop one screen after terminal results

Rejected because the previous screen may represent a stale plan or already-used
confirmation and therefore is not a safe retry surface.
