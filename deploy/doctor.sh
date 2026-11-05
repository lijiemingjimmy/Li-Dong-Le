#!/bin/sh
set -eu
printf 'OS: %s; architecture: %s; page size: %s\n' "$(uname -s)" "$(uname -m)" "$(getconf PAGE_SIZE)"
[ "$(uname -s)" = Linux ] || { echo 'Requires a Linux Docker host.'; exit 1; }
case "$(uname -m)" in aarch64|arm64) ;; *) echo 'This release supports ARM64 Linux only.'; exit 1 ;; esac
[ "$(getconf PAGE_SIZE)" = 4096 ] || { echo 'This Android image requires a 4KiB host kernel.'; exit 1; }
grep -qw binder /proc/filesystems || { echo 'binderfs is missing; load/enable the host binder_linux module.'; exit 1; }
[ -e /dev/dma_heap/system ] || { echo 'DMA-BUF system heap is missing on the host.'; exit 1; }
[ -d /proc/sys/net/ipv6 ] || { echo 'IPv6 kernel support is missing.'; exit 1; }
docker info >/dev/null
docker compose version
docker compose config --quiet
echo 'Host prerequisites found. App/login readiness is checked separately by ./ldl status.'
