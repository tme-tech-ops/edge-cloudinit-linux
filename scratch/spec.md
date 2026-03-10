# Multi-vm deployment update

# Context
This blueprint package deploys a virtual machine on a NativeEdge endpoint using a cloud-init image. NativeEdge is a Subset of Dell Automation Platform, which is a subset of Cloudify and leverages TOSCA dell_1_1 defenitions, similar to Cloudify.
The VM defenitions provide complex configuration presented in a simplified UI using input_groups. Deploy a simple VM, or deploy a complex VM with secure boot, multiple disks, and multiple interfaces.

# Goal
- Update this blueprint package to allow the user to OPTIONALLY deploy an additional N amount of VMs on different or the same endpoints.
- Leverage scaling groups and policies to manage the scaling of nodes based off the user inputs
- Provide new capabilities for each new VM that mimics the original VM
- Keep the user inputs as simplistic as possible.

# Things to keep in mind
- The UI must be relatively easy to use, such as using a set of common VM inputs to keep the input count down.
- For defining the N amount of additonal VMs, a custom data_types could be used to build a list of parameters. One data_type for 'vm resources' i.e. CPU, Memory, Disk Size, 'network config' dhcp, CIDR, etc.
- use the multi-node directory for adding the additonal definitions, inputs, and capabilities.
- Ensure the edge-cloudinit-linux.yaml is updated to include any new input_groups needed as well as importing the files from the multi-node directory.

# Resources to leverage for planning
- the 'scratch' directory contains references to the plugins used by this blueprint.
- The 'vm' directory contains the existing edge-cloud-init-linux blueprint logic which successfully deploys a single virtual machine on a nativeedge endpoint.
- the blueprint_reference directory contains an example ServiceComponent blueprint, which also deploys a NativeEdge VM. this can be referenced as an example if needed.

# IMPORTANT NOTES
- the initial VM gets its inventory from 'get_environment_capability' which will only work for the first VM. All optional VMs must leverage the ece_service_tag string as their NativeEdgeVM location (target).
- This also means the 'proxy_settings' used by vm_info will need to leverage different inputs to lookup the VM. We can determine a better way to get the proxty settings, such as referencing the get_proxy.py script.


# PHASE 1 - Initial multi-VM update

**Problem:** The blueprint only supported deploying a single VM. Users needed the ability to deploy additional VMs on the same or different NativeEdge endpoints from a single deployment.

**Solution:** Added a scaling group with `dell.policies.scaling` that pairs a prepare_config node (determines instance index, reads per-VM config from a list input) with VM nodes. A custom `additional_vm_config` data_type provides a clean UI for per-VM settings (service tag, name, hostname, resources, network).

**Files changed/added:**
- `multi-node/inputs.yaml` — New inputs: `deploy_additional_vms`, `additional_server_count`, `additional_vms` list with `additional_vm_config` data_type
- `multi-node/definitions.yaml` — Scaling group node templates and policy (0-9 instances)
- `multi-node/outputs.yaml` — Capabilities for additional VM details
- `multi-node/scripts/prepare_additional_vm.py` — Determines instance index via REST API, extracts per-VM config from list
- `edge-cloudinit-linux.yaml` — Added multi-node imports and `multi_node` input group

# PHASE 2 - Switch to ServiceComponent + Child Blueprint

**Problem:** Additional VMs deployed within the scaling group did not appear as separate deployments in the NativeEdge Orchestrator UI. The Deployments column showed 0 and per-VM capabilities were not individually visible.

**Solution:** Refactored to use `dell.nodes.ServiceComponent` which creates a child deployment per additional VM. A separate child blueprint handles single-VM deployment (cloud-init, proxy resolution, VM creation, VM info collection). The parent's prepare_config node now builds the complete cloud-init dict and passes it to the child via ServiceComponent inputs. Each child deployment is independently visible in the UI with its own capabilities.

