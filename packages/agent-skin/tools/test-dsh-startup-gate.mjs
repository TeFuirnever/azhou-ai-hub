// Exhaustive interleaving model check for extension/hosts/dsh-startup-gate.js.
//
// Runs the real, unmodified gate source inside a stubbed browser environment
// (mirroring tools/dsh-startup-gate.unit.test.mjs) and enumerates every
// interleaving of renderer API calls, watchdog/reveal timers, animation
// frames, pagehide, and duplicate injection, under a virtual clock. The gate
// closure cannot be rolled back, so exploration is replay-based: every node
// of the schedule tree replays its full event prefix from a fresh
// environment, checking the invariants after each indivisible event. Every
// schedule must satisfy the gate's promises; a violation prints the
// counterexample trace in the gate's own terms.
//
// Usage:
//   node tools/test-dsh-startup-gate.mjs [--gate <path>] [--variant <id>]
//        [--max-states <n>]
//
// Variants: normal (rAF delivered), dead-rAF (frames never fire, timers do),
// no-rAF (requestAnimationFrame absent, setTimeout fallback used).
// Exit 0 = all invariants hold; exit 1 = counterexample found; exit 2 = usage
// or checker error.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Script, runInNewContext } from 'node:vm';
import { fileURLToPath } from 'node:url';

const DEFAULT_GATE = fileURLToPath(new URL('../extension/hosts/dsh-startup-gate.js', import.meta.url));
const INSTALL_DEADLINE_MS = 8_000;
const CLAIM_DEADLINE_MS = 12_000;
const REVEAL_DEADLINE_MS = 250;
const MAX_STATES_DEFAULT = 200_000;
const ACTIVE_PHASES = new Set(['waiting', 'claimed', 'revealing']);
const TERMINAL_PHASES = new Set(['released', 'expired']);

function parseArgs(argv) {
  const options = { gate: DEFAULT_GATE, variants: ['normal', 'dead-rAF', 'no-rAF'], maxStates: MAX_STATES_DEFAULT };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (flag === '--gate') options.gate = argv[++index];
    else if (flag === '--variant') options.variants = [argv[++index]];
    else if (flag === '--max-states') options.maxStates = Number(argv[++index]);
    else throw new Error(`unknown flag: ${flag}`);
  }
  const known = new Set(['normal', 'dead-rAF', 'no-rAF']);
  if (!options.gate || options.variants.some((variant) => !known.has(variant))) {
    throw new Error('usage: test-dsh-startup-gate.mjs [--gate <path>] [--variant normal|dead-rAF|no-rAF]');
  }
  return options;
}

