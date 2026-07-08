export const meta = {
  name: 'frugal-fable-fanout',
  description: 'Frugal Fable fan-out template: route independent slices to the cheapest sufficient model AT THE LOWEST SUFFICIENT EFFORT, verify, auto-escalate the ones that fail a signal, synthesize. COPY AND ADAPT per task — do not run blind.',
  phases: [
    { title: 'Work', detail: 'one agent per slice, model+effort chosen by slice, writes to scratch file' },
    { title: 'Verify', detail: 'Sonnet adversarial pass on high-stakes slices only' },
    { title: 'Escalate', detail: 'one bumped re-run for slices that failed a signal (flagged / low-confidence / stopped short)' },
    { title: 'Synthesize', detail: 'Fable (session model) integrates from files on demand' },
  ],
}

// ── How to use ──────────────────────────────────────────────────────────────
// Pass `args` as an array of slice specs. Fable (the orchestrator) fills these
// in after decomposing the task — that decomposition is the part worth Fable's
// tokens; this script just executes the fan-out cheaply.
//
//   args = [
//     { id: 'scan-auth',  tier: 'haiku',  effort: 'low',  highStakes: false,
//       prompt: 'Inventory every call site of `authToken` ...',
//       scratch: '.frugal-fable/scan-auth/findings.md' },
//     { id: 'patch-login', tier: 'sonnet', effort: 'medium', highStakes: true,
//       prompt: 'Apply this bounded change to src/login.ts ... run `npm test -- login`.',
//       scratch: '.frugal-fable/patch-login/report.md' },
//     ...
//   ]
//
// Each slice's `tier` (haiku | sonnet | opus) AND `effort` (low | medium | high)
// come from the STATIC routing table (the floor): score stakes/reversibility/
// ambiguity, the highest axis sets BOTH floors. DEFAULT LOW on both — omit
// `effort` and it defaults to 'low'. Keep architectural/one-way slices OUT of
// this fan-out — Fable owns those directly.
//
// HYBRID ROUTING: the table is the DEFAULT, not a cage. Fable may override a
// slice UPWARD (never below the table floor) by attaching an `override`:
//     { id: 'patch-parser', tier: 'sonnet', effort: 'medium', highStakes: true,
//       override: { tier: 'opus', reason: 'grammar is subtle; Sonnet historically
//                   under-handles left-recursion here (see memory/parser.md)' },
//       prompt: '...', scratch: '...' }
// The override is CLAMPED to raise-only and LOGGED with its reason, so every
// deviation from the static policy is auditable after the run. A downward
// override is ignored (clamped back to the floor) and noted. This is the
// "static defaults, Fable can override with logged justification" contract.
//
// You do NOT need to guess right the first time. Slices that fail a QUALITY
// signal (verify flags them, they return confidence:low, or they stop short) get
// ONE automatic bumped re-run — effort first, then tier — before synthesis.
// That's "react, don't predict" made mechanical: start cheap, let failure raise
// the level. (A classifier BLOCK is handled separately — see isClassifierBlock.)
// ─────────────────────────────────────────────────────────────────────────────

// Some backends deliver `args` as a JSON-encoded string rather than a parsed
// array (the Claude Code workflow harness stringifies it on this backend).
// Coerce before the array check, otherwise the fan-out sees zero slices.
if (typeof args === 'string') {
  try { args = JSON.parse(args) } catch (e) { args = [] }
}
const slices = Array.isArray(args) ? args : []
if (slices.length === 0) {
  return { error: 'No slices passed. args must be an array of { id, tier, effort?, highStakes, prompt, scratch, override? }.' }
}

const RESULT_SCHEMA = {
  type: 'object',
  required: ['path', 'summary', 'confidence'],
  properties: {
    path: { type: 'string', description: 'scratch file the agent wrote (NOT the full content)' },
    summary: { type: 'string', description: '<=3 lines: what was done / found' },
    confidence: { enum: ['high', 'medium', 'low'] },
    verifyPassed: { type: 'boolean', description: 'did the required build/tests pass?' },
    stoppedShort: { type: 'boolean', description: 'true if a stop condition was hit' },
  },
}
const VERDICT_SCHEMA = {
  type: 'object',
  required: ['sound', 'evidence'],
  properties: {
    sound: { type: 'boolean' },
    evidence: { type: 'string' },
    confidence: { enum: ['high', 'medium', 'low'] },
  },
}

