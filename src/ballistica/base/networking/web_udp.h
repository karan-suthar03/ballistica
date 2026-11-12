// Released under the MIT License. See LICENSE for details.

#ifndef BALLISTICA_BASE_NETWORKING_WEB_UDP_H_
#define BALLISTICA_BASE_NETWORKING_WEB_UDP_H_

#include "ballistica/shared/ballistica.h"

#if BA_PLATFORM_WEB

#include <sys/socket.h>
#include <sys/types.h>

#include <cstddef>

// UDP for web builds. Browsers can't send raw UDP, so the engine's single
// IPv4 game socket is backed by a WebRTC data channel (unordered, no
// retransmits: UDP semantics) to our gateway, which forwards each datagram
// to its real UDP destination and passes replies back. Frames on the
// channel are [4-byte IPv4][2-byte port, big endian][payload], naming the
// destination (outgoing) or source (incoming) address. The JS side lives in
// web/shell (Module.baUdp). By Karan (@karan-suthar03), 2026-11-12.
namespace ballistica::base {

/// Stand-in socket descriptor for the web UDP socket. Never a real fd.
constexpr int kWebUdpSocket = 0x7ffff000;

/// Start accepting/sending packets (the JS side connects lazily).
void WebUdpOpen();

/// Stop; queued incoming packets are dropped.
void WebUdpClose();

/// Block until a packet is waiting. Returns false if closed.
auto WebUdpWaitReadable() -> bool;

/// Queue a packet as if it arrived from loopback (wakes the reader).
void WebUdpPushLocal(const void* data, size_t len);

auto WebUdpRecvFrom(void* buf, size_t len, sockaddr* from, socklen_t* from_len)
    -> ssize_t;

auto WebUdpSendTo(const void* buf, size_t len, const sockaddr* to) -> ssize_t;

}  // namespace ballistica::base

#endif  // BA_PLATFORM_WEB

#endif  // BALLISTICA_BASE_NETWORKING_WEB_UDP_H_
