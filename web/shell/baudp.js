// UDP for the web build: the engine's game socket rides a WebRTC data
// channel (unordered, no retransmits) to our gateway (web/gateway), which
// forwards each datagram as real UDP. Frames: [IPv4 x4][port BE x2][data].
// See src/ballistica/base/networking/web_udp.h.
// ?gate=<url> overrides the gateway. By Karan (@karan-suthar03), 2026-11-12.
(() => {
  const GATE = new URLSearchParams(location.search).get('gate')
    || 'https://play.karansuthar.me';
  const MAX_QUEUE = 256;
  // Python's own UDP sockets (the pre-join probe) go through emscripten's
  // socket layer, which speaks WebSocket; send them all to the gateway.
  Module.websocket = { url: GATE.replace(/^http/, 'ws') + '/ws', subprotocol: 'binary' };
  let pc = null, dc = null, connecting = false, queue = [], retryAt = 0;
  const say = t => (window.log ? window.log('out', `[udp] ${t}`) : console.log(t));

  async function connect() {
    // One link at a time: a channel that is still opening counts too
    // (otherwise every packet sent meanwhile opened another connection,
    // and the server saw one player arriving from several addresses).
    if (connecting || (dc && ['open', 'connecting'].includes(dc.readyState))) return;
    if (performance.now() < retryAt) return;
    connecting = true;
    try {
      if (pc) { try { pc.close(); } catch (e) {} }
      const myPc = new RTCPeerConnection();
      const myDc = myPc.createDataChannel('udp', { ordered: false, maxRetransmits: 0 });
      pc = myPc; dc = myDc;
      myDc.binaryType = 'arraybuffer';
      myDc.onopen = () => {
        say(`connected to ${GATE}`);
        for (const f of queue.splice(0)) myDc.send(f);
      };
      myDc.onmessage = e => deliver(new Uint8Array(e.data));
      myDc.onclose = () => { say('channel closed'); if (dc === myDc) dc = null; };
      myPc.onconnectionstatechange = () => {
        say(`connection ${myPc.connectionState}`);
        // 'disconnected' is usually a brief blip ICE recovers from.
        if (['failed', 'closed'].includes(myPc.connectionState)) {
          try { myPc.close(); } catch (e) {}
          if (dc === myDc) dc = null;
        }
      };
      await pc.setLocalDescription(await pc.createOffer());
      await new Promise(r => {
        if (pc.iceGatheringState === 'complete') return r();
        pc.onicegatheringstatechange = () => pc.iceGatheringState === 'complete' && r();
        setTimeout(r, 1000);
      });
      const resp = await fetch(`${GATE}/rtc`, {
        method: 'POST', mode: 'cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pc.localDescription),
      });
      if (!resp.ok) throw new Error(`gateway said ${resp.status}`);
      await pc.setRemoteDescription(await resp.json());
    } catch (e) {
      say(`connect failed: ${e.message || e}`);
      retryAt = performance.now() + 2000;
      try { pc && pc.close(); } catch (e2) {}
      dc = null;
    } finally {
      connecting = false;
    }
  }

  function deliver(frame) {
    if (frame.length <= 6 || !Module._ba_web_udp_recv) return;
    const p = Module._malloc(frame.length);
    if (!p) return;
    // HEAPU8 isn't exported on Module; the engine's global view is
    // re-created when memory grows, so read it at call time.
    (Module.HEAPU8 || self.HEAPU8).set(frame, p);
    Module._ba_web_udp_recv(p, frame.length);  // takes ownership
  }

  // Connect while the game loads, so joining doesn't wait on WebRTC
  // setup, and keep the link warm (the gateway drops idle clients).
  setTimeout(connect, 2000);
  setInterval(() => {
    if (dc && dc.readyState === 'open') dc.send(new Uint8Array(6));
    else connect();
  }, 20000);

  Module.baUdp = {
    send(frame) {
      if (dc && dc.readyState === 'open') {
        if (dc.bufferedAmount < 1 << 20) dc.send(frame);
        return;
      }
      if (queue.length < MAX_QUEUE) queue.push(frame);
      connect();
    },
  };
})();