// ── Ladders: the two escalation dimensions, cheapest → dearest ──
const EFFORT_LADDER = ['low', 'medium', 'high']
const TIER_LADDER = ['haiku', 'sonnet', 'opus']
const tierToModel = t => (TIER_LADDER.includes(t) ? t : 'haiku')
const normEffort = e => (EFFORT_LADDER.includes(e) ? e : 'low')

// ── Hybrid routing: static floor + raise-only Fable override ──────────────────
// The slice's {tier, effort} from the table is the FLOOR. If Fable attached an
// `override`, we take the max of floor and override on each axis independently
// (so a reason for raising tier doesn't accidentally lower effort, or vice
// versa), and log the deviation with its reason. Downward overrides are clamped
// away and flagged, so the static policy is never silently undercut.
const maxOn = (ladder, a, b) =>
  ladder[Math.max(ladder.indexOf(a), ladder.indexOf(b))]

const resolveLevel = (s) => {
  const floor = { tier: tierToModel(s.tier), effort: normEffort(s.effort) }
  if (!s.override) return { level: floor, routed: 'table' }
  const wantTier = tierToModel(s.override.tier || floor.tier)
  const wantEffort = normEffort(s.override.effort || floor.effort)
  const level = {
    tier: maxOn(TIER_LADDER, floor.tier, wantTier),
    effort: maxOn(EFFORT_LADDER, floor.effort, wantEffort),
  }
  const raised = level.tier !== floor.tier || level.effort !== floor.effort
  const clampedDown =
    (TIER_LADDER.indexOf(wantTier) < TIER_LADDER.indexOf(floor.tier)) ||
    (EFFORT_LADDER.indexOf(wantEffort) < EFFORT_LADDER.indexOf(floor.effort))
  if (raised) {
    log('  override[' + s.id + ']: ' + floor.tier + '/' + floor.effort + ' → ' +
        level.tier + '/' + level.effort + ' — ' + (s.override.reason || 'no reason given ⚠'))
  }
  if (clampedDown) {
    log('  override[' + s.id + ']: requested a level BELOW table floor — clamped to floor. ' +
        'Static policy is raise-only.')
  }
  if (raised && !s.override.reason) {
    log('  override[' + s.id + ']: ⚠ raised without a reason — hybrid contract wants a justification.')
  }
  return { level, routed: raised ? 'override-up' : (clampedDown ? 'override-clamped' : 'table'),
           overrideReason: raised ? (s.override.reason || null) : null }
}

// ── Classifier-block handling (Fable-on-API only) ────────────────────────────
// Per the Fable 5 system card (§1.5): on the Messages API the DEFAULT behavior
// when a safety classifier (cyber / bio-chem / distillation) fires is to BLOCK —
// the request returns a structured refusal category, NOT an automatic Opus
// fallback. (Auto-fallback is a client-app behavior, and even opt-in server-side
// fallback must be configured.) So a blocked slice is NOT a quality failure:
// bumping its effort just re-blocks. It needs a MODEL SWAP to a non-Fable model.
//
// This only bites if a delegated agent is served by Fable. Haiku/Sonnet/Opus
// subagents are not Fable, so in the standard routing table this path is dormant
// for workers — its real purpose is (a) safety if you route a slice to Fable, and
// (b) making the block case a named, testable branch instead of a silent null.
//
// Detection is best-effort and harness-dependent. `agent()` may surface a block
// as a thrown error, a null return, or a result object carrying a refusal flag —
// we check all three. Tune `isClassifierBlock` to whatever your runtime emits;
// the structured refusal category from the API is the reliable signal.
const OPUS_FALLBACK = 'opus' // most-recent Opus per card's designated fallback model

