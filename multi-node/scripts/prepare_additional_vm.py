import json
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


def build_network_settings(vm_config, add_nics):
    """Build network_settings list for primary NIC + additional NICs."""
    network_settings = []

    # Primary NIC (VNIC0)
    segment_name = vm_config.get('segment_name', '')
    if not segment_name:
        raise NonRecoverableError(
            "segment_name is required for primary NIC (VNIC0)."
        )
    network_settings.append({
        'name': 'VNIC0',
        'segment_name': segment_name
    })

    # Additional NICs (VNIC1+)
    for idx, nic in enumerate(add_nics):
        segment = nic.get('segment_name', '')
        if not segment:
            raise NonRecoverableError(
                f"segment_name is required for additional NIC "
                f"{idx + 1} (VNIC{idx + 1})."
            )
        vnic_name = f'VNIC{idx + 1}'
        network_setting = {
            'name': vnic_name,
            'segment_name': segment
        }

        # Handle NAT port forwarding
        pf_rules_raw = nic.get('port_forward_rules', '')
        if nic.get('use_nat', False) and pf_rules_raw:
            if isinstance(pf_rules_raw, str):
                try:
                    pf_rules = json.loads(pf_rules_raw)
                    network_setting['port_fwd_rules'] = pf_rules
                except json.JSONDecodeError:
                    ctx.logger.warning(
                        f'Invalid JSON for port_forward_rules on {vnic_name}')
            elif isinstance(pf_rules_raw, list):
                network_setting['port_fwd_rules'] = pf_rules_raw

        network_settings.append(network_setting)

    return network_settings


def build_netplan_yaml(vm_config, add_nics, mgmt_interface):
    """Build netplan YAML for primary NIC + additional NICs + management."""
    netplan = {
        'network': {
            'version': 2,
            'renderer': 'networkd',
            'ethernets': {}
        }
    }

    # --- Primary NIC (enp1s0) ---
    use_dhcp = vm_config.get('use_dhcp', True)
    static_ip = vm_config.get('static_ip', '')
    use_gateway = vm_config.get('use_gateway', False)
    gateway = vm_config.get('gateway', '')
    use_dns = vm_config.get('use_dns', False)
    dns_raw = vm_config.get('dns', '')
    dns_list = [s.strip() for s in dns_raw.split(',') if s.strip()] \
        if dns_raw else []

    if not use_dhcp:
        if not static_ip:
            raise NonRecoverableError(
                'Primary NIC: if DHCP not used, static_ip must be provided.')
        if use_gateway and not gateway:
            raise NonRecoverableError(
                'Primary NIC: gateway is required when use_gateway is true.')

    primary_conf = {'dhcp-identifier': 'mac', 'dhcp4': use_dhcp}
    if not use_dhcp:
        if static_ip:
            primary_conf['addresses'] = [static_ip]
        if use_dns and dns_list:
            primary_conf['nameservers'] = {'addresses': dns_list}
        if use_gateway and gateway:
            primary_conf['routes'] = [{'to': 'default', 'via': gateway}]

    netplan['network']['ethernets']['enp1s0'] = primary_conf

    # --- Additional NICs (enp2s0, enp3s0, ...) ---
    for idx, nic in enumerate(add_nics):
        iface = f'enp{idx + 2}s0'
        nic_use_dhcp = nic.get('use_dhcp', True)
        nic_accept_routes = nic.get('accept_dhcp_routes', False)
        nic_static_ip = nic.get('static_ip', '')
        nic_use_gateway = nic.get('use_gateway', False)
        nic_gateway = nic.get('gateway', '')
        nic_route_dest = nic.get('route_destination', '')
        nic_use_dns = nic.get('use_dns', False)
        nic_dns_raw = nic.get('dns', '')

        if isinstance(nic_dns_raw, str) and nic_dns_raw:
            nic_dns_list = [s.strip() for s in nic_dns_raw.split(',')
                           if s.strip()]
        elif isinstance(nic_dns_raw, list):
            nic_dns_list = nic_dns_raw
        else:
            nic_dns_list = []

        nic_label = f'Additional NIC {idx + 1} ({iface})'

        # Validate
        if not nic_use_dhcp and not nic_static_ip:
            raise NonRecoverableError(
                f'{nic_label}: if DHCP not used, static_ip must be provided.')
        if nic_use_gateway:
            if not nic_gateway:
                raise NonRecoverableError(
                    f'{nic_label}: gateway is required when '
                    f'use_gateway is true.')
            if not nic_route_dest:
                raise NonRecoverableError(
                    f'{nic_label}: route_destination is required when '
                    f'use_gateway is true (e.g. 10.20.0.0/16).')
            if nic_route_dest == '0.0.0.0/0':
                raise NonRecoverableError(
                    f'{nic_label}: route_destination cannot be 0.0.0.0/0. '
                    f'Only the primary NIC should have a default route.')

        nic_conf = {'dhcp-identifier': 'mac', 'dhcp4': nic_use_dhcp}

        if nic_use_dhcp:
            if not nic_accept_routes:
                nic_conf['dhcp4-overrides'] = {'use-routes': False}
        else:
            if nic_static_ip:
                nic_conf['addresses'] = [nic_static_ip]
            if nic_use_dns and nic_dns_list:
                nic_conf['nameservers'] = {'addresses': nic_dns_list}
            if nic_use_gateway and nic_gateway:
                nic_conf['routes'] = [
                    {'to': nic_route_dest, 'via': nic_gateway}
                ]

        netplan['network']['ethernets'][iface] = nic_conf

    # --- Management interface (always DHCP, suppress routes) ---
    netplan['network']['ethernets'][mgmt_interface] = {
        'dhcp4': True,
        'dhcp4-overrides': {'use-routes': False}
    }

    netplan_yaml = yaml.dump(netplan, default_flow_style=False)
    return base64.b64encode(netplan_yaml.encode('utf-8')).decode('utf-8')


