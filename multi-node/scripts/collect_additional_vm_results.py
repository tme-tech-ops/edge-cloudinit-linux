from nativeedge import ctx
from nativeedge.manager import get_rest_client


if __name__ == "__main__":
    client = get_rest_client()

    instances = client.node_instances.list(
        deployment_id=ctx.deployment.id,
        node_id='additional_server_vm'
    )

    sorted_instances = sorted(instances, key=lambda ni: ni.id)

    additional_vms = {}
    for inst in sorted_instances:
        caps = inst.runtime_properties.get('capabilities', {})
        vm_name_id = caps.get('vm_name_id', '')
        if vm_name_id:
            additional_vms[vm_name_id] = {
                'service_tag': caps.get('service_tag', ''),
                'hostname': caps.get('vm_hostname', ''),
                'primary_ip': caps.get('vm_primary_ip', ''),
                'tap_ip': caps.get('tap_ip', ''),
            }

    ctx.instance.runtime_properties['additional_vms'] = additional_vms
    ctx.instance.update()

    ctx.logger.info(
        f"Collected results from {len(sorted_instances)} "
        f"additional_server_vm instances: {additional_vms}"
    )
