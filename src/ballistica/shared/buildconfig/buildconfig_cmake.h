// Released under the MIT License. See LICENSE for details.

#ifndef BALLISTICA_SHARED_BUILDCONFIG_BUILDCONFIG_CMAKE_H_
#define BALLISTICA_SHARED_BUILDCONFIG_BUILDCONFIG_CMAKE_H_

// CMake may override our variant.
#if BA_VARIANT_TEST_BUILD
#define BA_VARIANT "test_build"
#elif BA_VARIANT_SERVER
#define BA_VARIANT "server"
#elif BA_VARIANT_SERVER_BASN
#define BA_VARIANT "server_basn"
#elif BA_VARIANT_STEAM
#define BA_VARIANT "steam"
#else
#define BA_VARIANT "generic"
#ifndef BA_VARIANT_GENERIC
#define BA_VARIANT_GENERIC 1
#endif
#endif

// For cmake builds, attempt to figure out what architecture we're running on
// and define stuff accordingly.
#if __APPLE__

// Yes Apple, I know GL is deprecated. I don't need constant reminders. You're
// stressing me out.
#define GL_SILENCE_DEPRECATION

#define BA_PLATFORM "macos"
#define BA_PLATFORM_MACOS 1

// We currently support regular and client builds on 64 bit mac posix
#if __amd64__
#define BA_ARCH "x86_64"
#elif __aarch64__
#define BA_ARCH "arm64"
#else
#error Unknown processor architecture.
#endif

#elif __EMSCRIPTEN__

// Web (WebAssembly) build. Emscripten provides a mostly-POSIX environment,
// so we reuse the Linux platform code and special-case with BA_PLATFORM_WEB.
#define BA_PLATFORM "linux"
#define BA_PLATFORM_LINUX 1
#define BA_PLATFORM_WEB 1
#define BA_ARCH "wasm32"

#elif __linux__

#define BA_PLATFORM "linux"
#define BA_PLATFORM_LINUX 1

#if __amd64__
#define BA_ARCH "x86_64"
#elif __i386__
#define BA_ARCH "x86"
#elif __arm__
#define BA_ARCH "arm"
#elif __aarch64__
#define BA_ARCH "arm64"
#else
#error unknown linux arch
#endif

#else
#error config_cmake.h: unknown architecture
#endif

#define dTRIMESH_ENABLED 1

// Builds without the closed-source plus feature-set: web (no wasm build of
// it exists) and native builds configured with the NO_PLUS cmake option
// (self-hosted servers). They run offline stand-ins instead (OfflinePlus in
// base.cc, ba_data/python/bawebplus.py).
#if BA_PLATFORM_WEB && !defined(BA_NO_PLUS)
#define BA_NO_PLUS 1
#endif
#ifndef BA_NO_PLUS
#define BA_NO_PLUS 0
#endif

#if !BA_HEADLESS_BUILD
#define BA_ENABLE_AUDIO 1

#define BA_ENABLE_OPENGL 1
#define BA_SDL_BUILD 1
#define BA_ENABLE_SDL_JOYSTICKS 1
#else
#define BA_MINSDL_BUILD 1
#endif

#if !BA_PLATFORM_WEB
// Yup we've got that.
#define BA_ENABLE_EXECINFO_BACKTRACES 1

// Allow stdin commands too.
#define BA_ENABLE_STDIO_CONSOLE 1
#endif

#ifndef BA_DEFINE_MAIN
#define BA_DEFINE_MAIN 1
#endif

#if !BA_DEBUG_BUILD

// Used by ODE.
#define dNODEBUG 1

// Used by assert.
#ifndef NDEBUG
#define NDEBUG
#endif
#endif  // !BA_DEBUG_BUILD

// Include some stuff here for once we get precompiling going.
#ifdef __cplusplus
#endif  // __cplusplus

// This must always be last.
#include "ballistica/shared/buildconfig/buildconfig_common.h"

#endif  // BALLISTICA_SHARED_BUILDCONFIG_BUILDCONFIG_CMAKE_H_