// Stub browser environment. Same shape and semantics as the unit-test stub so
// the gate installs cleanly; timers carry absolute virtual deadlines so the
// scheduler can reason about watchdog ordering. frameMode:
//   normal  — requestAnimationFrame exists and its callbacks are deliverable
//   dead-rAF— requestAnimationFrame exists but frames are never delivered
//   no-rAF  — requestAnimationFrame is absent; ready() uses setTimeout(0)
function makeEnvironment(frameMode) {
  let now = 0;
  const timers = new Map();
  const frames = new Map();
  const pagehideListeners = new Set();
  let nextId = 1;
  const root = {
    children: [],
    appendChild(element) {
      element.parentNode?.removeChild?.(element);
      element.parentNode = this;
      this.children.push(element);
      return element;
    },
    removeChild(element) {
      const index = this.children.indexOf(element);
      if (index >= 0) this.children.splice(index, 1);
      element.parentNode = null;
      return element;
    },
  };
  const body = { hasAttribute() { return false; } };
  const document = {
    hidden: false,
    visibilityState: 'visible',
    body,
    documentElement: root,
    elementFromPoint() { return root.children.at(-1); },
    createElement(tag) {
      assert.equal(tag, 'div');
      return {
        style: {},
        attributes: new Map(),
        setAttribute(name, value) { this.attributes.set(name, value); },
        getBoundingClientRect() {
          return { left: 0, top: 0, right: 800, bottom: 600, width: 800, height: 600 };
        },
        remove() { this.parentNode?.removeChild(this); },
      };
    },
  };
  const host = {
    document,
    innerWidth: 800,
    innerHeight: 600,
    CSS: { supports(property, value) {
      return property === 'color'
        && /^(?:#[\da-f]{3,8}|(?:rgb|rgba|hsl|hsla|color)\([^)]*\)|transparent|currentcolor)$/i
          .test(String(value).trim());
    } },
    getComputedStyle(element) {
      const background = element?.style?.backgroundColor;
      const hex = /^#([\da-f]{6})$/i.exec(background ?? '');
      const backgroundColor = background === '#f8f8f8' ? 'rgb(248, 248, 248)'
        : background === '#10121c' ? 'rgba(16, 18, 28, 1)'
          : hex ? `rgb(${Number.parseInt(hex[1].slice(0, 2), 16)}, ${Number.parseInt(hex[1].slice(2, 4), 16)}, ${Number.parseInt(hex[1].slice(4, 6), 16)})`
            : background === 'transparent' ? 'rgba(0, 0, 0, 0)'
              : /^rgba?\(/i.test(background ?? '') ? background : 'rgba(16, 18, 28, 1)';
      return {
        position: element?.style?.position,
        display: element?.style?.display || 'block',
        visibility: element?.style?.visibility || 'visible',
        pointerEvents: element?.style?.pointerEvents,
        zIndex: element?.style?.zIndex,
        opacity: '1',
        backgroundColor,
        colorScheme: 'dark',
        getPropertyValue(name) {
          if (element === body) return '';
          return name === 'color-scheme' ? 'dark' : '';
        },
      };
    },
    setTimeout(callback, delay) {
      const id = nextId++;
      timers.set(id, { callback, deadline: now + delay });
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
    ...(frameMode !== 'no-rAF' ? {
      requestAnimationFrame(callback) {
        const id = nextId++;
        frames.set(id, callback);
        return id;
      },
      cancelAnimationFrame(id) { frames.delete(id); },
    } : {}),
    addEventListener(type, callback) { pagehideListeners.add(callback); },
    removeEventListener(type, callback) { pagehideListeners.delete(callback); },
    matchMedia(query) {
      assert.equal(query, '(prefers-color-scheme: dark)');
      return { matches: true };
    },
  };
  return {
    host, root, timers, frames, pagehideListeners,
    now: () => now,
    advanceTo(time) { now = time; },
  };
}

const ACTIONS = [
  { id: 'claim', budget: 2 },
  { id: 'ready', budget: 2 },
  { id: 'release', budget: 2 },
  { id: 'listen', budget: 2 },
  { id: 'cancel', budget: 2 },
  { id: 'pagehide', budget: 1 },
  { id: 'rerun', budget: 1 },
];

// Model-side bookkeeping for one replay. The gate closure is opaque; the
// model derives everything it asserts from observable state plus its own
// records of API results and listener callbacks.
function freshModel(frameMode) {
  return {
    used: Object.fromEntries(ACTIONS.map((action) => [action.id, 0])),
    listeners: [],
    cancels: [],
    seenReleased: false,
    seenExpired: false,
    hardDeadline: INSTALL_DEADLINE_MS,
  };
}

function digest(env, model) {
  return JSON.stringify({
    now: env.now(),
    timers: [...env.timers.values()].map((entry) => entry.deadline).sort((a, b) => a - b),
    frames: env.frames.size,
    children: env.root.children.length,
    used: model.used,
    listeners: model.listeners.map((listener) => ({ fired: listener.fired, cancelled: listener.cancelled, regPhase: listener.regPhase, owed: listener.owed })),
    seenReleased: model.seenReleased,
    seenExpired: model.seenExpired,
    hardDeadline: model.hardDeadline,
  });
}

function checkInvariants(env, model, sink, frameMode) {
  const gate = env.host.__azhouDshStartupGate;
  const status = gate.status();
  const children = env.root.children.length;
  const now = env.now();
  const attached = children === 1;
  const fail = (message) => sink(message);

  // P1: the cover is attached exactly while the gate holds an active phase,
  // and there is never more than one cover.
  if (children > 1) fail('more than one cover element is attached at once');
  if (attached !== ACTIVE_PHASES.has(status)) {
    fail(`cover attached=${attached} while phase is '${status}': the cover must stay visible through every active phase and vanish the moment the gate leaves one`);
  }

  // P2: released and expired are absorbing; a stale callback must not flip a
  // finished gate into the other terminal phase.
  if (model.seenReleased && status !== 'released') fail(`phase left 'released' into '${status}'`);
  if (model.seenExpired && status !== 'expired') fail(`phase left 'expired' into '${status}'`);

  // P3: while the cover is up, a watchdog timer is armed at the tracked hard
  // deadline and that deadline has not been crossed; the cover can never
  // outlive its own watchdog.
  const timerDeadlines = [...env.timers.values()].map((entry) => entry.deadline);
  if (attached) {
    if (!timerDeadlines.includes(model.hardDeadline)) {
      fail(`cover attached without its watchdog armed at t=${model.hardDeadline} (pending: ${timerDeadlines.join(', ') || 'none'})`);
    }
    if (now > model.hardDeadline) {
      fail(`cover still attached at t=${now} after its hard deadline t=${model.hardDeadline}: cold start would hang on an opaque cover`);
    }
  }

  // P6: bounded concurrent timers/frames, and a finished gate leaves no
  // zombie timers, frames, covers, or pagehide listeners behind. In the
  // no-rAF environment the reveal fallback legitimately coexists with the
  // watchdog.
  const maxTimers = frameMode === 'no-rAF' ? 2 : 1;
  if (timerDeadlines.length > maxTimers) fail(`${timerDeadlines.length} timers pending at once (limit ${maxTimers})`);
  if (env.frames.size > 1) fail(`${env.frames.size} animation frames pending at once`);
  if (TERMINAL_PHASES.has(status) && (timerDeadlines.length > 0 || env.frames.size > 0 || children > 0 || env.pagehideListeners.size > 0)) {
    fail(`terminal phase '${status}' left ${timerDeadlines.length} timers, ${env.frames.size} frames, ${children} covers, ${env.pagehideListeners.size} pagehide listeners behind`);
  }

  // P5: listener semantics — a listener fires exactly once iff expiry
  // happened while it was registered and not yet cancelled. `owed` is set
  // once, at the moment the gate first enters 'expired', for every listener
  // then registered in an active phase and not cancelled; registration in
  // the 'expired' phase owes its fire immediately. The expectation is
  // derived independently of `fired`, so a premature or spurious
  // notification is a violation, not evidence of legitimacy.
  for (const listener of model.listeners) {
    if (listener.fired > 1) fail(`an expiry listener fired ${listener.fired} times`);
    const expected = listener.owed ? 1 : 0;
    if (listener.fired !== expected) {
      fail(`expiry listener (registered in '${listener.regPhase}'${listener.cancelled ? ', cancelled' : ''}) fired ${listener.fired} times, expected ${expected}`);
    }
  }
}

// One indivisible event. Returns its trace label; records an apiFailure via
// out-param so the violation trace includes the event itself.
function applyEvent(env, model, event, source, frameMode, sink) {
  const gate = env.host.__azhouDshStartupGate;
  let label = '';
  let apiFailure = null;
  if (event.type === 'claim' || event.type === 'ready' || event.type === 'release') {
    const before = gate.status();
    const result = gate[event.type]();
    const expected = event.type === 'claim' ? before === 'waiting'
      : event.type === 'ready' ? before === 'claimed'
        : !TERMINAL_PHASES.has(before);
    if (result !== expected) {
      apiFailure = `${event.type}() returned ${result} from phase '${before}': ${event.type} must succeed exactly on its legal phase`;
    }
    const expectedPost = event.type === 'claim' ? 'claimed'
      : event.type === 'ready' ? 'revealing'
        : 'expired';
    if (result === true) {
      if (gate.status() !== expectedPost) {
        apiFailure = `${event.type}() returned true from phase '${before}' but the phase is now '${gate.status()}': a successful ${event.type} must enter '${expectedPost}'`;
      }
      model.hardDeadline = env.now()
        + (event.type === 'claim' ? CLAIM_DEADLINE_MS : REVEAL_DEADLINE_MS);
    } else if (gate.status() !== before) {
      apiFailure = `${event.type}() returned false from phase '${before}' but the phase is now '${gate.status()}': a rejected ${event.type} must preserve the phase`;
    }
    model.used[event.type] += 1;
    label = `${event.type}() -> ${result} (phase ${before} -> ${gate.status()})`;
  } else if (event.type === 'listen') {
    const before = gate.status();
    const listener = { fired: 0, cancelled: false, regPhase: before, owed: before === 'expired' };
    const index = model.listeners.length;
    model.cancels.push(gate.onExpire(() => { listener.fired += 1; }));
    model.listeners.push(listener);
    model.used.listen += 1;
    label = `onExpire(listener #${index}) registered in phase '${before}'`;
  } else if (event.type === 'cancel') {
    const target = model.listeners.findIndex((listener) => !listener.cancelled);
    model.cancels[target]();
    model.listeners[target].cancelled = true;
    model.used.cancel += 1;
    label = `cancel(listener #${target})`;
  } else if (event.type === 'pagehide') {
    const before = gate.status();
    for (const callback of [...env.pagehideListeners]) callback();
    env.pagehideListeners.clear();
    if (ACTIVE_PHASES.has(before) && gate.status() !== 'expired') {
      apiFailure = `pagehide fired from phase '${before}' but the phase is now '${gate.status()}': pagehide must expire an active gate`;
    }
    model.used.pagehide += 1;
    label = `pagehide fires (cover ${env.root.children.length === 0 ? 'removed' : 'still attached'})`;
  } else if (event.type === 'rerun') {
    const before = env.host.__azhouDshStartupGate;
    const childrenBefore = env.root.children.length;
    runInNewContext(source, env.host, { filename: 'dsh-startup-gate.js' });
    if (env.host.__azhouDshStartupGate !== before) {
      apiFailure = 'duplicate injection replaced the published gate object';
    }
    if (env.root.children.length !== childrenBefore) {
      apiFailure ??= `duplicate injection changed the cover count from ${childrenBefore} to ${env.root.children.length}`;
    }
    model.used.rerun += 1;
    label = 'duplicate IIFE injection';
  } else if (event.type === 'frame') {
    const before = gate.status();
    const [id, callback] = env.frames.entries().next().value;
    env.frames.delete(id);
    callback();
    if (gate.status() !== 'released') {
      apiFailure = `animation frame delivered from phase '${before}' but the phase is now '${gate.status()}': a delivered reveal frame must release the gate`;
    }
    label = 'animation frame delivered (reveal callback)';
  } else if (event.type === 'fireTimers') {
    const before = gate.status();
    const parts = [];
    for (const id of event.ids) {
      const entry = env.timers.get(id);
      env.timers.delete(id);
      entry.callback();
      if (entry.deadline === model.hardDeadline) {
        if (ACTIVE_PHASES.has(before) && gate.status() !== 'expired') {
          apiFailure ??= `watchdog at t=${entry.deadline} fired from phase '${before}' but the phase is now '${gate.status()}': a watchdog must expire an active gate`;
        }
      } else if (gate.status() !== 'released') {
        apiFailure ??= `reveal fallback timer at t=${entry.deadline} fired from phase '${before}' but the phase is now '${gate.status()}': a delivered reveal callback must release the gate`;
      }
      parts.push(`timer at t=${entry.deadline} fires`);
    }
    label = parts.join(', then ');
  } else if (event.type === 'advance') {
    env.advanceTo(event.to);
    label = `time advances to t=${event.to}`;
  } else {
    throw new Error(`unknown event type: ${event.type}`);
  }
  return { label, apiFailure };
}

function successorEvents(env, model, frameMode) {
  const successors = [];
  for (const action of ACTIONS) {
    if (model.used[action.id] >= action.budget) continue;
    if (action.id === 'cancel' && !model.listeners.some((listener) => !listener.cancelled)) continue;
    successors.push({ type: action.id });
  }
  if (frameMode !== 'dead-rAF' && env.frames.size > 0) successors.push({ type: 'frame' });
  const due = [...env.timers].filter(([, entry]) => entry.deadline <= env.now());
  if (due.length === 1) {
    successors.push({ type: 'fireTimers', ids: [due[0][0]] });
  } else if (due.length === 2) {
    successors.push({ type: 'fireTimers', ids: [due[0][0], due[1][0]] });
    successors.push({ type: 'fireTimers', ids: [due[1][0], due[0][0]] });
  } else if (due.length > 2) {
    throw new Error('more than 2 timers due at once; widen the permutation table');
  }
  if (due.length === 0 && env.timers.size > 0) {
    successors.push({ type: 'advance', to: Math.min(...[...env.timers.values()].map((entry) => entry.deadline)) });
  }
  return successors;
}

// Replay-based DFS: each node replays its full event prefix in a fresh
// environment, checking the invariants after every event along the way, then
// expands one step per successor. Digests deduplicate expansion.
function explore(script, source, frameMode, maxStates) {
  const visited = new Set();
  let violation = null;
  const sink = (message, trace) => {
    violation ??= { message, trace };
  };

  // Returns the live environment/model at the end of the sequence, or null
  // when this prefix is done (violation recorded, or already explored).
  const replay = (events) => {
    const env = makeEnvironment(frameMode);
    const model = freshModel(frameMode);
    const trace = [];
    script.runInNewContext(env.host);
    if (!env.host.__azhouDshStartupGate) {
      throw new Error('gate did not publish in the stub environment; the checker requires a passing install');
    }
    trace.push('t=0 gate installed, cover attached, 8s watchdog armed');
    checkInvariants(env, model, (message) => sink(message, [...trace]), frameMode);
    if (violation) return null;
    visited.add(digest(env, model));
    for (const event of events) {
      const { label, apiFailure } = applyEvent(env, model, event, source, frameMode, sink);
      trace.push(`t=${env.now()} ${label}`);
      if (apiFailure) sink(apiFailure, [...trace]);
      const statusNow = env.host.__azhouDshStartupGate.status();
      if (statusNow === 'released') model.seenReleased = true;
      if (statusNow === 'expired' && !model.seenExpired) {
        // The expiry transition: every listener registered in an active
        // phase and not yet cancelled is owed exactly one notification.
        for (const listener of model.listeners) {
          if (!listener.cancelled && ACTIVE_PHASES.has(listener.regPhase)) listener.owed = true;
        }
      }
      if (statusNow === 'expired') model.seenExpired = true;
      checkInvariants(env, model, (message) => sink(message, [...trace]), frameMode);
      if (violation) return null;
    }
    const key = digest(env, model);
    if (visited.has(key) && events.length > 0) return null; // subtree already explored
    visited.add(key);
    return { env, model };
  };

  const dfs = (events) => {
    const end = replay(events);
    if (end === null) return;
    if (violation) return;
    if (visited.size > maxStates) throw new Error(`state space exceeded --max-states=${maxStates}`);
    for (const event of successorEvents(end.env, end.model, frameMode)) {
      dfs([...events, event]);
    }
  };

  dfs([]);
  return { visited: visited.size, violation };
}

function runVariant(script, source, frameMode, maxStates) {
  return explore(script, source, frameMode, maxStates);
}

function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(String(error.message ?? error));
    process.exit(2);
  }
  const source = readFileSync(options.gate, 'utf8');
  const script = new Script(source, { filename: 'dsh-startup-gate.js' });
  let totalStates = 0;
  let failed = false;
  for (const frameMode of options.variants) {
    let result;
    try {
      result = runVariant(script, source, frameMode, options.maxStates);
    } catch (error) {
      console.error(`[${frameMode}] checker error: ${error.message}`);
      process.exit(2);
    }
    totalStates += result.visited;
    if (result.violation) {
      failed = true;
      console.error(`\n[${frameMode}] INVARIANT VIOLATION: ${result.violation.message}`);
      console.error('Counterexample schedule:');
      for (const line of result.violation.trace) console.error(`  ${line}`);
    } else {
      console.log(`[${frameMode}] ok — ${result.visited} states explored, all invariants hold`);
    }
  }
  if (failed) process.exit(1);
  console.log(`all variants passed (${totalStates} states total, gate source: ${options.gate})`);
}

main();
