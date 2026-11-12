// UDP for the web build: the engine's game socket rides a WebRTC data
// channel (unordered, no retransmits) to our gateway (web/gateway), which
// forwards each datagram as real UDP. Frames: [IPv4 x4][port BE x2][data].
// See src/ballistica/base/networking/web_udp.h.
// ?gate=<url> overrides the gateway. By Karan (@karan-suthar03), 2026-11-12.
(() => {
  const GATE = new URLSearchParams(location.search).get('gate')
    || 'https://play.karansuthar.me';
  const MAX_QUEUE = 256;
  let pc = null, dc = null, connecting = false, queue = [], retryAt = 0;
  const say = t => (window.log ? window.log('out', `[udp] ${t}`) : console.log(t));

  async function connect() {
    if (connecting || (dc && dc.readyState === 'open')) return;
    if (performance.now() < retryAt) return;
    connecting = true;
    try {
      pc = new RTCPeerConnection();
      dc = pc.createDataChannel('udp', { ordered: false, maxRetransmits: 0 });
      dc.binaryType = 'arraybuffer';
      dc.onopen = () => {
        say(`connected to ${GATE}`);
        for (const f of queue.splice(0)) dc.send(f);
      };
      dc.onmessage = e => deliver(new Uint8Array(e.data));
      dc.onclose = () => { say('channel closed'); dc = null; };
      pc.onconnectionstatechange = () => {
        if (['failed', 'disconnected', 'closed'].includes(pc.connectionState)) {
          say(`connection ${pc.connectionState}`);
          try { pc.close(); } catch (e) {}
          dc = null;
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
    Module.HEAPU8.set(frame, p);
    Module._ba_web_udp_recv(p, frame.length);  // takes ownership
  }

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
