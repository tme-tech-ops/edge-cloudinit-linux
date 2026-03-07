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