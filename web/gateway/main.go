// bsgate: WebRTC <-> UDP gateway for BombSquad web clients.
//
// Browsers can't send raw UDP, so each web client opens one WebRTC data
// channel (unordered, no retransmits: UDP semantics) to us. Frames are
// [4-byte IPv4][2-byte port, big endian][payload]: the destination for
// frames from the browser, the source for frames to it. We forward each
// one as a real UDP datagram from a socket owned by that client, so game
// servers see every web player as a separate address.
//
// Only allowlisted destinations are reachable (our own game servers), so
// this is not an open relay. Our own public IP is mapped to localhost.
//
// By Karan (@karan-suthar03), 2026-11-12.
package main

import (
	"encoding/binary"
	"encoding/json"
	"flag"
	"io"
	"log"
	"net"
	"net/http"
	"net/netip"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/coder/websocket"
	"github.com/pion/webrtc/v4"
)

var (
	listen   = flag.String("listen", ":8443", "https listen address (signaling)")
	certFile = flag.String("cert", "", "TLS cert (empty: plain http)")
	keyFile  = flag.String("key", "", "TLS key")
	rtcPort  = flag.Int("rtc-port", 3478, "single UDP port for all WebRTC traffic")
	publicIP = flag.String("public-ip", "130.210.6.57", "our public IP (ICE + local mapping)")
	allow    = flag.String("allow", "127.0.0.1:43210", "comma-separated allowed UDP destinations (ip:port)")
	origins  = flag.String("origins", "https://bombsquad.karansuthar.me,http://localhost:8000", "allowed page origins")
	maxPeers = flag.Int("max-peers", 64, "max simultaneous web clients")
	idle     = flag.Duration("idle", 60*time.Second, "close a client after this long with no traffic")
)

var (
	api      *webrtc.API
	allowed  = map[netip.AddrPort]bool{}
	ourAddr  netip.Addr
	loopback = netip.MustParseAddr("127.0.0.1")
	peers    atomic.Int32
)

// client is one browser: its data channel and its own UDP socket.
type client struct {
	pc       *webrtc.PeerConnection
	udp      *net.UDPConn
	lastSeen atomic.Int64
	once     sync.Once
}

func (c *client) close() {
	c.once.Do(func() {
		peers.Add(-1)
		c.pc.Close()
		if c.udp != nil {
			c.udp.Close()
		}
	})
}

// fromBrowser forwards one frame to its UDP destination.
func (c *client) fromBrowser(frame []byte) {
	if len(frame) <= 6 {
		return
	}
	c.lastSeen.Store(time.Now().Unix())
	ip := netip.AddrFrom4([4]byte(frame[:4]))
	port := binary.BigEndian.Uint16(frame[4:6])
	if ip == ourAddr {
		ip = loopback
	}
	dst := netip.AddrPortFrom(ip, port)
	if !allowed[dst] {
		return
	}
	c.udp.WriteToUDPAddrPort(frame[6:], dst)
}

// toBrowser pumps UDP replies back over the data channel.
func (c *client) toBrowser(dc *webrtc.DataChannel) {
	buf := make([]byte, 6+65536)
	for {
		n, src, err := c.udp.ReadFromUDPAddrPort(buf[6:])
		if err != nil {
			return
		}
		ip := src.Addr().Unmap()
		if ip == loopback {
			ip = ourAddr // show the address the client asked for
		}
		if !ip.Is4() {
			continue
		}
		a := ip.As4()
		copy(buf[:4], a[:])
		binary.BigEndian.PutUint16(buf[4:6], src.Port())
		c.lastSeen.Store(time.Now().Unix())
		if dc.Send(buf[:6+n]) != nil {
			return
		}
	}
}

func cors(w http.ResponseWriter, r *http.Request) bool {
	o := r.Header.Get("Origin")
	for _, a := range strings.Split(*origins, ",") {
		if o == a {
			w.Header().Set("Access-Control-Allow-Origin", o)
			w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
			w.Header().Set("Cross-Origin-Resource-Policy", "cross-origin")
			w.Header().Set("Vary", "Origin")
			return true
		}
	}
	return o == "" // non-browser tools
}

