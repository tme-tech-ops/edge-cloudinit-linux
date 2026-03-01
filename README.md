# edge-cloudinit-linux

A blueprint for the **Dell Automation Platform** that deploys a cloud-init Linux Virtual Machine on a NativeEdge Endpoint for the **NativeEdge Outcome**. The VM is fully configured at first boot via cloud-init, including networking, users, and storage.

This blueprint may be used standalone or as a target environment for the **tme-tech-ops blueprint suite**.

---

## Supported Features

| Feature | Details |
|---|---|
| **OS Support** | Ubuntu 18.04 / 20.04 / 22.04 / 22.10 / 24.04, Debian (32/64-bit), RHEL 9, SUSE SLES 15, Linux Other |
| **Multiple Disks** | Primary OS disk + up to N additional virtual disks, configurable size and datastore |
| **Multiple NICs** | Primary NIC + up to 9 additional NICs; each independently configured |
| **NIC Types** | NAT (with port forwarding) or Bridge per interface |
| **Static / DHCP** | Configurable per NIC — DHCP or static IP, gateway, DNS |
| **UEFI / Secure Boot** | Optional UEFI firmware, Secure Boot, and vTPM |
| **Device Passthrough** | USB, PCIe, GPU, Video, and Serial port passthrough |
| **SSH Key Automation** | SSH keypair generated automatically at deploy time |

---

## Prerequisites

