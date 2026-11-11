#!/usr/bin/env node
// Dump the call stack of every thread (page + all pthread workers) of the
// web build, using the Chrome DevTools Protocol against a headless Chrome.
//
// usage: node web/tools/stacks.mjs [url] [waitSeconds]
//   url defaults to http://localhost:8000/ ; waitSeconds to 15.
// Build with --profiling-funcs to get readable wasm function names.

import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const url = process.argv[2] ?? 'http://localhost:8000/';
const waitSecs = Number(process.argv[3] ?? 15);
const port = 9333;
const profile = mkdtempSync(join(tmpdir(), 'ba-stacks-'));

const chrome = spawn('google-chrome', [
  '--headless=new', `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`, '--no-first-run',
  '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
  '--window-size=1280,720', 'about:blank',
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function browserWsUrl() {
  for (let i = 0; i < 50; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/version`);
      return (await r.json()).webSocketDebuggerUrl;
    } catch { await sleep(200); }
  }
  throw new Error('chrome did not start');
}

const ws = new WebSocket(await browserWsUrl());
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let nextId = 1;
const pending = new Map();
const listeners = [];
ws.addEventListener('message', ev => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
  } else {
    for (const l of listeners) l(msg);
  }
});
function send(method, params = {}, sessionId) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params, sessionId }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

// Track every attached target (page + dedicated workers, recursively).
const sessions = new Map(); // sessionId -> {type, url}
listeners.push(async msg => {
  if (msg.method === 'Target.attachedToTarget') {
    const { sessionId, targetInfo } = msg.params;
    sessions.set(sessionId, { type: targetInfo.type, url: targetInfo.url });
    await send('Target.setAutoAttach',
      { autoAttach: true, waitForDebuggerOnStart: false, flatten: true },
      sessionId).catch(() => {});
    await send('Runtime.runIfWaitingForDebugger', {}, sessionId).catch(() => {});
  }
});

const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId: pageSession } = await send(
  'Target.attachToTarget', { targetId, flatten: true });
sessions.set(pageSession, { type: 'page', url });
// Auto-attach workers (and their nested workers, via the listener above).
await send('Target.setAutoAttach',
  { autoAttach: true, waitForDebuggerOnStart: false, flatten: true },
  pageSession);
await send('Page.enable', {}, pageSession);
await send('Page.navigate', { url }, pageSession);
console.error(`loaded ${url}; waiting ${waitSecs}s...`);
await sleep(waitSecs * 1000);

// Profile mode (BA_PROFILE=1): CPU-profile all threads at once for a few
// seconds and print each busy thread's hottest functions. Shows spinning
// threads, which Debugger.pause can't stop while in Atomics.wait anyway.
if (process.env.BA_PROFILE) {
  const ids = [...sessions.keys()];
  await Promise.all(ids.map(async sid => {
    await send('Profiler.enable', {}, sid).catch(() => {});
    await send('Profiler.setSamplingInterval', { interval: 500 }, sid).catch(() => {});
    await send('Profiler.start', {}, sid).catch(() => {});
  }));
  await sleep(4000);
  let i = 0;
  for (const sid of ids) {
    i++;
    let prof;
    try { ({ profile: prof } = await send('Profiler.stop', {}, sid)); } catch { continue; }
    const self = new Map();
    const byId = new Map(prof.nodes.map(nd => [nd.id, nd]));
    const counts = new Map();
    for (const s of prof.samples) counts.set(s, (counts.get(s) ?? 0) + 1);
    let total = 0;
    for (const [id, c] of counts) {
      const name = byId.get(id).callFrame.functionName || '(anon)';
      self.set(name, (self.get(name) ?? 0) + c);
      total += c;
    }
    const busy = [...self].filter(([nm]) => !/^\((idle|program|garbage collector)\)$/.test(nm));
    const busyCount = busy.reduce((a, [, c]) => a + c, 0);
    if (busyCount / Math.max(total, 1) < 0.02) continue; // idle thread
    console.log(`\n=== thread ${i} (${sessions.get(sid).type}) busy ${(100 * busyCount / total).toFixed(0)}%`);
    // Full call chain of the most-sampled leaf node (where it's stuck).
    const parent = new Map();
    for (const nd of prof.nodes) for (const ch of nd.children ?? []) parent.set(ch, nd.id);
    const [hotId] = [...counts].sort((a, b) => b[1] - a[1])[0];
    const chain = [];
    for (let id = hotId; id !== undefined; id = parent.get(id)) {
      const nm = byId.get(id).callFrame.functionName;
      if (nm && nm !== '(root)') chain.push(nm);
    }
    for (const nm of chain.slice(0, 30)) console.log(`    ${nm.slice(0, 140)}`);
  }
  ws.close(); chrome.kill(); rmSync(profile, { recursive: true, force: true });
  process.exit(0);
}

// Pause each thread in turn and print its stack.
let n = 0;
for (const [sid, info] of sessions) {
  n++;
  const paused = new Promise(resolve => {
    const l = msg => {
      if (msg.sessionId === sid && msg.method === 'Debugger.paused') {
        listeners.splice(listeners.indexOf(l), 1);
        resolve(msg.params.callFrames);
      }
    };
    listeners.push(l);
  });
  try {
    await send('Debugger.enable', {}, sid);
    await send('Debugger.pause', {}, sid);
    const frames = await Promise.race([paused, sleep(3000).then(() => null)]);
    console.log(`\n=== thread ${n} (${info.type}) ${frames ? '' : '[did not pause: idle/blocked in native wait]'}`);
    for (const f of (frames ?? []).slice(0, 25)) {
      console.log(`  ${f.functionName || '(anonymous)'}  ${f.url.split('/').pop()}:${f.location.lineNumber}`);
    }
    await send('Debugger.resume', {}, sid).catch(() => {});
  } catch (e) {
    console.log(`\n=== thread ${n} (${info.type}) error: ${e.message}`);
  }
}

ws.close();
chrome.kill();
rmSync(profile, { recursive: true, force: true });