def build_additional_disks(add_disks):
    """Build additional_disks list for NativeEdgeVM node."""
    disks = []
    for d in add_disks:
        disks.append({
            'name': d['name'],
            'disk': d['disk'],
            'storage': d['storage'],
            'storage_unit': d.get('storage_unit', 'GB')
        })
    return disks


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
    additional_vm = inputs.get('additional_vm', [])
    add_vm_add_nics = inputs.get('add_vm_add_nics', [])
    add_vm_add_disks = inputs.get('add_vm_add_disks', [])
    ssh_public_key = inputs.get('ssh_public_key', '')
    hashed_vm_passwd = inputs.get('hashed_vm_passwd', '')
    vm_user_name = inputs.get('vm_user_name', 'edgeuser')

    my_index = get_instance_index()

    if my_index >= len(additional_vm):
        raise NonRecoverableError(
            f"Instance index {my_index} exceeds additional_vm list "
            f"length {len(additional_vm)}. Ensure additional_server_count "
            f"matches the number of entries in additional_vm."
        )

    vm_config = additional_vm[my_index]
    ece_service_tag = vm_config['ece_service_tag']
    ctx.logger.info(
        f"Instance index {my_index}: configuring VM "
        f"'{vm_config.get('vm_name')}' on endpoint '{ece_service_tag}'"
    )

    # Extract per-instance config
    vm_name = vm_config['vm_name']

    # Filter additional NICs and disks by vm_name
    my_add_nics = [
        n for n in add_vm_add_nics
        if n.get('vm_name') == vm_name
    ]
    my_add_disks = [
        d for d in add_vm_add_disks
        if d.get('vm_name') == vm_name
    ]
    ctx.logger.info(
        f"Correlated {len(my_add_nics)} additional NIC(s) and "
        f"{len(my_add_disks)} additional disk(s) for VM '{vm_name}'"
    )

    vm_hostname = vm_config.get('vm_hostname', 'edgehost')
    vcpus = vm_config.get('vcpus', 2)
    memory_size = vm_config.get('memory_size', '4GB')
    os_disk_size = vm_config.get('os_disk_size', '50GB')
    disk = vm_config.get('disk', '/DataStore0')

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
        build_network_settings(vm_config, my_add_nics)

    # Build netplan and cloud-init config
    mgmt_interface = f'enp{2 + len(my_add_nics)}s0'
    netplan_b64 = build_netplan_yaml(vm_config, my_add_nics, mgmt_interface)

    cloudinit_config = build_cloudinit_config(
        vm_hostname, vm_user_name, hashed_vm_passwd,
        ssh_public_key, netplan_b64
    )
    ctx.instance.runtime_properties['cloudinit_config'] = cloudinit_config

    # Build additional disks
    ctx.instance.runtime_properties['additional_disks'] = \
        build_additional_disks(my_add_disks)

    ctx.instance.update()
    ctx.logger.info(
        f"Instance {my_index}: runtime properties set for "
        f"VM '{vm_name}' on endpoint '{ece_service_tag}'"
    )