const isClassifierBlock = (errOrResult) => {
  if (!errOrResult) return false
  const blob = JSON.stringify(
    errOrResult instanceof Error
      ? { m: errOrResult.message, ...errOrResult }
      : errOrResult
  ).toLowerCase()
  // Structured refusal signals the card / API surface. Adjust to your runtime.
  return /refus|classifier|blocked|safeguard|"stop_reason":"?(refusal|safety)|policy_block/.test(blob)
}

// Bump policy: raise EFFORT first (cheaper lever, and the one that most often
// fixes an undershoot); only when effort is already maxed do we raise TIER.
// Returns the next {tier, effort} up the ladder, or null if already at the ceiling.
const bump = ({ tier, effort }) => {
  const ei = EFFORT_LADDER.indexOf(normEffort(effort))
  if (ei < EFFORT_LADDER.length - 1) return { tier: tierToModel(tier), effort: EFFORT_LADDER[ei + 1] }
  const ti = TIER_LADDER.indexOf(tierToModel(tier))
  if (ti < TIER_LADDER.length - 1) return { tier: TIER_LADDER[ti + 1], effort: 'medium' } // fresh tier restarts effort mid-ladder
  return null // already opus/high — escalating further means handing it back to Fable
}

const workPrompt = (s, level) =>
  '## Frugal Fable worker: ' + s.id + '\n\n' +
  s.prompt + '\n\n' +
  '## Effort floor: ' + level.effort + '\n' +
  'Do the work to a ' + level.effort + '-effort standard — enough to clear the bar, not more. ' +
  'Do not gold-plate, refactor beyond scope, or add handling for cases that cannot happen.\n\n' +
  '## Output protocol (MANDATORY)\n' +
  '1. Write your full findings / patch / logs to: `' + s.scratch + '` (create dirs as needed).\n' +
  '2. Return ONLY: the path, a <=3-line summary, and your confidence. Do NOT paste the full content back.\n' +
  '3. If your slice requires a build/test, run it and set verifyPassed accordingly.\n' +
  '4. Stop conditions: if the code does not match this prompt, a command fails after one retry, or you need\n' +
  '   out-of-scope files — stop, set stoppedShort=true, and report what blocked you. Do not improvise.\n\n' +
  'Structured output only.'

const verifyPrompt = item =>
  '## Adversarial verifier for slice: ' + item.id + '\n\n' +
  'A worker reported: "' + item.result.summary + '" (confidence ' + item.result.confidence + ').\n' +
  'Its output is at `' + item.result.path + '`. Read it.\n\n' +
  'Be skeptical. Does the file actually accomplish the slice objective below, with evidence?\n' +
  'Check the diff/claims against the stated scope. If it touched out-of-scope files, overreached,\n' +
  'or its tests do not actually cover the change, set sound=false.\n\n' +
  '## Slice objective\n' + item.prompt + '\n\nStructured output only.'

// A slice "failed a signal" — the trigger for a QUALITY bumped re-run — if any of:
//   verify flagged it unsound · it returned confidence:low · it stopped short ·
//   it had a build/test requirement that did not pass.
// A slice with no result (errored / unresolved block) is NOT a quality failure —
// it never produced work to judge, so it goes straight to Fable, not the bump path.
const failedSignal = item =>
  !!item.result && (
    (item.verdict && !item.verdict.sound) ||
    item.result.confidence === 'low' ||
    item.result.stoppedShort === true ||
    item.result.verifyPassed === false
  )

