import yaml
import base64
from nativeedge import ctx
from nativeedge.state import ctx_parameters as inputs
from nativeedge.exceptions import NonRecoverableError

template = inputs.get("template")
parameters = inputs.get("parameters")

# Validate primary NIC
if not parameters.get("use_dhcp"):
    if not parameters.get("gateway"):
        raise NonRecoverableError(
            'Primary NIC: if DHCP not used, gateway must be provided.')
    if not parameters.get("static_ip"):
        raise NonRecoverableError(
            'Primary NIC: if DHCP not used, static_ip must be provided.')

# Build additional NIC configs for the template
additional_nics_raw = parameters.get("vm_add_nics", [])
additional_nics = []
for idx, nic in enumerate(additional_nics_raw):
    nic_config = {
        'interface': f'enp{idx + 2}s0',
        'use_dhcp': nic.get('use_dhcp', True),
        'accept_dhcp_routes': nic.get('accept_dhcp_routes', False),
        'static_ip': nic.get('static_ip', ''),
        'use_gateway': nic.get('use_gateway', False),
        'gateway': nic.get('gateway', ''),
        'route_destination': nic.get('route_destination', ''),
        'use_dns': nic.get('use_dns', False),
        'dns': [],
    }

    # Parse DNS from comma-separated string or list
    dns_raw = nic.get('dns', '')
    if isinstance(dns_raw, str) and dns_raw:
        nic_config['dns'] = [d.strip() for d in dns_raw.split(',')
                             if d.strip()]
    elif isinstance(dns_raw, list):
        nic_config['dns'] = dns_raw

    iface = f'enp{idx + 2}s0'
    nic_label = f'Additional NIC {idx + 1} ({iface})'

    # Validate: if not DHCP, static_ip is required
    if not nic_config['use_dhcp'] and not nic_config['static_ip']:
        raise NonRecoverableError(
            f'{nic_label}: if DHCP not used, static_ip must be provided.')

    # Validate: if use_gateway, route_destination and gateway are required
    if nic_config['use_gateway']:
        if not nic_config['gateway']:
            raise NonRecoverableError(
                f'{nic_label}: gateway is required when use_gateway is true.')
        if not nic_config['route_destination']:
            raise NonRecoverableError(
                f'{nic_label}: route_destination is required when '
                f'use_gateway is true (e.g. 10.20.0.0/16).')
        if nic_config['route_destination'] == '0.0.0.0/0':
            raise NonRecoverableError(
                f'{nic_label}: route_destination cannot be 0.0.0.0/0. '
                f'Only the primary NIC should have a default route.')

    additional_nics.append(nic_config)

# Management NIC is always the next interface after all user NICs
mgmt_interface = f'enp{len(additional_nics) + 2}s0'

# Build template variables
template_vars = {
    'use_dhcp': parameters.get('use_dhcp'),
    'static_ip': parameters.get('static_ip'),
    'use_gateway': parameters.get('use_gateway'),
    'gateway': parameters.get('gateway'),
    'use_dns': parameters.get('use_dns'),
    'dns': parameters.get('dns'),
    'vm_add_nics': additional_nics,
    'mgmt_interface': mgmt_interface,
}

ctx.logger.debug(f'Generating netplan config: {template}, {template_vars}')

content = ctx.get_resource_and_render(resource_path=template,
                                      template_variables=template_vars)
netplan_encoded = base64.b64encode(content)

ctx.instance.runtime_properties['template_resource_config'] = \
    yaml.load(content.decode('utf-8'), Loader=yaml.Loader)
ctx.instance.runtime_properties['netplan_encoded'] = \
    netplan_encoded.decode('utf-8')
