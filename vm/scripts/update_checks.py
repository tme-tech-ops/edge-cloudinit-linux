"""Refuses an update that asks a VM for something the Endpoint can't do.

Runs as check_drift, so it fails the update in the drift-check phase, before
any node changes. That matters with "Run automatic reinstall": a VM update the
Endpoint refuses (a smaller disk) would otherwise make the orchestrator delete
and recreate the VM.

Checks, per VM: the OS disk and existing additional disks don't shrink. The
requested sizes come from the operation inputs (evaluated with the update's
new inputs); the current ones from the VM's utility deployment. Read-only.
"""
import re

from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.manager import get_rest_client
from dell.state import ctx_parameters as inputs

UNITS = {"KB": 2**10, "MB": 2**20, "GB": 2**30, "TB": 2**40, "PB": 2**50}


def to_bytes(size, unit=None):
    if size is None:
        return None
    if unit:
        size = f"{size}{unit}"
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGTP]B)\s*", str(size).upper())
    return int(float(match.group(1)) * UNITS[match.group(2)]) if match else None


def disk_sizes(disks):
    return {d.get("name"): to_bytes(d.get("storage"), d.get("storage_unit") or "GB")
            for d in disks or [] if isinstance(d, dict)}


def children(client):
    """{vm name: utility deployment inputs} for this deployment's VM components."""
    found = {}
    for node_id in ("base_vm", "add_vm"):
        for inst in client.node_instances.list(deployment_id=ctx.deployment.id, node_id=node_id):
            child_id = ((inst.runtime_properties or {}).get("deployment") or {}).get("id")
            if not child_id:
                continue
            child = client.deployments.get(child_id, _include=["id", "inputs"])
            found[(child.inputs or {}).get("name")] = child.inputs or {}
    return found


def main():
    vms = [inputs.get("base") or {}] + list(inputs.get("others") or [])
    requested = {vm.get("name"): vm for vm in vms if vm.get("name")}
    problems = []
    for name, current in children(get_rest_client()).items():
        want = requested.get(name)
        if not want:
            continue
        new, old = to_bytes(want.get("storage")), to_bytes(current.get("storage"))
        if new is not None and old is not None and new < old:
            problems.append(f"{name}: OS disk {current.get('storage')} -> {want.get('storage')}")
        new_disks = disk_sizes(want.get("disks") if want.get("add_disks") else [])
        for disk, old_size in disk_sizes(current.get("additional_disks")).items():
            new_size = new_disks.get(disk)
            if new_size is not None and old_size is not None and new_size < old_size:
                problems.append(f"{name}: disk {disk} {old_size // 2**30}GB -> {new_size // 2**30}GB")
    if problems:
        raise NonRecoverableError(
            "Disks can only grow (the Endpoint refuses to shrink them): " + "; ".join(problems)
            + ". Nothing was changed; update again with sizes at least as large as now.")
    ctx.logger.info("update checks: passed")
    ctx.returns(None)


main()
