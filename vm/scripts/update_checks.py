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

It also warns, at the start of an update, when an app deployed on a VM will
block it (see force_warnings). Warnings never fail the update.

The same script runs as check_drift, update and create (ctx.operation.name).
"""
import re

from dell import ctx
from dell.exceptions import NonRecoverableError
from dell.manager import get_rest_client
from dell.state import ctx_parameters as inputs

ACTIVE = ("pending", "queued", "started", "scheduled")
UNITS = {"KB": 2**10, "MB": 2**20, "GB": 2**30, "TB": 2**40, "PB": 2**50}
END_STATES = ("deployed", "uninstalled", "uninstall_cancelled", "install_cancelled")


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


def updating(client):
    return any(e.get("workflow_id") == "update" and e.get("status") in ACTIVE
               for e in client.executions.list(deployment_id=ctx.deployment.id,
                                                _include=["workflow_id", "status"]))


def vm_deployments(client):
    """Ids of this deployment's VM deployments (the utility components)."""
    found = []
    for node_id in ("base_vm", "add_vm"):
        for inst in client.node_instances.list(deployment_id=ctx.deployment.id, node_id=node_id):
            child_id = ((inst.runtime_properties or {}).get("deployment") or {}).get("id")
            if child_id:
                found.append(child_id)
    return found


def applied_configs(client, children):
    """{vm name: expected_configuration} of this deployment's VMs."""
    found = {}
    for child_id in children:
        for vm in client.node_instances.list(deployment_id=child_id, node_id="vm"):
            config = (vm.runtime_properties or {}).get("expected_configuration") or {}
            if config.get("name"):
                found[config["name"]] = config
    return found


def problem(client, children):
    vms = [inputs.get("base") or {}] + list(inputs.get("others") or [])
    requested = {vm.get("name"): vm for vm in vms if vm.get("name")}
    found = []
    for name, applied in applied_configs(client, children).items():
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


def changes_something(record):
    """Does the update change an input or the blueprint? The record's new_inputs
    hold only the inputs the update sent; old_inputs hold all of them."""
    old, new = record.get("old_inputs") or {}, record.get("new_inputs") or {}
    return (any(old.get(name) != value for name, value in new.items())
            or record.get("old_blueprint_id") != record.get("new_blueprint_id")
            or record.get("old_blueprint_version") != record.get("new_blueprint_version"))


def needs_repair(deployment):
    """Would the component heal this VM deployment before updating it? Same
    rule as its check_status (validate_deployment_status)."""
    return (deployment.get("installation_status") != "active"
            or deployment.get("deployment_status") not in END_STATES
            or deployment.get("latest_execution_status") == "failed"
            or (deployment.get("unavailable_instances") or 0) > 0
            or (deployment.get("drifted_instances") or 0) > 0)


def force_warnings(client, children):
    """Apps deployed on a VM (its utility deployment is their "Deploy On"
    target) block that VM's update unless the update has Force, and block the
    repair (heal) of a failed VM deployment even with Force: the parent doesn't
    pass Force to a heal. DAP refuses either one and the parent retries for
    about 20 minutes before the update fails, so say it at the start."""
    params = client.executions.get(ctx.execution_id).parameters or {}
    record = {}
    if params.get("update_id"):
        record = client.deployment_updates.get(params["update_id"], _include=[
            "old_inputs", "new_inputs", "old_blueprint_id", "new_blueprint_id",
            "old_blueprint_version", "new_blueprint_version"])
    changes = changes_something(record) if record else True
    warnings = []
    for child_id in children:
        apps = client.deployments.list(_include=["id", "display_name"], filter_rules=[
            {"key": "csys-obj-parent", "values": [child_id], "operator": "any_of", "type": "label"}])
        if not apps:
            continue
        child = client.deployments.get(child_id, _include=[
            "id", "display_name", "installation_status", "deployment_status",
            "latest_execution_status", "unavailable_instances", "drifted_instances"])
        name = child.get("display_name") or child_id
        on_it = ", ".join(app.get("display_name") or app.get("id") for app in apps)
        if needs_repair(child):
            warnings.append(
                f"The VM deployment {name} needs a repair and has {on_it} deployed on it. DAP "
                f"refuses that repair (heal) while an app is deployed on it, even with Force, so if "
                f"this update changes that VM it fails after about 20 minutes. Cancel this update, "
                f"run Heal with Force on {name}, then update again.")
        elif changes and not params.get("force"):
            warnings.append(
                f"{on_it} is deployed on the VM deployment {name}. If this update changes that VM, "
                f"it needs Force: DAP refuses it otherwise and the update fails after about 20 "
                f"minutes. Cancel this update and run it again with Force ticked (Advanced).")
    return warnings


def main():
    op = ctx.operation.name.split(".")[-1]
    reason = None
    try:
        client = get_rest_client()
        if updating(client):  # not install, nor the check_drift workflow
            children = vm_deployments(client)
            reason = problem(client, children)
            if op == "check_drift" and not reason:
                try:
                    for warning in force_warnings(client, children):
                        ctx.logger.warning(f"update checks: {warning}")
                except Exception as err:
                    ctx.logger.warning(f"update checks: could not check the apps on the VMs ({err})")
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