// Run one slice at a given {tier, effort}, then (if high-stakes) verify it.
// Returns the enriched item; does not decide QUALITY escalation — the caller does.
// EXCEPTION: a classifier block is handled inline (model swap to Opus, same
// effort, once) because it is orthogonal to quality — see isClassifierBlock above.
const runSlice = async (s, level, _blockRetried = false) => {
  let r
  try {
    r = await agent(workPrompt(s, level), {
      label: 'work:' + s.id + '@' + level.effort,
      phase: 'Work',
      model: tierToModel(level.tier),
      output_config: { effort: level.effort }, // documented Anthropic effort key (EFFORT_LADDER levels)
      schema: RESULT_SCHEMA,
    })
  } catch (err) {
    if (isClassifierBlock(err) && !_blockRetried && tierToModel(level.tier) !== OPUS_FALLBACK) {
      log('  ' + s.id + ': classifier BLOCK at ' + level.tier + ' → retrying on ' +
          OPUS_FALLBACK + ' @ ' + level.effort + ' (same effort; block is not a quality signal)')
      const item = await runSlice(s, { tier: OPUS_FALLBACK, effort: level.effort }, true)
      // Only claim a successful swap if Opus actually produced work. If Opus ALSO
      // blocked/errored, preserve that unresolved state so it lands in needsFable.
      if (item && item.result) return { ...item, blocked: 'swapped-to-opus', blockedFrom: level.tier }
      if (item) return { ...item, blockedFrom: level.tier } // unresolved on Opus too — keep inner's blocked:'unresolved'
      return { ...s, level: { tier: OPUS_FALLBACK, effort: level.effort }, result: null,
               blocked: 'unresolved', blockedFrom: level.tier, errored: true,
               errorMsg: 'blocked at ' + level.tier + ' and on Opus fallback' }
    }
    log('  ' + s.id + ': agent error' + (isClassifierBlock(err) ? ' (classifier block, no retry left)' : '') +
        ' — surfacing to Fable')
    return { ...s, level, result: null, blocked: isClassifierBlock(err) ? 'unresolved' : undefined,
             errored: true, errorMsg: (err && err.message) || String(err) }
  }
  // Some runtimes return a refusal as a result object rather than throwing.
  if (isClassifierBlock(r) && !_blockRetried && tierToModel(level.tier) !== OPUS_FALLBACK) {
    log('  ' + s.id + ': classifier BLOCK (result-form) at ' + level.tier + ' → retrying on ' +
        OPUS_FALLBACK + ' @ ' + level.effort)
    const item = await runSlice(s, { tier: OPUS_FALLBACK, effort: level.effort }, true)
    if (item && item.result) return { ...item, blocked: 'swapped-to-opus', blockedFrom: level.tier }
    if (item) return { ...item, blockedFrom: level.tier }
    return { ...s, level: { tier: OPUS_FALLBACK, effort: level.effort }, result: null,
             blocked: 'unresolved', blockedFrom: level.tier, errored: true,
             errorMsg: 'blocked at ' + level.tier + ' and on Opus fallback' }
  }
  if (!r) return null
  let item = { ...s, level, result: r }
  if (s.highStakes) {
    const v = await agent(verifyPrompt(item), {
      label: 'verify:' + s.id,
      phase: 'Verify',
      model: 'sonnet',
      output_config: { effort: 'low' }, // bounded skeptic pass — cheap by design
      schema: VERDICT_SCHEMA,
    })
    item = { ...item, verdict: v }
  }
  return item
}

// ── Work + verify, pipelined (no barrier): each slice runs at its resolved level (floor or logged override), verifies as it lands ──
phase('Work')
const first = await pipeline(
  slices,
  s => {
    const { level, routed, overrideReason } = resolveLevel(s)
    return runSlice(s, level).then(item =>
      item ? { ...item, routed, overrideReason } : item)
  },
  item => item // verify already folded into runSlice; pipeline stage kept for parity/backpressure
)

let results = first.filter(Boolean)

// ── Escalate: ONE bumped re-run for slices that tripped a signal. React, don't predict. ──
// This is the mechanical form of the skill's escalation rule: default low, and let a
// concrete failure — not a hunch — raise effort (then tier). Capped at one re-run per
// slice so a genuinely stuck slice surfaces to Fable instead of looping the budget away.
const needsBump = results.filter(failedSignal)
let escalated = []
if (needsBump.length) {
  phase('Escalate')
  log(needsBump.length + ' slice(s) tripped a signal — one bumped re-run each')
  escalated = (await pipeline(
    needsBump,
    item => {
      const next = bump(item.level)
      if (!next) {
        log('  ' + item.id + ': already at opus/high — leaving for Fable, no re-run')
        return { ...item, escalation: 'ceiling' } // Fable must own this one
      }
      log('  ' + item.id + ': ' + item.level.tier + '/' + item.level.effort + ' → ' + next.tier + '/' + next.effort)
      return runSlice(item, next).then(re => re ? { ...re, escalation: 'rerun', prevLevel: item.level } : { ...item, escalation: 'rerun-failed' })
    }
  )).filter(Boolean)

  // Replace escalated slices' results with their re-run outcome.
  const byId = new Map(escalated.map(e => [e.id, e]))
  results = results.map(r => byId.get(r.id) || r)
}