**Files changed/added:**
- `multi-node/child-blueprint/vm.yaml` — Child blueprint entry point
- `multi-node/child-blueprint/vm/inputs.yaml` — Child inputs (service_tag, name, image, resources, network, cloudinit, etc.)
- `multi-node/child-blueprint/vm/outputs.yaml` — Child capabilities (vm_name, vm_primary_ip, tap_ip, etc.)
- `multi-node/child-blueprint/vm/blueprint.yaml` — Child node templates: cloudinit, proxy_resolver, vm, vm_info
- `multi-node/child-blueprint/vm/scripts/get_proxy.py` — Resolves proxy target_id from inventory service using service_tag
- `multi-node/child-blueprint/vm/scripts/get_vm_info.sh` — Collects VM IP info via fabric SSH
- `multi-node/definitions.yaml` — Replaced direct VM nodes with ServiceComponent referencing child blueprint
- `multi-node/scripts/prepare_additional_vm.py` — Expanded to build netplan YAML and complete cloud-init config dict
- `multi-node/inputs.yaml` — Added `child_blueprint_id` input
- `multi-node/outputs.yaml` — Updated to read from ServiceComponent capabilities
- `edge-cloudinit-linux.yaml` — Added `child_blueprint_id` to input group

# PHASE 3 - Post-Deploy Fixes (Dependency, Outputs, Child Rename)

**Problem:** Three issues found after successful Phase 2 deployment: (1) `additional_server_prepare_config` unnecessarily waited for the primary VM to deploy before starting, preventing parallel execution. (2) Parent output capabilities using `get_attribute` on scaled ServiceComponent instances did not resolve correctly. (3) Child blueprint's `vm_name` capability needed to be `vm_name_id` to align with the primary VM and upstream blueprints.

**Solution:** Removed the false `depends_on: vm` relationship so the scaling group runs in parallel with primary VM deployment. Added a singleton `additional_server_results` aggregator node (outside the scaling group) that queries all ServiceComponent instances via REST API after child deployments complete, collecting capabilities into a single correlated dict keyed by `vm_name_id`. Renamed the child capability to `vm_name_id`.

**Files changed/added:**
- `multi-node/definitions.yaml` — Removed `vm` dependency from `additional_server_prepare_config`; added `additional_server_results` aggregator node
- `multi-node/scripts/collect_additional_vm_results.py` — New aggregator script that queries all `additional_server_vm` instances and builds correlated dict
- `multi-node/outputs.yaml` — Replaced 5 separate capabilities with single `additional_vms` dict capability
- `multi-node/child-blueprint/vm/outputs.yaml` — Renamed `vm_name` capability to `vm_name_id`

# PHASE 4 - Naming Refactor, Flat Data Types, and Additional Disk Support

**Problem:** (1) Node template, input, and capability names were inconsistent and verbose (e.g. `additional_server_prepare_config`, `additional_nics`). (2) Nested `vm_nic_config` data_type inside `additional_vm_config` didn't render properly in the NativeEdge UI. (3) Additional VMs had no support for extra virtual disks. (4) NIC/disk correlation by `ece_service_tag` would fail when multiple VMs share the same endpoint.

**Solution:** Standardized all names across the blueprint (e.g. `add_vm_prep_config`, `add_vm`, `vm_add_nics`, `prep_config`). Replaced nested NIC data_type with three separate top-level data_types following the main VM pattern: `add_vm_config` (per-VM config with flat primary NIC fields and boolean toggles), `add_vm_add_nic_config` (additional NICs with full feature parity), and `add_vm_add_disks` (additional disks). Each NIC/disk list has a boolean toggle input for UI show/hide. The prepare script correlates additional NICs and disks to VMs by `vm_name` (not `ece_service_tag`) to support multiple VMs on the same endpoint. Added `additional_disks` pass-through from parent to child blueprint.

**Files changed/added:**
- `multi-node/inputs.yaml` — Renamed `additional_vm_config` to `add_vm_config` with flat primary NIC fields; added `add_vm_add_nic_config` and `add_vm_add_disks` data_types; added 4 new inputs with boolean toggles; removed nested `vm_nic_config`
- `multi-node/definitions.yaml` — All node/group/policy renames; added `add_vm_add_nics` and `add_vm_add_disks` inputs to prep node; added `additional_disks` mapping to ServiceComponent
- `multi-node/scripts/prepare_additional_vm.py` — Full rewrite: correlates 3 input lists by `vm_name`, builds network_settings with NAT support, netplan with full NIC features, disk list processing, validation matching main VM logic
- `multi-node/scripts/collect_additional_vm_results.py` — Renamed node_id and property keys
- `multi-node/outputs.yaml` — Renamed capability and node reference
- `multi-node/child-blueprint/vm/inputs.yaml` — Added `additional_disks` input
- `multi-node/child-blueprint/vm/blueprint.yaml` — Changed `additional_disks: []` to `{ get_input: additional_disks }`
- `multi-node/child-blueprint/vm/scripts/get_vm_info.sh` — Renamed `additional_nics_ips` to `vm_add_nics_ips`
- `vm/definitions.yaml` — Renamed `prepare_config` to `prep_config`, `additional_nics` to `vm_add_nics`
- `vm/inputs.yaml` — Renamed input and data_type
- `vm/outputs.yaml` — Renamed capabilities
- `vm/scripts/prepare_network_settings.py` — Renamed dict key
- `vm/scripts/prepare_netplan_config.py` — Renamed dict keys
- `vm/templates/netplan_config.yaml` — Renamed Jinja2 variable
- `vm/scripts/get_vm_info.sh` — Renamed runtime property
- `edge-cloudinit-linux.yaml` — Added 4 new inputs to `multi_node` group; renamed input references

