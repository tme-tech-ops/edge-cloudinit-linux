"""Resolve the effective utility VM blueprint ID.

If `utility_blueprint_id_override` is non-empty, use it; otherwise fall
back to the visible `utility_blueprint_id`. Stores the result in the
runtime property `blueprint_id` for downstream ServiceComponent nodes
to consume via `get_attribute`.

This indirection is the seam used by the edge-cloudinit-windows plan
smoke-test phase to target `edge-cloudinit-utility-vm-v2` without
affecting the visible default that production deployments use.
"""
from dell import ctx
from dell.state import ctx_parameters as inputs


def main():
    primary = (inputs.get("primary") or "").strip()
    override = (inputs.get("override") or "").strip()

    resolved = override or primary
    if not resolved:
        raise Exception(
            "Neither utility_blueprint_id nor utility_blueprint_id_override "
            "is set. Cannot resolve a utility VM blueprint to use."
        )

    ctx.instance.runtime_properties["blueprint_id"] = resolved
    ctx.logger.info(
        f"Resolved utility blueprint id: {resolved} "
        f"(override='{override}', primary='{primary}')"
    )


main()
