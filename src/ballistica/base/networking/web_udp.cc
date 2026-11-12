// Released under the MIT License. See LICENSE for details.

#include "ballistica/base/networking/web_udp.h"

#if BA_PLATFORM_WEB

#include <arpa/inet.h>
#include <emscripten/emscripten.h>
#include <netinet/in.h>

#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <mutex>
#include <vector>

namespace ballistica::base {

namespace {

struct WebUdpPacket {
  uint32_t ip{};    // network byte order
  uint16_t port{};  // network byte order
  std::vector<uint8_t> data;
};

// Bounded so a stalled reader can't eat memory; game traffic is far below.
constexpr size_t kMaxQueued = 4096;

std::mutex g_mutex;
std::condition_variable g_cv;
std::deque<WebUdpPacket> g_queue;
bool g_open{};

void WebUdpPush(WebUdpPacket&& p) {
  {
    std::scoped_lock lock(g_mutex);
    if (!g_open || g_queue.size() >= kMaxQueued) {
      return;
    }
    g_queue.push_back(std::move(p));
  }
  g_cv.notify_one();
}

}  // namespace

void WebUdpOpen() {
  std::scoped_lock lock(g_mutex);
  g_open = true;
}

void WebUdpClose() {
  {
    std::scoped_lock lock(g_mutex);
    g_open = false;
    g_queue.clear();
  }
  g_cv.notify_all();
}

auto WebUdpWaitReadable() -> bool {
  std::unique_lock lock(g_mutex);
  g_cv.wait(lock, [] { return !g_open || !g_queue.empty(); });
  return g_open && !g_queue.empty();
}

void WebUdpPushLocal(const void* data, size_t len) {
  WebUdpPacket p;
  p.ip = htonl(INADDR_LOOPBACK);
  p.port = 0;
  p.data.assign(static_cast<const uint8_t*>(data),
                static_cast<const uint8_t*>(data) + len);
  WebUdpPush(std::move(p));
}

auto WebUdpRecvFrom(void* buf, size_t len, sockaddr* from, socklen_t* from_len)
    -> ssize_t {
  WebUdpPacket p;
  {
    std::scoped_lock lock(g_mutex);
    if (g_queue.empty()) {
      errno = EWOULDBLOCK;
      return -1;
    }
    p = std::move(g_queue.front());
    g_queue.pop_front();
  }
  auto n = std::min(len, p.data.size());
  memcpy(buf, p.data.data(), n);
  if (from && from_len) {
    sockaddr_in sa{};
    sa.sin_family = AF_INET;
    sa.sin_addr.s_addr = p.ip;
    sa.sin_port = p.port;
    auto copy_len = std::min(static_cast<size_t>(*from_len), sizeof(sa));
    memcpy(from, &sa, copy_len);
    *from_len = sizeof(sa);
  }
  return static_cast<ssize_t>(n);
}

auto WebUdpSendTo(const void* buf, size_t len, const sockaddr* to) -> ssize_t {
  if (!to || to->sa_family != AF_INET || len == 0 || len > 65000) {
    errno = EINVAL;
    return -1;
  }
  const auto* sa = reinterpret_cast<const sockaddr_in*>(to);

  // Frame it: [ip][port][payload]. Handed to JS on the browser main thread
  // (the data channel lives there), which frees the copy.
  auto* frame = static_cast<uint8_t*>(malloc(len + 6));
  if (!frame) {
    errno = ENOMEM;
    return -1;
  }
  memcpy(frame, &sa->sin_addr.s_addr, 4);
  memcpy(frame + 4, &sa->sin_port, 2);
  memcpy(frame + 6, buf, len);
  MAIN_THREAD_ASYNC_EM_ASM(
      {
        const frame = HEAPU8.slice($0, $0 + $1);
        _free($0);
        if (Module.baUdp) {
          Module.baUdp.send(frame);
        }
      },
      frame, static_cast<int>(len + 6));
  return static_cast<ssize_t>(len);
}

}  // namespace ballistica::base

// Called from JS (browser main thread) for each frame arriving on the data
// channel. Takes ownership of the malloc'd frame.
extern "C" EMSCRIPTEN_KEEPALIVE void ba_web_udp_recv(uint8_t* frame,
                                                     int len) {
  if (frame && len > 6) {
    ballistica::base::WebUdpPacket p;
    memcpy(&p.ip, frame, 4);
    memcpy(&p.port, frame + 4, 2);
    p.data.assign(frame + 6, frame + len);
    ballistica::base::WebUdpPush(std::move(p));
  }
  free(frame);
}

#endif  // BA_PLATFORM_WEB
