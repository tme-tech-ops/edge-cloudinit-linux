"""Makes an update a VM can't apply (a smaller disk) fail visibly.

The utility VM leaves the VM alone when a disk would shrink (the Endpoint
refuses that, and a failed VM update can turn into delete + create of the VM
with "Run automatic reinstall"). This node makes the reason visible: its
check_drift reports it as drift, so its update operation runs and fails with
the reason; with automatic reinstall it is reinstalled instead, and its create
fails with the same reason. The VMs don't change.

Checks, per VM: the OS disk and existing additional disks don't shrink. The
requested sizes come from the operation inputs (evaluated with the update's new
inputs); the current ones from each VM's record of what was last applied
(expected_configuration of the utility deployment's `vm` node).

The same script runs as check_drift, update and create (ctx.operation.name).
"""
import re

from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.manager import get_rest_client
from dell.state import ctx_parameters as inputs

ACTIVE = ("pending", "queued", "started", "scheduled")
UNITS = {"KB": 2**10, "MB": 2**20, "GB": 2**30, "TB": 2**40, "PB": 2**50}


def to_bytes(size, unit=None):
    if isinstance(size, int) and not unit:
        return size
    if unit:
        size = f"{size}{unit}"
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTP]B)\s*", str(size or "").upper())
    return int(float(match.group(1)) * UNITS[match.group(2)]) if match else None


def disk_sizes(disks):
    return {d.get("name"): (d["storage"] if "storage_unit" not in d and isinstance(d.get("storage"), int)
                            else to_bytes(d.get("storage"), d.get("storage_unit") or "GB"))
            for d in disks or [] if isinstance(d, dict)}


def applied_configs(client):
    """{vm name: expected_configuration} of this deployment's VMs."""
    found = {}
    for node_id in ("base_vm", "add_vm"):
        for inst in client.node_instances.list(deployment_id=ctx.deployment.id, node_id=node_id):
            child_id = ((inst.runtime_properties or {}).get("deployment") or {}).get("id")
            if not child_id:
                continue
            for vm in client.node_instances.list(deployment_id=child_id, node_id="vm"):
                config = (vm.runtime_properties or {}).get("expected_configuration") or {}
                if config.get("name"):
                    found[config["name"]] = config
    return found


def problem():
    client = get_rest_client()
    if not any(e.get("workflow_id") == "update" and e.get("status") in ACTIVE
               for e in client.executions.list(deployment_id=ctx.deployment.id,
                                                _include=["workflow_id", "status"])):
        return None  # install, or the check_drift workflow
    vms = [inputs.get("base") or {}] + list(inputs.get("others") or [])
    requested = {vm.get("name"): vm for vm in vms if vm.get("name")}
    found = []
    for name, applied in applied_configs(client).items():
        want = requested.get(name)
        if not want:
            continue
        new = to_bytes(want.get("storage"))
        old = to_bytes((applied.get("resource_constraints") or {}).get("storage"))
        if new and old and new < old:
            found.append(f"{name}: OS disk {old // 2**30}GB -> {new // 2**30}GB")
        new_disks = disk_sizes(want.get("disks") if want.get("add_disks") else [])
        for disk, old_size in disk_sizes(applied.get("additional_disks")).items():
            new_size = new_disks.get(disk)
            if new_size and old_size and new_size < old_size:
                found.append(f"{name}: disk {disk} {old_size // 2**30}GB -> {new_size // 2**30}GB")
    if found:
        return ("Disks can only grow (the Endpoint refuses to shrink them): " + "; ".join(found)
                + ". The VMs were not changed; update again with sizes at least as large as now.")
    return None


def main():
    op = ctx.operation.name.split(".")[-1]
    try:
        reason = problem()
    except Exception as err:  # API not reachable: don't block the update
        ctx.logger.warning(f"update checks: could not check this update ({err})")
        reason = None
    if op == "check_drift":
        if reason:
            ctx.logger.warning(f"update checks: {reason}")
            ctx.returns({"resource_id": "update_checks", "diff_count": 1, "diff": reason})
        else:
            ctx.returns(None)
    elif reason:
        raise NonRecoverableError(reason)
    else:
        ctx.logger.info(f"update checks: {op}: passed")


main()