func handleRTC(w http.ResponseWriter, r *http.Request) {
	if !cors(w, r) {
		http.Error(w, "origin not allowed", http.StatusForbidden)
		return
	}
	if r.Method == http.MethodOptions {
		return
	}
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	var offer webrtc.SessionDescription
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&offer); err != nil {
		http.Error(w, "bad offer", http.StatusBadRequest)
		return
	}
	if int(peers.Add(1)) > *maxPeers {
		peers.Add(-1)
		http.Error(w, "gateway full", http.StatusServiceUnavailable)
		return
	}
	pc, err := api.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		peers.Add(-1)
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	c := &client{pc: pc}
	c.lastSeen.Store(time.Now().Unix())
	if c.udp, err = net.ListenUDP("udp4", &net.UDPAddr{}); err != nil {
		c.close()
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	pc.OnConnectionStateChange(func(s webrtc.PeerConnectionState) {
		switch s {
		case webrtc.PeerConnectionStateFailed, webrtc.PeerConnectionStateClosed,
			webrtc.PeerConnectionStateDisconnected:
			c.close()
		}
	})
	pc.OnDataChannel(func(dc *webrtc.DataChannel) {
		dc.OnOpen(func() { go c.toBrowser(dc) })
		dc.OnMessage(func(m webrtc.DataChannelMessage) { c.fromBrowser(m.Data) })
		dc.OnClose(c.close)
	})
	// Idle reaper.
	go func() {
		t := time.NewTicker(5 * time.Second)
		defer t.Stop()
		for range t.C {
			if time.Since(time.Unix(c.lastSeen.Load(), 0)) > *idle {
				c.close()
			}
			if pc.ConnectionState() == webrtc.PeerConnectionStateClosed {
				return
			}
		}
	}()

	if err := pc.SetRemoteDescription(offer); err != nil {
		c.close()
		http.Error(w, "bad offer", http.StatusBadRequest)
		return
	}
	answer, err := pc.CreateAnswer(nil)
	if err != nil {
		c.close()
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	gathered := webrtc.GatheringCompletePromise(pc)
	if err := pc.SetLocalDescription(answer); err != nil {
		c.close()
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	<-gathered
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(pc.LocalDescription())
}

// handleWS serves the web build's emscripten socket layer, which turns
// Python UDP sockets (the pre-join requirements probe) into WebSockets.
// The shell points every such socket at this one URL, so all datagrams go
// to our game server (the first -allow entry). Emscripten first sends a
// 'port' message ([ff ff ff ff 'p' 'o' 'r' 't' hi lo]); we skip it.
func handleWS(w http.ResponseWriter, r *http.Request) {
	ws, err := websocket.Accept(w, r, &websocket.AcceptOptions{
		Subprotocols:    []string{"binary"},
		OriginPatterns:  originHosts(),
		CompressionMode: websocket.CompressionDisabled,
	})
	if err != nil {
		return
	}
	defer ws.CloseNow()
	if int(peers.Add(1)) > *maxPeers {
		peers.Add(-1)
		return
	}
	defer peers.Add(-1)
	udp, err := net.ListenUDP("udp4", &net.UDPAddr{})
	if err != nil {
		return
	}
	defer udp.Close()
	ctx := r.Context()
	go func() {
		buf := make([]byte, 65536)
		for {
			udp.SetReadDeadline(time.Now().Add(*idle))
			n, _, err := udp.ReadFromUDPAddrPort(buf)
			if err != nil {
				ws.CloseNow()
				return
			}
			if ws.Write(ctx, websocket.MessageBinary, buf[:n]) != nil {
				return
			}
		}
	}()
	for {
		_, data, err := ws.Read(ctx)
		if err != nil {
			return
		}
		if len(data) == 10 && string(data[:8]) == "\xff\xff\xff\xffport" {
			continue
		}
		udp.WriteToUDPAddrPort(data, wsTarget)
	}
}

func originHosts() []string {
	var hosts []string
	for _, o := range strings.Split(*origins, ",") {
		o = strings.TrimPrefix(strings.TrimPrefix(o, "https://"), "http://")
		hosts = append(hosts, o)
	}
	return hosts
}

var wsTarget netip.AddrPort

func main() {
	flag.Parse()
	var err error
	if ourAddr, err = netip.ParseAddr(*publicIP); err != nil {
		log.Fatal(err)
	}
	for _, a := range strings.Split(*allow, ",") {
		ap, err := netip.ParseAddrPort(strings.TrimSpace(a))
		if err != nil {
			log.Fatalf("bad -allow entry %q: %v", a, err)
		}
		allowed[ap] = true
		if !wsTarget.IsValid() {
			wsTarget = ap
		}
	}

	mux, err := net.ListenUDP("udp4", &net.UDPAddr{Port: *rtcPort})
	if err != nil {
		log.Fatal(err)
	}
	se := webrtc.SettingEngine{}
	se.SetICEUDPMux(webrtc.NewICEUDPMux(nil, mux))
	se.SetNAT1To1IPs([]string{*publicIP}, webrtc.ICECandidateTypeHost)
	se.SetNetworkTypes([]webrtc.NetworkType{webrtc.NetworkTypeUDP4})
	api = webrtc.NewAPI(webrtc.WithSettingEngine(se))

	m := http.NewServeMux()
	m.HandleFunc("/rtc", handleRTC)
	m.HandleFunc("/ws", handleWS)
	m.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("ok\n"))
	})
	srv := &http.Server{Addr: *listen, Handler: m, ReadHeaderTimeout: 10 * time.Second}
	log.Printf("bsgate: signaling %s, webrtc udp %d, allow %s", *listen, *rtcPort, *allow)
	if *certFile != "" {
		log.Fatal(srv.ListenAndServeTLS(*certFile, *keyFile))
	}
	log.Fatal(srv.ListenAndServe())
}
