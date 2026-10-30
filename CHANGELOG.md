# Changelog for edge-cloudinit-linux

All notable changes to this blueprint are recorded here. The version is also
the catalog revision to upload the blueprint as (see the README).

## 1.2.0.0 - unreleased

Deployment updates (Day-2). Needs `edge-cloudinit-utility-vm` 1.2.0.0 or a
later 1.x revision.

- Added: `utility_blueprint_revision` (default 1.2.0.0) pins the utility
  blueprint revision the VMs use. Before, every update moved the VMs to the
  newest utility revision in the catalog, even with no change, so uploading a
  new utility revision changed running VMs. To move to a newer utility
  revision, update this input.
- Fixed: an update with no change still updated every VM. The VM components
  received null for hidden inputs (passthrough lists, additional disks),
  which never matched the utility deployment's stored values. They now
  receive explicit values.
- Fixed: a changed segment or NAT rule never reached the VM. These were
  computed once at install by `prep_config`; they are now computed from the
  inputs on every update (VMs 2-10 too: each picks its own settings by VM
  name). `prep_config` and `add_vm_prep_config` report no drift, so an update
  never re-runs them.
- Fixed: the cloud-init password hash changed on every run of `prep_config`
  (new random salt), which made the VMs' cloud-init look changed. The salt is
  now derived from the deployment ID.
- Fixed: the aggregated `base_vm` / `additional_vm` capabilities are read
  from the VM deployments again after an update.
- Fixed: in the update form, VM 2-10 static IP, gateway and DNS fields could
  show for VMs that don't exist, prefilled with "null", and block the form.
  They are now hidden with their VM, and the IP patterns accept the stored
  null values.
- Added: `update_checks` fails an update that would shrink a VM's OS disk or
  an additional disk ("Disks can only grow"), with the VMs left as they are.
  With "Run automatic reinstall" the Endpoint's refusal used to make the
  orchestrator delete and recreate the VM.
- Changed: only inputs that a running VM can apply are updatable: vCPUs,
  memory, OS disk size (grow only), primary segment, NAT port forwarding and
  additional disks (base VM and VMs 2-10), plus the utility revision.
  Everything set by cloud-init or at creation (names, OS image, user,
  password, IP settings, number of VMs, additional NICs, passthrough, disk
  controller) is locked. See "Updating a deployment" in the README.
- Changed: every input constraint has an error message; list inputs declare
  their item type. `CHANGELOG.yaml` is now `CHANGELOG.md`.

## 1.1.0.4

- Populate base and additional VM aggregate capabilities with non-sensitive VM
  details from current utility VM capability fields.

## 1.1.0.3

- Return the VM password secret name from capabilities instead of exposing its
  resolved plaintext value.

## 1.1.0.2

- Handle null optional list inputs during single-VM and multi-VM configuration
  preparation.
- Centralize plugin imports and resolve the binary image access token directly
  from its typed secret.

## 1.1.0.1

- Baseline release for DDPC EdgeOS 4.2.0.0 compatibility.