- A **NativeEdge Endpoint** onboarded in the Dell Automation Platform
- A **Virtual Network Segment** (NAT or Bridge) configured on the Endpoint for the primary NIC
- Two secrets created before deployment (see [Secrets](#secrets))

---

## Secrets

Two secrets must be created in the platform before deploying this blueprint.

### 1. OS Image Secret (`edge_os_image_secret`)

Type: **Binary Configuration**

This secret provides the blueprint with access to the OS image repository. It must contain the following fields:

| Field | Description | Example |
|---|---|---|
| `binary_image_url` | URL of the OS image | `https://repo.example.com/images/ubuntu22.img` |
| `binary_image_access_user` | Repository username | (only if required) `myuser` |
| `binary_image_access_token` | Repository access token or password | (only if required) `mytoken` |
| `binary_image_version` | Image version tag | `22.04.1` |

---

### 2. VM Password Secret (`vm_password`)

Type: **Password**

This secret holds the login password for the VM user account. Type the password in plain text, it will automatically be encrypted (SHA-256) at runtime.

---

## Inputs

### Required Inputs

| Display Name | Input Name | Type | Description |
|---|---|---|---|
| OS Image Secret for Virtual Machine creation | `edge_os_image_secret` | Secret | OS image secret (see [Secrets](#secrets)) |
| VM Password | `vm_password` | Secret | VM user password secret (see [Secrets](#secrets)) |
| Endpoint Datastore Path | `disk_wrapper` | String | Datastore path on the target Endpoint (selected from endpoint inventory) |
| Virtual Network Segment name for Management Interface | `vnic_0_segment_name` | String | Virtual Network Segment name for the primary NIC (selected from endpoint inventory) |

---

### Virtual Machine

| Display Name | Input Name | Type | Default | Updatable | Description |
|---|---|---|---|---|---|
| VM Name | `vm_name` | String | `edge-cloud-init-01` | Yes | Name of the Virtual Machine |
| VM Hostname | `vm_hostname` | String | `edgehost` | Yes | Hostname (letters, numbers, hyphens only; max 63 chars) |
| VM Username | `vm_user_name` | String | `edgeuser` | No | Login username for the VM |
| OS Type | `os_type` | String | `UBUNTU22.04` | No | Operating system type |
| vCPUs | `vcpus` | Integer | `2` | Yes | Number of virtual CPUs (minimum 2) |
| Memory Size | `memory_size` | String | `4GB` | Yes | RAM allocation — value + unit (e.g. `8GB`) |
| OS Disk Size | `os_disk_size` | String | `50GB` | Yes | OS disk size — value + unit (e.g. `100GB`) |
| Disk Controller | `disk_controller` | String | `VIRTIO` | Yes | Disk controller type: `VIRTIO`, `SATA`, or `SCSI` |
| Endpoint Datastore Path | `disk_wrapper` | String | *(required)* | No | DataStore path for OS disk (selected from endpoint inventory) |

**Supported OS Types:** `UBUNTU18.04`, `UBUNTU20.04`, `UBUNTU22.04`, `UBUNTU22.10`, `UBUNTU24.04`, `DEBIAN-32B`, `DEBIAN-64B`, `RHEL9`, `SUSE-SLES15`, `LINUX-OTHER`

---

### Additional Disks (Optional)

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
| Optional list of additional Virtual Disks | `additional_disks` | List | `[]` | List of additional virtual disks to attach to the VM |

Each disk entry requires:

| Display Name | Field Name | Default | Description |
|---|---|---|---|
| Name | `name` | `vdisk2` | Unique name to identify the disk |
| Disk Path | `disk` | `/DataStore0` | DataStore path where the disk will be created |
| Storage Size | `storage` | `16` | Disk size (integer) |
| Storage Unit | `storage_unit` | `GB` | Size unit: `KB`, `MB`, `GB`, `TB`, etc. |

---

### Advanced Boot Options (Optional)

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
| Firmware Type | `hardware_options.firmware_type` | String | `BIOS` | Firmware type: `BIOS` or `UEFI` |
| Secure Boot | `hardware_options.secure_boot` | Boolean | `false` | Enable Secure Boot (requires UEFI) |
| Add vTPM | `hardware_options.vTPM` | Boolean | `false` | Add a virtual TPM (typically required for Secure Boot) |

---

### Device Passthrough (Optional)

Enable with `use_passthrough: true`. All passthrough inputs are populated from the endpoint inventory.

| Display Name | Input Name | Type | Description |
|---|---|---|---|
| Enable device passthrough | `use_passthrough` | Boolean | Enable device passthrough |
| USB Device list | `usb` | List | USB device logical names to pass through |
| PCIe Passthrough | `pcie` | List | PCIe device logical names to pass through |
| GPU Passthrough | `gpu` | List | GPU logical names to pass through |
| Video Passthrough | `video` | List | Video controller to pass through (e.g. `onboard controller`) |
| Serial Port | `serial_port_wrapper` | List | Serial port + mode pairs to pass through |

---

### Primary Network Interface

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
| Virtual Network Segment name for Management Interface | `vnic_0_segment_name` | String | *(required)* | Virtual Network Segment for the primary NIC |
| Use DHCP | `use_dhcp` | Boolean | `true` | Use DHCP on the primary NIC |
| Static IP and CIDR prefix | `static_ip` | String | — | Static IP/CIDR (e.g. `192.168.1.100/24`). Required when DHCP is disabled |
| Use Gateway | `use_gateway` | Boolean | `false` | Configure a default gateway |
| Gateway IP | `gateway` | String | — | Gateway IP address (e.g. `192.168.1.1`) |
| Use DNS | `use_dns` | Boolean | `false` | Configure DNS servers |
| DNS Servers | `dns` | List | `[]` | List of DNS server IP addresses |
| Enable NAT Port Forwarding | `use_nat` | Boolean | `false` | Enable NAT port forwarding on the primary NIC |
| Port Mapping | `port_forward_rules` | List | `[]` | Port forwarding rules (see below) |

**Port forwarding rule fields:**

| Field | Description |
|---|---|
| `host_ip` | IP of the NAT interface on the Endpoint host |
| `host_port` | Host-side port to expose |
| `vm_port` | VM-side port to forward to |
| `protocol` | `TCP` or `UDP` |
| `service_type` | `SSH`, `HTTP`, or `CUSTOM` |
| `vm_ip` | VM IP — only required when using static IP on the primary NIC |

---

### Additional Network Interfaces (Optional)

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
| Additional Network Interfaces | `additional_nics` | List | `[]` | Up to 9 additional NICs beyond the primary |

Each additional NIC entry:

| Display Name | Field Name | Required | Default | Description |
|---|---|---|---|---|
| NIC Label | `nic_name` | Yes | — | Unique label for this NIC entry (e.g. `Data NIC 1`) |
| Segment Name | `segment_name` | Yes | — | Virtual Network Segment name to attach to (NAT or Bridge) |
| Use DHCP | `use_dhcp` | Yes | `true` | Use DHCP. If false, `static_ip` is required |
| Accept DHCP Routes | `accept_dhcp_routes` | No | `false` | Accept gateway/routes from DHCP. Disable to prevent routing conflicts |
| Static IP/CIDR | `static_ip` | No | — | Static IP/CIDR (e.g. `10.10.0.50/24`). Required when DHCP is disabled |
| Use Gateway | `use_gateway` | No | `false` | Configure a static route for this NIC |
| Gateway IP | `gateway` | No | — | Gateway IP for the static route |
| Route Destination (CIDR) | `route_destination` | No | — | Destination subnet in CIDR (e.g. `10.20.0.0/16`). Do not use `0.0.0.0/0` |
| Use DNS | `use_dns` | No | `false` | Configure DNS servers for this NIC |
| DNS Servers | `dns` | No | — | Comma-separated DNS IPs (e.g. `8.8.8.8,8.8.4.4`) |
| Enable NAT | `use_nat` | No | `false` | Enable NAT port forwarding on this NIC |
| Port Forward Rules (JSON) | `port_forward_rules` | No | — | JSON string of port forwarding rules |

> **Note:** Multiple NICs may share the same segment name. Only the primary NIC should have a default route (`0.0.0.0/0`).

---

## Outputs / Capabilities

After a successful deployment, the following values are available as environment capabilities:

| Output | Description |
|---|---|
| `service_tag` | NativeEdge Endpoint service tag |
| `vm_name` | Name of the deployed Virtual Machine |
| `vm_hostname` | Hostname configured inside the VM |
| `vm_primary_ip` | IP address of the primary NIC (`enp1s0`) |
| `additional_nics` | IPs of additional NICs as `["enp2s0:192.168.10.50", ...]`, or `N/A` if none |
| `tap_interface` | IP address of the management (tap) interface |
| `vm_user_name` | Login username for the VM |
| `vm_ssh_private_key` | Name of the secret holding the auto-generated SSH private key |
| `vm_password_secret` | Reference to the VM password secret |

---

## Network Interface Layout

The VM interfaces are assigned in the following deterministic order:

| Interface | Role |
|---|---|
| `enp1s0` | Primary NIC (`vnic_0_segment_name`) |
| `enp2s0` … `enp{N+1}s0` | Additional NICs (in order of the `additional_nics` list) |
| `enp{N+2}s0` | Management / tap interface (infrastructure segment, always present) |

---

## Notes

- The SSH keypair is generated automatically at deploy time. The private key is stored as a platform secret and referenced by the `vm_ssh_private_key` output. If you preffer your own ssh-key pair, create `general` type secrets containing the values name `edge_key_public` and `edge_key_private` respectively.
- The management tap interface is always provisioned regardless of `additional_nics` configuration, and always occupies the last `enp*s0` interface slot.
- `accept_dhcp_routes` on additional NICs defaults to `false` to prevent unintended default route conflicts with the primary NIC.
