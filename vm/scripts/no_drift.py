"""check_drift for nodes whose output only matters when the VMs are created.

They never drift, so a deployment update never re-runs or reinstalls them.
Read-only.
"""
from dell import ctx

ctx.logger.info(f"{ctx.node.id}: no drift (only used when the VMs are created)")
ctx.returns(None)
