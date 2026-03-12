import json
from nativeedge import ctx
from nativeedge.state import ctx_parameters as inputs

primary_segment = inputs.get('primary_segment')
primary_port_forwards = inputs.get('primary_port_forwards', [])
additional_nics = inputs.get('vm_add_nics', [])

network_settings = []

# Primary NIC (VNIC0)
if primary_segment:
    network_setting = {
        'name': 'VNIC0',
        'segment_name': primary_segment
    }
    if primary_port_forwards:
        network_setting['port_fwd_rules'] = primary_port_forwards
    network_settings.append(network_setting)
else:
    ctx.logger.error('Primary network segment (vnic_0) is required.')

# Additional NICs (VNIC1 through VNIC9)
for idx, nic in enumerate(additional_nics):
    segment = nic.get('segment_name', '')
    if segment:
        vnic_name = f'VNIC{idx + 1}'
        network_setting = {
            'name': vnic_name,
            'segment_name': segment
        }

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
    else:
        ctx.logger.debug(
            f'Skipping additional NIC {idx + 1} - no segment name.')

ctx.logger.debug(f'Number of VNICs attached: {len(network_settings)}')

ctx.instance.runtime_properties['network_settings'] = network_settings