const flagged = results.filter(r => r.verdict && !r.verdict.sound)
const stopped = results.filter(r => r.result && r.result.stoppedShort)
const atCeiling = results.filter(r => r.escalation === 'ceiling')
// Slices that produced no work: an unresolved classifier block, or a hard error.
// These never entered the quality path — they go straight to Fable.
const needsFable = results.filter(r => !r.result || r.blocked === 'unresolved')
const swappedToOpus = results.filter(r => r.blocked === 'swapped-to-opus')
log(results.length + ' slices done · ' + flagged.length + ' still flagged · ' +
    stopped.length + ' still stopped short · ' + atCeiling.length + ' hit ceiling · ' +
    swappedToOpus.length + ' block→Opus · ' + needsFable.length + ' unresolved (need Fable)')

// ── Synthesize: inherits the session model (Fable). This is the call worth full quality. ──
// Fable reads the scratch files ON DEMAND — the manifest carries only paths+summaries+level,
// keeping the context firewall intact. Pull a file in only when integrating it.
phase('Synthesize')
const manifest = results.map(r =>
  '- [' + r.id + '] ' + r.level.tier + '/' + r.level.effort +
  (r.routed === 'override-up' ? ' (override↑: ' + (r.overrideReason || 'no reason') + ')' : '') +
  (r.escalation === 'rerun' ? ' (escalated from ' + r.prevLevel.tier + '/' + r.prevLevel.effort + ')' : '') +
  (r.escalation === 'ceiling' ? ' (AT CEILING — Fable must own)' : '') +
  (r.blocked === 'swapped-to-opus' ? ' (classifier-blocked at ' + r.blockedFrom + ' → ran on Opus)' : '') +
  (r.blocked === 'unresolved' ? ' (CLASSIFIER-BLOCKED, unresolved — Fable must own)' : '') +
  (r.errored && r.blocked !== 'unresolved' ? ' (ERRORED — Fable must own)' : '') +
  (r.result ? ' · confidence=' + r.result.confidence : ' · NO RESULT') +
  (r.verdict ? ' · verify=' + (r.verdict.sound ? 'sound' : 'FLAGGED: ' + r.verdict.evidence) : '') +
  (r.result && r.result.stoppedShort ? ' · STOPPED SHORT' : '') +
  (r.result ? '\n  file: ' + r.result.path + '\n  summary: ' + r.result.summary
            : '\n  (no output produced — ' + (r.errorMsg || 'blocked') + ')')
).join('\n')

return {
  task: 'frugal-fable fan-out',
  sliceCount: slices.length,
  completed: results.filter(r => r.result).length,
  escalatedCount: escalated.length,
  swappedToOpus: swappedToOpus.map(r => ({ id: r.id, blockedFrom: r.blockedFrom, file: r.result && r.result.path })),
  flagged: flagged.map(r => ({ id: r.id, why: r.verdict.evidence, file: r.result && r.result.path })),
  stoppedShort: stopped.map(r => ({ id: r.id, file: r.result.path })),
  atCeiling: atCeiling.map(r => ({ id: r.id, file: r.result && r.result.path })),
  needsFable: needsFable.map(r => ({ id: r.id, reason: r.blocked === 'unresolved' ? 'classifier-block' : 'error', detail: r.errorMsg })),
  manifest,
  next: 'Fable: read flagged + at-ceiling + needsFable + high-stakes files from the manifest, integrate, run final review. ' +
        'At-ceiling slices exhausted the cheap ladder — own them directly. ' +
        'needsFable slices produced NO output (classifier block or error) — own them directly; do not treat as done. ' +
        'Do NOT trust summaries for high-impact decisions — reopen the file.',
}
