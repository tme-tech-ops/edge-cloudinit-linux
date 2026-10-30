from nativeedge import ctx
from nativeedge.manager import get_rest_client


def get_vm_name(caps):
    vm_config = caps.get('vm_config') or {}
    return caps.get('vm_name') or vm_config.get('name') or caps.get('vm_name_id') or ''


def child_capabilities(client, inst):
    """The child deployment's current capabilities.

    The component's own copy (runtime property 'capabilities') is written at
    install and not refreshed by an update, so read the child directly and fall
    back to the copy if that fails.
    """
    caps = inst.runtime_properties.get('capabilities', {}) or {}
    child_id = (inst.runtime_properties.get('deployment') or {}).get('id')
    if child_id:
        try:
            caps = client.deployments.capabilities.get(child_id).get(
                'capabilities') or caps
        except Exception as err:
            ctx.logger.warning(
                f"Capabilities of {child_id} not readable ({err}); using the copy")
    return caps


def build_vm_entry(caps, vm_name):
    """Build a standardized VM result dict from ServiceComponent capabilities."""
    return {
        'name': vm_name,
        'name_id': caps.get('vm_name_id', ''),
        'service_tag': caps.get('service_tag', ''),
        'hostname': caps.get('vm_hostname', ''),
        'primary_ip': caps.get('vm_primary_ip', ''),
        'tap_ip': caps.get('tap_ip', ''),
        'additional_nics': caps.get('vm_add_nics', 'N/A'),
        'additional_disks': caps.get('vm_add_disks') or [],
        'passthrough': caps.get('vm_add_passthrough') or {},
    }


if __name__ == "__main__":
    client = get_rest_client()

    # Collect base VM results
    base_instances = client.node_instances.list(
        deployment_id=ctx.deployment.id,
        node_id='base_vm'
    )
    base_vm = {}
    for inst in base_instances:
        caps = child_capabilities(client, inst)
        vm_name = get_vm_name(caps)
        if vm_name:
            base_vm[vm_name] = build_vm_entry(caps, vm_name)
            break

    ctx.instance.runtime_properties['base_vm'] = base_vm

    # Collect additional VM results
    add_instances = client.node_instances.list(
        deployment_id=ctx.deployment.id,
        node_id='add_vm'
    )
    sorted_instances = sorted(add_instances, key=lambda ni: ni.id)

    additional_vm = {}
    for inst in sorted_instances:
        caps = child_capabilities(client, inst)
        vm_name = get_vm_name(caps)
        if vm_name:
            additional_vm[vm_name] = build_vm_entry(caps, vm_name)

    ctx.instance.runtime_properties['additional_vm'] = additional_vm
    ctx.instance.update()

    ctx.logger.info(
        f"Collected base VMs: {list(base_vm.keys())}, "
        f"additional VMs: {list(additional_vm.keys())}"
    )