# PHASE 5 - Fix Proxy Resolution for Child VM Sub-Services

**Problem:** When deploying an upstream blueprint (e.g. object-tech-ops) as a sub-service of a child VM deployment, SSH connections fail with `Error reading SSH protocol banner`. The fabric plugin's `resolve_internal_proxy` uses `ctx.deployment.id` to resolve the proxy endpoint. For ServiceComponent child deployments, this falls back to the parent deployment's endpoint context instead of using the `service_tag` from `proxy_settings`. The child VM exists on a different endpoint, so the proxy tunnel routes to the wrong host.

**Solution:** Added a `proxy_resolver` node to the base VM blueprint (matching the child blueprint's existing pattern) that explicitly resolves the `target_id` from the inventory service using `get_proxy.py`. Both the base VM and child VM now expose a `proxy_target_id` capability. Updated the object-tech-ops blueprint to use `auto_resolve: false` with the explicit `target_id` from `get_environment_capability: proxy_target_id`, bypassing the faulty auto-resolution entirely.

**Files changed/added:**
- `vm/scripts/get_proxy.py` — New file (copied from child blueprint): resolves target_id from inventory service using service_tag, sets `_proxy_target_id` and `connection_proxy_settings` runtime properties
- `vm/definitions.yaml` — Added `proxy_resolver` node (runs `get_proxy.py` with `get_environment_capability: ece_service_tag`); updated `get_vm_info` proxy_settings from `auto_resolve: true` + `service_tag` to `auto_resolve: false` + explicit `target_id`; added `proxy_resolver` dependency to `vm_info`
- `vm/outputs.yaml` — Added `proxy_target_id` capability
- `multi-node/child-blueprint/vm/outputs.yaml` — Added `proxy_target_id` capability
- `scratch/blueprint_reference/object-tech-ops/tech-ops/definitions.yaml` — Changed all 6 `proxy_settings` blocks from `service_tag`-based auto-resolution to `auto_resolve: false` + `target_id: { get_environment_capability: proxy_target_id }`

# PHASE 6 - Add Device Passthrough Inputs for Additional VMs

**Problem:** The child blueprint already supported USB, serial port, GPU, video, and PCIe host/device passthrough inputs (including a `format_serial_ports` node for serial port transformation), but the upstream `add_vm` ServiceComponent did not pass these inputs through. Additional VMs could not use device passthrough.

**Solution:** Added a unified `add_vm_passthrough_config` data type with a `device_type` discriminator field (`usb`, `serial_port`, `gpu`, `video`, `pcie`), following the `add_vm_add_disks` vm_name-correlation pattern. Each list entry represents one device for one VM. The `prepare_additional_vm.py` script filters entries by `vm_name` and groups by `device_type` to build per-type device lists, which are passed through the ServiceComponent to the child blueprint.

**Files changed/added:**
- `multi-node/inputs.yaml` — Added `add_vm_passthrough` boolean toggle, `add_vm_passthrough_devices` list input (item_type: `add_vm_passthrough_config`), and `add_vm_passthrough_config` data type (vm_name, device_type, device)
- `multi-node/scripts/prepare_additional_vm.py` — Added `build_passthrough_devices()` helper that groups entries by device_type; filters passthrough entries by vm_name per instance; sets `usb`, `serial_port`, `gpu`, `video`, `pcie` runtime properties
- `multi-node/definitions.yaml` — Passes `add_vm_passthrough_devices` input to prep script; passes all 5 device-type lists from `add_vm_prep_config` to the child ServiceComponent
- `edge-cloudinit-linux.yaml` — Added `add_vm_passthrough` and `add_vm_passthrough_devices` to `multi_node` input group