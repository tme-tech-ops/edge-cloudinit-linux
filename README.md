# edge-cloudinit-linux

A blueprint for the **Dell Automation Platform** that deploys a cloud-init Linux Virtual Machine on a NativeEdge Endpoint for the **NativeEdge Outcome**. The VM is fully configured at first boot via cloud-init, including networking, users, and storage.

This blueprint may be used standalone or as a target environment for the **tme-tech-ops blueprint suite**.

## Table of Contents

[Supported Features](#supported-features)  
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
| **Multiple VM Definitions** | Support for multiple VM deployments from a single blueprint |
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
- The **edge-cloudinit-utility-vm** blueprint uploaded to the platform
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

### Multi-VM Deployment (Optional)

Deploy additional VMs alongside the base VM. Each additional VM can be deployed on different NativeEdge Endpoints with independent configurations.

| Display Name | Input Name | Type | Default | Description |
|---|---|---|---|---|
| Additional VM Configurations | `additional_vm` | List | `[]` | List of additional VM configurations. Each entry defines a VM with per-VM settings. The number of VM instances is automatically calculated from this list. |
| Add NICs to Additional VMs | `add_vm_nics` | Boolean | `false` | Enable additional network interfaces for additional VMs |
| Additional VM NICs | `add_vm_add_nics` | List | `[]` | Network interface configurations for additional VMs |
| Add Disks to Additional VMs | `add_vm_disks` | Boolean | `false` | Enable additional virtual disks for additional VMs |
| Additional VM Disks | `add_vm_add_disks` | List | `[]` | Virtual disk configurations for additional VMs |
| Add Passthrough Devices to Additional VMs | `add_vm_passthrough` | Boolean | `false` | Enable device passthrough for additional VMs |
| Additional VM Passthrough Devices | `add_vm_passthrough_devices` | List | `[]` | Device passthrough configurations for additional VMs |

**Additional VM Configuration Fields:**

| Display Name | Field Name | Required | Default | Description |
|---|---|---|---|---|
| Endpoint Service Tag | `ece_service_tag` | Yes | — | Service tag of the NativeEdge Endpoint where this VM will be deployed |
| VM Name | `vm_name` | Yes | `edge-cloud-init-02` | Name of the Virtual Machine |
| VM Hostname | `vm_hostname` | Yes | `edgehost2` | Hostname (letters, numbers, hyphens only; max 63 chars) |
| vCPUs | `vcpus` | Yes | `2` | Number of virtual CPUs (minimum 2) |
| Memory Size | `memory_size` | Yes | `4GB` | RAM allocation — value + unit (e.g. `8GB`) |
| OS Disk Size | `os_disk_size` | Yes | `50GB` | OS disk size — value + unit (e.g. `100GB`) |
| Datastore Path | `disk` | Yes | `/DataStore0` | Datastore path on the target Endpoint |
| Primary Network Segment | `segment_name` | Yes | — | Virtual Network Segment name for the primary NIC |
| Use DHCP | `use_dhcp` | Yes | `true` | Use DHCP for the primary NIC. If false, static_ip is required |
| Static IP/CIDR | `static_ip` | No | — | Static IP/CIDR (e.g. `192.168.0.100/24`). Required when DHCP is disabled |
| Use Gateway | `use_gateway` | No | `false` | Configure a default gateway for the primary NIC |
| Gateway | `gateway` | No | — | Gateway IP address (e.g. `192.168.0.1`) |
| Use DNS | `use_dns` | No | `false` | Configure DNS servers for the primary NIC |
| DNS Servers | `dns` | No | — | Comma-separated DNS server IPs (e.g. `8.8.8.8,8.8.4.4`) |

**Additional VM NIC Configuration Fields:**

| Display Name | Field Name | Required | Default | Description |
|---|---|---|---|---|
| VM Name | `vm_name` | Yes | — | VM Name to correlate this NIC with an additional VM entry |
| NIC Label | `nic_name` | Yes | `nic2` | Unique label for this NIC entry (e.g. "NIC 2") |
| Segment Name | `segment_name` | Yes | — | Name of the Virtual Network Segment to attach this NIC to |
| Use DHCP | `use_dhcp` | Yes | `true` | Use DHCP for this NIC. If false, static_ip is required |
| Accept DHCP Routes | `accept_dhcp_routes` | No | `false` | Accept gateway/routes from DHCP server (default: false) |
| Static IP/CIDR | `static_ip` | No | — | Static IP/CIDR (e.g. `192.168.0.100/24`). Required when DHCP is disabled |
| Use Gateway | `use_gateway` | No | `false` | Configure a static route for this NIC |
| Gateway IP | `gateway` | No | — | Gateway IP address for the static route |
| Route Destination (CIDR) | `route_destination` | No | — | Destination subnet in CIDR (e.g. `10.20.0.0/16`). Do not use `0.0.0.0/0` |
| Use DNS | `use_dns` | No | `false` | Configure DNS servers for this NIC |
| DNS Servers | `dns` | No | — | Comma-separated DNS server IPs (e.g. `8.8.8.8,8.8.4.4`) |
| Enable NAT | `use_nat` | No | `false` | Enable NAT port forwarding for this NIC |
| Port Forward Rules (JSON) | `port_forward_rules` | No | — | JSON-formatted port forwarding rules as a string |

**Additional VM Disk Configuration Fields:**

| Display Name | Field Name | Required | Default | Description |
|---|---|---|---|---|
| VM Name | `vm_name` | Yes | — | VM Name to correlate this disk with an additional VM entry |
| Name | `name` | Yes | `vdisk2` | Unique name to identify the virtual disk |
| Disk Path | `disk` | Yes | `/DataStore0` | The /DataStore path where the virtual disk will be created |
| Storage Size | `storage` | Yes | `16` | The size of the virtual disk, specified as an integer value |
| Storage Unit | `storage_unit` | Yes | `GB` | The unit of measurement for the disk size |

**Additional VM Passthrough Device Configuration Fields:**

| Display Name | Field Name | Required | Description |
|---|---|---|---|
| VM Name | `vm_name` | Yes | VM Name to correlate this passthrough device with an additional VM entry |
| Device Type | `device_type` | Yes | Type of passthrough device: `usb`, `serial_port`, `gpu`, `video`, `pcie` |
| Device | `device` | Yes | Device logical name or identifier. For serial ports, use PORT_MODE format (e.g. `COM-1_RS-232`) |

---

## Outputs / Capabilities

After a successful deployment, the following values are available as environment capabilities:

### Base VM Outputs

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

### Additional VM Outputs

When deploying additional VMs, the following outputs are available:

| Output | Description |
|---|---|
| `base_vm` | Base VM details and configuration |
| `additional_vm` | Additional VM details keyed by VM name |

The `additional_vm` capability contains a dictionary where each key is the VM name and the value includes:
- VM name and hostname
- Primary IP address
- Endpoint service tag
- Network interface details
- SSH access information

Access individual VM information using the VM name as the key in the `additional_vm` capability.

---

## Network Interface Layout

The VM interfaces are assigned in the following deterministic order:

| Interface | Role |
|---|---|
| `enp1s0` | Primary NIC (`vnic_0_segment_name`) |
| `enp2s0` … `enp{N+1}s0` | Additional NICs (in order of the `additional_nics` list) |
| `enp{N+2}s0` | Management / tap interface (infrastructure segment, always present) |

---

## Multi-VM Deployment

The blueprint supports deploying multiple VMs from a single deployment, enabling complex edge computing scenarios with distributed workloads.

### Overview

Deploy a base VM plus up N additional VMs with the following capabilities:

- **Cross-Endpoint Deployment**: Each additional VM can be deployed on different NativeEdge Endpoints
- **Independent Configuration**: Per-VM resource allocation, networking, and storage settings
- **Scalable Architecture**: Use scaling policies to dynamically adjust the number of additional VMs
- **Resource Correlation**: Associate NICs, disks, and devices with specific VMs using VM names

### Deployment Requirements

- **Utility Blueprint**: The `edge-cloudinit-utility-vm` blueprint must be uploaded to the platform
- **Multiple Endpoints**: For cross-endpoint deployments, ensure all target endpoints are onboarded
- **Resource Planning**: Verify sufficient resources (CPU, memory, storage) on target endpoints
- **Network Segments**: Ensure required network segments exist on all target endpoints

### VM Correlation Mechanism

Resources are correlated with VMs using the following mechanisms:

- **VM Name**: Primary correlation key for NICs, disks, and passthrough devices
- **Endpoint Service Tag**: Identifies the target endpoint for each VM
- **Scaling Policy**: Controls the number of VM instances deployed

### Scaling Configuration

The blueprint uses a scaling policy with the following parameters:

- **Default Instances**: Automatically calculated from the length of `additional_vm` list
- **Minimum Instances**: 0 (no additional VMs)
- **Target Group**: `add_vm_group` (includes VM preparation and deployment components)

The number of VM instances is dynamically determined by the number of entries in the `additional_vm` configuration list, eliminating the need for manual count management.

### Deployment Order

1. **Base VM**: Deployed first with primary configuration
2. **Additional VMs**: Deployed in parallel after base VM completion
3. **Resource Collection**: VM information gathered and made available as capabilities
4. **Result Aggregation**: All VM results compiled into structured outputs

### Cross-Endpoint Considerations

When deploying VMs across multiple endpoints:

- **Network Connectivity**: Ensure endpoints can communicate if required
- **Resource Availability**: Verify each endpoint has sufficient resources
- **Security Policies**: Apply appropriate security policies per endpoint
- **Monitoring**: Configure monitoring for distributed VM deployments

---

## Usage Examples

### Single VM Deployment

Deploy a single VM with basic configuration:

```yaml
vm_name: "edge-cloud-init-01"
vm_hostname: "edgehost"
vcpus: 2
memory_size: "4GB"
os_disk_size: "50GB"
vnic_0_segment_name: "management-segment"
use_dhcp: true
```

### Multi-VM Deployment on Single Endpoint

Deploy base VM plus 2 additional VMs on the same endpoint:

```yaml
additional_vm:
  - ece_service_tag: "endpoint-001"
    vm_name: "edge-cloud-init-02"
    vm_hostname: "edgehost2"
    vcpus: 2
    memory_size: "4GB"
    os_disk_size: "50GB"
    segment_name: "management-segment"
    use_dhcp: true
  - ece_service_tag: "endpoint-001"
    vm_name: "edge-cloud-init-03"
    vm_hostname: "edgehost3"
    vcpus: 4
    memory_size: "8GB"
    os_disk_size: "100GB"
    segment_name: "data-segment"
    use_dhcp: false
    static_ip: "10.10.0.50/24"
    use_gateway: true
    gateway: "10.10.0.1"
```

### Cross-Endpoint Multi-VM Deployment

Deploy VMs across different endpoints with network and disk configurations:

```yaml
additional_vm:
  - ece_service_tag: "endpoint-001"
    vm_name: "web-server-01"
    vm_hostname: "webhost01"
    vcpus: 2
    memory_size: "4GB"
    segment_name: "web-segment"
    use_dhcp: true
  - ece_service_tag: "endpoint-002"
    vm_name: "database-01"
    vm_hostname: "dbhost01"
    vcpus: 4
    memory_size: "16GB"
    os_disk_size: "100GB"
    segment_name: "db-segment"
    use_dhcp: false
    static_ip: "192.168.10.100/24"

add_vm_nics: true
add_vm_add_nics:
  - vm_name: "database-01"
    nic_name: "backup-nic"
    segment_name: "backup-segment"
    use_dhcp: true
  - vm_name: "web-server-01"
    nic_name: "data-nic"
    segment_name: "data-segment"
    use_dhcp: false
    static_ip: "10.20.0.200/24"

add_vm_disks: true
add_vm_add_disks:
  - vm_name: "database-01"
    name: "data-disk"
    disk: "/DataStore0"
    storage: 500
    storage_unit: "GB"
  - vm_name: "web-server-01"
    name: "log-disk"
    disk: "/DataStore0"
    storage: 100
    storage_unit: "GB"
```

### Device Passthrough Configuration

Configure device passthrough for additional VMs:

```yaml
add_vm_passthrough: true
add_vm_passthrough_devices:
  - vm_name: "gpu-workstation-01"
    device_type: "gpu"
    device: "nvidia-gpu-001"
  - vm_name: "serial-device-01"
    device_type: "serial_port"
    device: "COM-1_RS-232"
  - vm_name: "usb-device-01"
    device_type: "usb"
    device: "usb-device-001"
```

---

## Notes

- The SSH keypair is generated automatically at deploy time. The private key is stored as a platform secret and referenced by the `vm_ssh_private_key` output. If you preffer your own ssh-key pair, create `general` type secrets containing the values name `edge_key_public` and `edge_key_private` respectively.
- The management tap interface is always provisioned regardless of `additional_nics` configuration, and always occupies the last `enp*s0` interface slot.
- `accept_dhcp_routes` on additional NICs defaults to `false` to prevent unintended default route conflicts with the primary NIC.
- **Multi-VM Considerations**: Each additional VM requires a unique `vm_name` within the deployment. VM names are used as correlation keys for NICs, disks, and passthrough devices.
- **Resource Planning**: Ensure target endpoints have sufficient resources for all planned VMs, especially when deploying multiple VMs with high resource requirements.
- **Network Segments**: Verify that all required network segments exist on target endpoints before deploying multi-VM configurations.
- **Automatic Scaling**: The number of VM instances is automatically calculated from the `additional_vm` list length. For larger deployments, consider multiple blueprint deployments.
