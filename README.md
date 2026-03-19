# edge-cloudinit-linux

A blueprint for the **Dell Automation Platform** that deploys a cloud-init Linux Virtual Machine on a NativeEdge Endpoint for the **NativeEdge Outcome**. The VM is fully configured at first boot via cloud-init, including networking, users, and storage.

This blueprint may be used standalone or as a target environment for the **tme-tech-ops blueprint suite**.

## Getting Started

1. Download the **edge-cloudinit-utility-vm** blueprint from the [edge-cloudinit-utility-vm repository](https://tme-tech-ops/edge-cloudinit-utility-vm) using **Code > Download ZIP**.
2. Upload it from the **Blueprints** page in the Dell Automation Platform. It is recommended to name this blueprint `edge-cloudinit-utility-vm`.
3. Download this blueprint using **Code > Download ZIP**.
4. Upload it from the **Blueprints** page.

During deployment, inputs can be provided through the UI form or by uploading a JSON/YAML input file through the UI.

## Table of Contents

[Supported Features](#supported-features)
[Getting Started](#getting-started)
[Prerequisites](#prerequisites)
[Secrets](#secrets)
[Inputs](#inputs)
[Outputs / Capabilities](#outputs--capabilities)
[Network Interface Layout](#network-interface-layout)
[Multi-VM Deployment](#multi-vm-deployment)
[Usage Examples](#usage-examples)
[Notes](#notes)

---

## Supported Features

| Feature | Details |
|---|---|
| **OS Support** | Ubuntu 18.04 / 20.04 / 22.04 / 22.10 / 24.04, Debian (32/64-bit), RHEL 9, SUSE SLES 15, Linux Other |
| **Multiple VM Definitions** | Deploy up to 10 VMs from a single blueprint (1 base + up to 9 additional) |
| **Multiple Disks** | Primary OS disk + additional virtual disks, configurable size and datastore |
| **Multiple NICs** | Primary NIC + up to 9 additional NICs; each independently configured |
| **NIC Types** | NAT (with port forwarding) or Bridge per interface |
| **Static / DHCP** | Configurable per NIC — DHCP or static IP, gateway, DNS |
| **UEFI / Secure Boot** | Optional UEFI firmware, Secure Boot, and vTPM |
| **Device Passthrough** | USB, PCIe, GPU, Video, and Serial port passthrough |
| **SSH Key Automation** | SSH keypair generated automatically at deploy time |

> **Note:** This blueprint creates a cloud-init configuration tuned for networkd and netplan, which is default for Ubuntu. Adjust other OS platforms accordingly.

---

## Prerequisites

- A **NativeEdge Endpoint** onboarded in the Dell Automation Platform
- A **Virtual Network Segment** (NAT or Bridge) configured on the Endpoint for the primary NIC
- The **edge-cloudinit-utility-vm** blueprint uploaded to the platform (see [Getting Started](#getting-started))
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

This secret holds the login password for the VM user account. Type the password in plain text; it will automatically be encrypted (SHA-512) at runtime.

---

## Inputs

### Required Inputs

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
| Number of Virtual Machines | `number_of_vms` | Integer | `1` | Number of VMs to create (1-10) |
| OS Image Secret | `edge_os_image_secret` | Secret | — | OS image secret (see [Secrets](#secrets)) |
| VM Password | `vm_password` | Secret | — | VM user password secret (see [Secrets](#secrets)) |
| Endpoint Datastore Path | `disk_wrapper` | String | — | Datastore path on the target Endpoint (selected from endpoint inventory) |
| Virtual Network Segment | `vnic_0_segment_name` | String | — | Virtual Network Segment name for the primary NIC (selected from endpoint inventory) |
| OS Disk Size | `os_disk_size` | String | `50GB` | OS disk size — value + unit (e.g. `100GB`) |

---

### Basic VM Configuration (Optional)

| Display Name | Input Name | Type | Default | Updatable | Description |
|---|---|---|---|---|---|
| OS Type | `os_type` | String | `UBUNTU22.04` | No | Operating system type |
| Utility Blueprint Name | `utility_blueprint_id` | String | `edge-cloudinit-utility-vm` | No | Name of the uploaded edge-cloudinit utility blueprint |
| VM Name | `vm_name` | String | `edge-cloudinit-01` | Yes | Name of the Virtual Machine |
| VM Hostname | `vm_hostname` | String | `edgehost-01` | Yes | Hostname (letters, numbers, hyphens only; max 63 chars) |
| VM Username | `vm_user_name` | String | `edgeuser` | No | Login username for the VM |
| Use DHCP | `use_dhcp` | Boolean | `true` | Yes | Use DHCP on the primary NIC. If false, configure static IP below |
| Static IP/CIDR | `static_ip` | String | — | Yes | Static IP in CIDR notation (e.g. `192.168.1.100/24`). Required when DHCP is disabled |
| Use Gateway | `use_gateway` | Boolean | `false` | Yes | Configure a default gateway |
| Gateway IP | `gateway` | String | — | Yes | Gateway IP address (e.g. `192.168.1.1`) |
| Use DNS | `use_dns` | Boolean | `false` | Yes | Configure DNS servers |
| DNS Servers | `dns` | List | `[]` | Yes | List of DNS server IP addresses |

**Supported OS Types:** `UBUNTU18.04`, `UBUNTU20.04`, `UBUNTU22.04`, `UBUNTU22.10`, `UBUNTU24.04`, `DEBIAN-32B`, `DEBIAN-64B`, `RHEL9`, `SUSE-SLES15`, `LINUX-OTHER`
> **Note:** This blueprint creates a cloud-init configuration tuned for networkd and netplan, which is default for Ubuntu. Adjust other OS platforms accordingly.

---

### Advanced VM Configuration (Optional)

#### Hardware and Resources

| Display Name | Input Name | Type | Default | Updatable | Description |
|---|---|---|---|---|---|
| Firmware Type | `hardware_options.firmware_type` | String | `BIOS` | No | Firmware type: `BIOS` or `UEFI` |
| Secure Boot | `hardware_options.secure_boot` | Boolean | `false` | No | Enable Secure Boot (requires UEFI) |
| Add vTPM | `hardware_options.vTPM` | Boolean | `false` | No | Add a virtual TPM (typically required for Secure Boot) |
| vCPUs | `vcpus` | Integer | `2` | Yes | Number of virtual CPUs (minimum 2) |
| Memory Size | `memory_size` | String | `4GB` | Yes | RAM allocation — value + unit (e.g. `8GB`) |
| Disk Controller | `disk_controller` | String | `VIRTIO` | Yes | Disk controller type: `VIRTIO`, `SATA`, or `SCSI` |

#### Additional Disks

Enable with `add_disks: true` to reveal the disk list.

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
| Add Additional Disks | `add_disks` | Boolean | `false` | Enable additional virtual disks |
| Additional Disks | `additional_disks` | List | `[]` | List of additional virtual disks to attach |

Each disk entry requires:

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | String | `vdisk2` | Unique name to identify the disk |
| `disk` | String | `/DataStore0` | DataStore path where the disk will be created |
| `storage` | Integer | `16` | Disk size (integer) |
| `storage_unit` | String | `GB` | Size unit: `KB`, `MB`, `GB`, `TB`, etc. |

#### NAT Port Forwarding

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
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

#### Additional Network Interfaces

Enable with `add_nics: true` to reveal the NIC list.

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
| Add Additional NICs | `add_nics` | Boolean | `false` | Enable additional network interfaces |
| Additional NICs | `vm_add_nics` | List | `[]` | Up to 9 additional NICs beyond the primary |

Each additional NIC entry:

| Field | Required | Default | Description |
|---|---|---|---|
| `nic_name` | Yes | — | Unique label for this NIC entry (e.g. `nic2`) |
| `segment_name` | Yes | — | Virtual Network Segment name to attach to (NAT or Bridge) |
| `use_dhcp` | Yes | `true` | Use DHCP. If false, `static_ip` is required |
| `accept_dhcp_routes` | No | `false` | Accept gateway/routes from DHCP. Disable to prevent routing conflicts |
| `static_ip` | No | — | Static IP/CIDR (e.g. `10.10.0.50/24`). Required when DHCP is disabled |
| `use_gateway` | No | `false` | Configure a static route for this NIC |
| `gateway` | No | — | Gateway IP for the static route |
| `route_destination` | No | — | Destination subnet in CIDR (e.g. `10.20.0.0/16`). Do not use `0.0.0.0/0` |
| `use_dns` | No | `false` | Configure DNS servers for this NIC |
| `dns` | No | — | Comma-separated DNS IPs (e.g. `8.8.8.8,8.8.4.4`) |
| `use_nat` | No | `false` | Enable NAT port forwarding on this NIC |
| `port_forward_rules` | No | — | JSON string of port forwarding rules |

> **Note:** Multiple NICs may share the same segment name. Only the primary NIC should have a default route (`0.0.0.0/0`).

#### Device Passthrough

Enable with `use_passthrough: true`. All passthrough inputs are populated from the endpoint inventory.

| Display Name | Input Name | Type | Description |
|---|---|---|---|
| Enable Device Passthrough | `use_passthrough` | Boolean | Enable device passthrough |
| USB Devices | `usb_wrapper` | List | USB device logical names to pass through |
| GPU Devices | `gpu_wrapper` | List | GPU logical names to pass through |
| PCIe Devices | `pcie_wrapper` | List | PCIe device logical names to pass through |
| Video Devices | `video` | List | Video controller to pass through (e.g. `onboard controller`) |
| Serial Ports | `serial_port_wrapper` | List | Serial port + mode pairs to pass through (e.g. `COM-1_RS-232`) |

---

## Outputs / Capabilities

After a successful deployment, the following values are available as environment capabilities:

### Base VM Outputs

| Output | Description |
|---|---|
| `base_vm` | Base VM details (name, hostname, primary IP, service tag, network interfaces, SSH info) |
| `vm_user_name` | Login username for the VM |
| `vm_ssh_private_key` | Name of the secret holding the auto-generated SSH private key |
| `vm_password_secret` | Reference to the VM password secret |

### Multi-VM Outputs

When deploying additional VMs (`number_of_vms` > 1):

| Output | Description |
|---|---|
| `additional_vm` | Dictionary of additional VMs keyed by VM name, each containing name, hostname, primary IP, service tag, network interfaces, and SSH info |

---

## Network Interface Layout

The VM interfaces are assigned in the following deterministic order:

| Interface | Role |
|---|---|
| `enp1s0` | Primary NIC (`vnic_0_segment_name`) |
| `enp2s0` ... `enp{N+1}s0` | Additional NICs (in order of the `vm_add_nics` list) |
| `enp{N+2}s0` | Management / tap interface (infrastructure segment, always present) |

---

## Multi-VM Deployment

The blueprint supports deploying up to 10 VMs from a single deployment using the `number_of_vms` input.

### How It Works

- Set `number_of_vms` to the total number of VMs (1-10). The first VM uses the base inputs documented above.
- For each additional VM (2-10), a set of per-VM inputs becomes available in the UI, prefixed with `vm_N_` (e.g. `vm_2_name`, `vm_3_vcpus`).
- Each additional VM also has a `deployment_id_0N` input (e.g. `deployment_id_02`) to select which NativeEdge Endpoint it will be deployed on.
- Additional VM inputs only appear in the UI when `number_of_vms` is set to that VM's number or higher.

### Per-VM Inputs (VMs 2-10)

Each additional VM supports the same configuration categories as the base VM. The input names follow the pattern `vm_N_<input_name>`:

| Category | Inputs | Defaults |
|---|---|---|
| **Endpoint** | `deployment_id_0N` | — (required) |
| **Identity** | `vm_N_name`, `vm_N_hostname` | `edge-cloudinit-0N`, `edgehost-0N` |
| **Resources** | `vm_N_vcpus`, `vm_N_memory_size`, `vm_N_os_disk_size`, `vm_N_disk_controller` | `2`, `4GB`, `50GB`, `VIRTIO` |
| **Storage** | `vm_N_disk_wrapper` | — (required) |
| **Primary Network** | `vm_N_vnic_0_segment_name`, `vm_N_use_dhcp`, `vm_N_static_ip`, `vm_N_use_gateway`, `vm_N_gateway`, `vm_N_use_dns`, `vm_N_dns` | — (segment required), `true`, ... |
| **NAT** | `vm_N_use_nat`, `vm_N_port_forward_rules` | `false`, `[]` |
| **Additional NICs** | `vm_N_add_nics`, `vm_N_vm_add_nics` | `false`, `[]` |
| **Additional Disks** | `vm_N_add_disks`, `vm_N_additional_disks` | `false`, `[]` |
| **Device Passthrough** | `vm_N_use_passthrough`, `vm_N_usb_wrapper`, `vm_N_gpu_wrapper`, `vm_N_pcie_wrapper`, `vm_N_video`, `vm_N_serial_port_wrapper` | `false`, `[]` |

> Replace `N` with the VM number (2-10) and `0N` with the zero-padded VM number (02-10).

### Cross-Endpoint Deployment

Each additional VM can target a different NativeEdge Endpoint via its `deployment_id_0N` input. Ensure that:

- All target endpoints are onboarded in the platform
- Required network segments exist on each target endpoint
- Sufficient resources (CPU, memory, storage) are available on each endpoint

---

## Usage Examples

### Single VM with DHCP

```yaml
number_of_vms: 1
edge_os_image_secret: "my_image_secret_name"
vm_name: "edge-cloudinit-01"
vm_hostname: "edgehost-01"
vm_user_name: "edgeuser"
vm_password: "my_password_secret_name"
disk_wrapper: "/DataStore0"
vnic_0_segment_name: "bridge0"
vcpus: 2
memory_size: "4GB"
os_disk_size: "50GB"
use_dhcp: true
```

### Single VM with Static IP

```yaml
number_of_vms: 1
edge_os_image_secret: "my_image_secret_name"
os_type: "UBUNTU22.04"
utility_blueprint_id: "edge-cloudinit-utility-vm"
vm_name: "edge-cloudinit-01"
vm_hostname: "edgehost-01"
vm_user_name: "edgeuser"
vm_password: "my_password_secret_name"
disk_wrapper: "/DataStore0"
vnic_0_segment_name: "bridge0"
vcpus: 4
memory_size: "8GB"
os_disk_size: "100GB"
use_dhcp: false
static_ip: "192.168.1.100/24"
use_gateway: true
gateway: "192.168.1.1"
use_dns: true
dns:
  - "8.8.8.8"
  - "8.8.4.4"
```

### Two VMs on the Same Endpoint

```yaml
number_of_vms: 2

# Base VM
edge_os_image_secret: "my_image_secret_name"
vm_name: "edge-cloudinit-01"
vm_hostname: "edgehost-01"
vm_user_name: "edgeuser"
vm_password: "my_password_secret_name"
disk_wrapper: "/DataStore0"
vnic_0_segment_name: "bridge0"
vcpus: 2
memory_size: "4GB"
os_disk_size: "50GB"
use_dhcp: true

# VM 2
deployment_id_02: "ece-XXXXXXX"
vm_2_name: "edge-cloudinit-02"
vm_2_hostname: "edgehost-02"
vm_2_vcpus: 4
vm_2_memory_size: "8GB"
vm_2_os_disk_size: "100GB"
vm_2_disk_wrapper: "/DataStore1"
vm_2_vnic_0_segment_name: "bridge1"
vm_2_use_dhcp: false
vm_2_static_ip: "10.10.0.50/24"
vm_2_use_gateway: true
vm_2_gateway: "10.10.0.1"
```

### Three VMs Across Multiple Endpoints

```yaml
number_of_vms: 3

# Base VM (deployed on the primary endpoint selected during deployment)
edge_os_image_secret: "my_image_secret_name"
vm_name: "web-server"
vm_hostname: "webserver-01"
vm_user_name: "admin"
vm_password: "my_password_secret_name"
disk_wrapper: "/DataStore0"
vnic_0_segment_name: "bridge0"
vcpus: 2
memory_size: "4GB"
os_disk_size: "50GB"
use_dhcp: true

# VM 2 on a second endpoint
deployment_id_02: "ece-XXXXXXX"
vm_2_name: "app-server"
vm_2_hostname: "apphost-01"
vm_2_vcpus: 4
vm_2_memory_size: "16GB"
vm_2_os_disk_size: "100GB"
vm_2_disk_wrapper: "/DataStore0"
vm_2_vnic_0_segment_name: "bridge0"
vm_2_use_dhcp: true

# VM 3 on a third endpoint
deployment_id_03: "ece-YYYYYYY"
vm_3_name: "db-server"
vm_3_hostname: "dbhost-01"
vm_3_vcpus: 4
vm_3_memory_size: "16GB"
vm_3_os_disk_size: "200GB"
vm_2_disk_wrapper: "/Shared_DataStore"
vm_2_vnic_0_segment_name: "bridge0"
vm_3_use_dhcp: false
vm_3_static_ip: "192.168.10.100/24"
vm_3_use_gateway: true
vm_3_gateway: "192.168.10.1"
vm_3_add_disks: true
vm_3_additional_disks:
  - name: "data-disk"
    disk: "/DataStore0"
    storage: 500
    storage_unit: "GB"
vm_3_add_nics: true
vm_3_vm_add_nics:
  - nic_name: nic2
  - segment_name: bridge1
  - use_dhcp: false
  - static_ip: "172.16.20.50/22"
```

---

## Notes

- The SSH keypair is generated automatically at deploy time. The private key is stored as a platform secret and referenced by the `vm_ssh_private_key` output. If you prefer your own SSH key pair, create `general` type secrets containing the values named `edge_key_public` and `edge_key_private` respectively.
- The management tap interface is always provisioned regardless of additional NIC configuration, and always occupies the last `enp*s0` interface slot.
- `accept_dhcp_routes` on additional NICs defaults to `false` to prevent unintended default route conflicts with the primary NIC.
- All additional VMs share the same OS type, username, password, and SSH keys as the base VM.
- The maximum number of VMs per deployment is 10. For larger deployments, use multiple blueprint deployments.
