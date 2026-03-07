import base64
import yaml

from nativeedge import ctx
from nativeedge.exceptions import NonRecoverableError
from nativeedge.state import ctx_parameters as inputs
from nativeedge.manager import get_rest_client


def get_instance_index():
    """Determine this instance's index within the scaling group."""
    client = get_rest_client()
    node_instances = client.node_instances.list(
        deployment_id=ctx.deployment.id,
        node_id=ctx.node.id
    )
    sorted_instances = sorted(node_instances, key=lambda ni: ni.id)
    for i, ni in enumerate(sorted_instances):
        if ni.id == ctx.instance.id:
            return i
    raise NonRecoverableError(
        f"Could not find instance {ctx.instance.id} in node instances list."
    )


def build_network_settings(segment_name):
    """Build network_settings list for a single primary NIC."""
    if not segment_name:
        raise NonRecoverableError(
            "segment_name is required for additional VM network configuration."
        )
    return [{'name': 'VNIC0', 'segment_name': segment_name}]


def build_netplan_yaml(use_dhcp, static_ip, use_gateway, gateway,
                       use_dns, dns_list, mgmt_interface='enp2s0'):
    """Build netplan YAML for a single-NIC VM and return base64 encoded."""
    netplan = {
        'network': {
            'version': 2,
            'renderer': 'networkd',
            'ethernets': {}
        }
    }

    # Primary NIC
    primary = {'dhcp-identifier': 'mac', 'dhcp4': use_dhcp}
    if not use_dhcp:
        if static_ip:
            primary['addresses'] = [static_ip]
        if use_dns and dns_list:
            primary['nameservers'] = {'addresses': dns_list}
        if use_gateway and gateway:
            primary['routes'] = [{'to': 'default', 'via': gateway}]
    netplan['network']['ethernets']['enp1s0'] = primary

    # Management interface (always DHCP, ignore routes)
    netplan['network']['ethernets'][mgmt_interface] = {
        'dhcp4': True,
        'dhcp4-overrides': {'use-routes': False}
    }

    netplan_yaml = yaml.dump(netplan, default_flow_style=False)
    return base64.b64encode(netplan_yaml.encode('utf-8')).decode('utf-8')


def build_cloudinit_config(vm_hostname, vm_user_name, hashed_vm_passwd,
                           ssh_public_key, netplan_b64):
    """Build the complete cloud-init configuration dict."""
    return {
        'hostname': vm_hostname,
        'runcmd': [
            'netplan apply',
            'systemctl restart sshd'
        ],
        'write_files': [
            {
                'content': netplan_b64,
                'encoding': 'b64',
                'path': '/etc/netplan/50-cloud-init.yaml'
            },
            {
                'content': 'ClientAliveInterval 1800\nClientAliveCountMax 3\n',
                'path': '/etc/ssh/sshd_config',
                'append': True
            }
        ],
        'disable_root_opts':
            'no-port-forwarding,no-agent-forwarding,no-X11-forwarding',
        'disable_root': False,
        'ssh_pwauth': True,
        'ssh_authorized_keys': [ssh_public_key],
        'users': [
            {
                'name': vm_user_name,
                'sudo': ['ALL=(ALL) NOPASSWD:ALL'],
                'groups': 'users, admin',
                'passwd': hashed_vm_passwd,
                'lock_passwd': False,
                'shell': '/bin/bash',
                'ssh_authorized_keys': [ssh_public_key]
            }
        ]
    }


if __name__ == "__main__":
    additional_vms = inputs.get('additional_vms', [])
    ssh_public_key = inputs.get('ssh_public_key', '')
    hashed_vm_passwd = inputs.get('hashed_vm_passwd', '')
    vm_user_name = inputs.get('vm_user_name', 'edgeuser')

    my_index = get_instance_index()

    if my_index >= len(additional_vms):
        raise NonRecoverableError(
            f"Instance index {my_index} exceeds additional_vms list "
            f"length {len(additional_vms)}. Ensure additional_server_count "
            f"matches the number of entries in additional_vms."
        )

    vm_config = additional_vms[my_index]
    ctx.logger.info(
        f"Instance index {my_index}: configuring VM '{vm_config.get('vm_name')}'"
    )

    # Extract per-instance config
    ece_service_tag = vm_config['ece_service_tag']
    vm_name = vm_config['vm_name']
    vm_hostname = vm_config.get('vm_hostname', 'edgehost')
    vcpus = vm_config.get('vcpus', 2)
    memory_size = vm_config.get('memory_size', '4GB')
    os_disk_size = vm_config.get('os_disk_size', '50GB')
    disk = vm_config.get('disk', '/DataStore0')
    segment_name = vm_config.get('segment_name', '')

    # Network config
    use_dhcp = vm_config.get('use_dhcp', True)
    static_ip = vm_config.get('static_ip', '')
    gateway = vm_config.get('gateway', '')
    dns_raw = vm_config.get('dns', '')
    use_gateway = bool(gateway)
    use_dns = bool(dns_raw)
    dns_list = [s.strip() for s in dns_raw.split(',') if s.strip()] \
        if dns_raw else []

    # Set runtime properties for ServiceComponent inputs
    ctx.instance.runtime_properties['ece_service_tag'] = ece_service_tag
    ctx.instance.runtime_properties['vm_name'] = vm_name
    ctx.instance.runtime_properties['vm_hostname'] = vm_hostname
    ctx.instance.runtime_properties['vcpus'] = vcpus
    ctx.instance.runtime_properties['memory_size'] = memory_size
    ctx.instance.runtime_properties['os_disk_size'] = os_disk_size
    ctx.instance.runtime_properties['disk'] = disk

    # Build network settings
    ctx.instance.runtime_properties['network_settings'] = \
        build_network_settings(segment_name)

    # Build netplan and cloud-init config
    netplan_b64 = build_netplan_yaml(
        use_dhcp, static_ip, use_gateway, gateway, use_dns, dns_list
    )

    cloudinit_config = build_cloudinit_config(
        vm_hostname, vm_user_name, hashed_vm_passwd,
        ssh_public_key, netplan_b64
    )
    ctx.instance.runtime_properties['cloudinit_config'] = cloudinit_config

    ctx.instance.update()
    ctx.logger.info(
        f"Instance {my_index}: runtime properties set for "
        f"VM '{vm_name}' on endpoint '{ece_service_tag}'"
    )
