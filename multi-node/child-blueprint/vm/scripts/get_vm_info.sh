#!/bin/bash

# Wait up to $2 seconds for an IP on interface $1; prints IP or empty string
function wait_for_ip() {
  local iface=$1
  local timeout=$2
  local ip=""
  until [ $timeout -le 0 ] || [ -n "$ip" ]; do
    ip=$(ip -4 a s "$iface" | awk '/inet/ {print $2}' | cut -d'/' -f1)
    [ -n "$ip" ] && break
    sleep 10
    timeout=$((timeout - 10))
  done
  echo "$ip"
}

# Discover all enp*s0 interfaces in numeric order
mapfile -t ALL_IFACES < <(ls /sys/class/net/ | grep -E '^enp[0-9]+s0$' | sort -t 'p' -k2 -n)

PRIMARY_IFACE="${ALL_IFACES[0]}"                                       # enp1s0
MGMT_IFACE="${ALL_IFACES[-1]}"                                         # last = tap/mgmt
ADDITIONAL_IFACES=("${ALL_IFACES[@]:1:${#ALL_IFACES[@]}-2}")          # everything in between

# --- Primary NIC ---
VM_IP=$(wait_for_ip "$PRIMARY_IFACE" 30)
if [ -z "$VM_IP" ]; then
  ctx logger error "Timeout waiting for IP on primary interface ${PRIMARY_IFACE}."
  exit 1
fi
ctx logger info "Primary (${PRIMARY_IFACE}) IP: ${VM_IP}"
ctx instance runtime-properties capabilities.vm_public_ip "$VM_IP"

# --- Additional NICs ---
ADDITIONAL_ENTRIES=()
for iface in "${ADDITIONAL_IFACES[@]}"; do
  ip=$(ip -4 a s "$iface" | awk '/inet/ {print $2}' | cut -d'/' -f1)
  [ -z "$ip" ] && ip="N/A"
  ADDITIONAL_ENTRIES+=("${iface}:${ip}")
done

if [ ${#ADDITIONAL_ENTRIES[@]} -eq 0 ]; then
  ctx instance runtime-properties capabilities.vm_add_nics_ips "N/A"
else
  RESULT=$(printf '"%s",' "${ADDITIONAL_ENTRIES[@]}")
  ctx instance runtime-properties capabilities.vm_add_nics_ips "[${RESULT%,}]"
fi

# --- Management / Tap interface ---
if [ "$MGMT_IFACE" != "$PRIMARY_IFACE" ]; then
  TAP_IP=$(ip -4 a s "$MGMT_IFACE" | awk '/inet/ {print $2}' | cut -d'/' -f1)
  [ -z "$TAP_IP" ] && TAP_IP="N/A"
  ctx logger info "Tap interface (${MGMT_IFACE}) IP: ${TAP_IP}"
  ctx instance runtime-properties capabilities.tap_ip "$TAP_IP"
else
  ctx instance runtime-properties capabilities.tap_ip "N/A"
fi
