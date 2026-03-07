########
# Copyright © 2024 Dell Inc. or its subsidiaries. All Rights Reserved.

import json
import os
import requests

from marshmallow import ValidationError
from nativeedge.decorators import operation
from nativeedge.exceptions import NonRecoverableError, RecoverableError
from nativeedge.plugins.workflows import create_resource_drift_info

import nativeedge_plugin.constants as constants
from nativeedge_plugin.eo_proxy.eo_proxy import eo_proxy, cluster_proxy
from nativeedge_plugin import schema
from nativeedge_plugin.vm import vm
from nativeedge_plugin.binary import binary
from nativeedge_plugin.compose import compose
from nativeedge_plugin.registry import registry
from nativeedge_plugin.package import package
from nativeedge_plugin.os import os as operating_system
from nativeedge_plugin.client_credentials import client_credentials
from nativeedge_plugin.license import license
from nativeedge_plugin.endpoint import endpoint
from nativeedge_plugin.utils import get_update_vm_config, get_request_with_code
from nativeedge_plugin.utils import common_request_headers


# 'ctx' is always passed as a keyword argument to operations
# list, or accept '**kwargs'. will receive inputs from blueprint
# eo proxy operation implementation
@operation
def get_eo_proxy(ctx, **kwargs):
    # call eo proxy for url
    eo_proxy(ctx, **kwargs)


@operation
def get_cluster_proxy(ctx, **kwargs):
    # call TCP cluster API to retrieve host and port
    cluster_proxy(ctx, **kwargs)


@operation
def precreate(ctx, **kwargs):
    ctx.logger.info("Validating VM config")
    # properties validation
    # as some types are not supported in plugin.yaml definition,
    # such as list of custom types, enums etc
    try:
        # validate by loading vm_config to schema
        vm_config = vm.parse_image_location(ctx)
        data = schema.VMDeployDefinition().load(vm_config)
        ctx.instance.runtime_properties["memory_input"] = data.get("resourceConstraints", {}).pop("memoryInput", "")
        ctx.instance.runtime_properties["storage_input"] = data.get("resourceConstraints", {}).pop("storageInput", "")
        ctx.instance.runtime_properties["vm_config"] = data
        # NOTE: vm_config may contain sensitive data like cloudinit data and should not be logged
    except ValidationError as err:
        raise NonRecoverableError(f"Invalid plugin node properties: {err}")


@operation
def precreate_app_vm(ctx, **kwargs):
    ctx.logger.info("Validating VM config")
    # properties validation
    # as some types are not supported in plugin.yaml definition,
    # such as list of custom types, enums etc
    try:
        # validate by loading vm_config to schema
        data = schema.AppVMDeployDefinition().load(ctx.node.properties["app_vm_config"])
        ctx.instance.runtime_properties["memory_input"] = data.get("resourceConstraints", {}).pop("memoryInput", "")
        ctx.instance.runtime_properties["storage_input"] = data.get("resourceConstraints", {}).pop("storageInput", "")
        ctx.instance.runtime_properties["app_vm_config"] = data
        # NOTE: vm_config may contain sensitive data like cloudinit data and should not be logged
    except ValidationError as err:
        raise NonRecoverableError(f"Invalid plugin node properties: {err}")


@operation
def create_app_vm(ctx, **kwargs):
    # Operation is executed for the first time, will initiate VM deployment
    if ctx.operation.retry_number == 0:
        ctx.logger.info("Starting the VM deployment")
        vm.deploy_app_vm(ctx)

        # It will take some time until the VM starts running, request to check status after 30 seconds
        return ctx.operation.retry(
            message="Waiting for the VM to run..",
            retry_after=constants.VERIFY_CREATE_VM_RETRY_TIMER,
        )

    # Verify VM status to be running ("ok")
    if vm.verify_vm_status(ctx, vm.deploy_app_vm):
        ctx.logger.info("Successfully deployed the VM!")


@operation
def create(ctx, **kwargs):
    # Operation is executed for the first time, will initiate VM deployment
    if ctx.operation.retry_number == 0:
        ctx.logger.info("Starting the VM deployment")
        vm.deploy_vm(ctx)

        # It will take some time until the VM starts running, request to check status after 30 seconds
        return ctx.operation.retry(
            message="Waiting for the VM to run..",
            retry_after=constants.VERIFY_CREATE_VM_RETRY_TIMER,
        )

    # Verify VM status to be running ("ok")
    if vm.verify_vm_status(ctx, vm.deploy_vm):
        ctx.logger.info("Successfully deployed the VM!")


@operation
def start(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        if not vm.start_vm(ctx, **kwargs):
            return

        ctx.logger.info("Starting VM")
        return ctx.operation.retry(message="Waiting for the VM to run..", retry_after=10)

    if vm.verify_vm_runstate(ctx, vm.get_vm_details(ctx, **kwargs), "running"):
        ctx.logger.info("Successfully started VM")


def save_vm_config_to_runtime_properties(ctx):
    try:
        # Load and validate vm_config from node properties
        vm_config = vm.parse_image_location(ctx)
        vm_config_data = schema.VMDeployDefinition().load(vm_config)
        ctx.logger.info("VM configuration loaded successfully.")
    except ValidationError as err:
        # Log the validation errors
        ctx.logger.error(
            "Validation error occurred while loading VM configuration: %s",
            err.messages,
        )
        raise ValidationError(f"Validation error: {err.messages}")

    # Remove the 'cloudinit' field if it exists, as it may contain sensitive data
    removed_value = vm_config_data.pop("cloudinit", None)
    if removed_value is not None:
        ctx.logger.info("Removed sensitive cloudinit data from VM configuration before saving.")

    # Save the VM configuration in 'expected_configuration' within runtime_properties
    ctx.instance.runtime_properties["expected_configuration"] = vm_config_data
    ctx.logger.info("setting expected_configuration to: %s", vm_config_data)


@operation
def poststart(ctx, **kwargs):
    from nativeedge.manager import get_rest_client

    save_vm_config_to_runtime_properties(ctx)

    # Get the rest client
    client = get_rest_client()
    # Get the current deployment
    dep = client.deployments.get(ctx.deployment.id)

    # Below updates are only for application_blueprint
    if dep.blueprint_id != "application_blueprint":
        return

    # Create a new list of labels: the previously-existing labels,
    # Plus a new label: application_installed=true
    new_labels = []
    for label in dep.labels:
        # dep.labels is in the format: [{"key": x, "value": y}]
        # NOTE: .update_labels expects it a different format: [{x: y}]
        # So we change it here.
        if label["key"] == "application_blueprint_installed":
            continue
        else:
            new_label = {label["key"]: label["value"]}
            new_labels.append(new_label)

    new_labels.append({"application_blueprint_installed": "true"})

    # Send the labels back
    client.deployments.update_labels(ctx.deployment.id, labels=new_labels)


@operation
def stop(ctx, **kwargs):
    # Uninstall workflow will trigger a few operations including stop and delete
    # Skip if the stop operation is triggered by uninstall and reinstall workflow,
    # because delete will destroy the VM anyway. (reinstall will call uninstall and install)
    if ctx.workflow_id == "uninstall" or ctx.workflow_id == "reinstall":
        ctx.logger.debug("Stop is triggered by uninstall workflow, skipping stop")
        return

    if ctx.operation.retry_number == 0:
        if not vm.stop_vm(ctx, **kwargs):
            return

        ctx.logger.info("Stopping VM")
        return ctx.operation.retry(message="Waiting for the VM to stop..", retry_after=10)

    if vm.verify_vm_runstate(ctx, vm.get_vm_details(ctx, **kwargs), "stopped"):
        ctx.logger.info("Successfully stopped VM")


@operation
def restart(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        ctx.logger.info("Restarting VM")
        vm.restart_vm(ctx, **kwargs)

    if vm.verify_vm_runstate(ctx, vm.get_vm_details(ctx, **kwargs), "running"):
        ctx.logger.info("Successfully initiated VM restart")


@operation
def suspend(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        ctx.logger.info("Suspending VM")
        if not vm.suspend_vm(ctx, **kwargs):
            return

    if vm.verify_vm_runstate(ctx, vm.get_vm_details(ctx, **kwargs), "suspended"):
        ctx.logger.info("Successfully suspended VM")


@operation
def resume(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        ctx.logger.info("Resuming VM")
        if not vm.resume_vm(ctx, **kwargs):
            return

    if vm.verify_vm_runstate(ctx, vm.get_vm_details(ctx, **kwargs), "running"):
        ctx.logger.info("Successfully resumed VM")


# To avoid reinstalling instances when their properties have changed, check_drift and update operations have to be
# installed. Instances of nodes that implement those operations, will run them instead of being reinstalled.
# If check_drift returns an empty or false value, update operations will not run, and even in case of blueprint
# changes (e.g. if the node properties have changed), the instances will not be updated or reinstalled.
# Always return a non-empty or true value to trigger update operations
@operation
def check_drift(ctx, **kwargs):
    try:
        ctx.instance.refresh(force=True)
    except Exception as err:
        ctx.logger.error(f"Error refreshing ctx: {err}")
        raise err

    expected_VM_configuration = ctx.instance.runtime_properties.get("expected_configuration", {})
    if not expected_VM_configuration:
        error_message = "expected_configuration is missing in runtime_properties"
        ctx.logger.error(error_message)
        raise ValueError(error_message)

    current_vm_config_template = expected_VM_configuration.copy()
    current_properties = get_current_vm_config(ctx, current_vm_config_template)
    ctx.logger.info(
        "Returning drift information: prev=%s, curr=%s, resource_id=%s",
        expected_VM_configuration,
        current_properties,
        "vm_config",
    )

    drift_result = create_resource_drift_info(current_properties, expected_VM_configuration, "vm_config")
    # TODO: Remove this condition once bug NE-53832 is fixed
    if drift_result is None:
        ctx.logger.info("No drift detected. Returning default empty drift result.")
        drift_result = create_empty_drift_result("vm_config")

    ctx.logger.info("Drift data : %s", drift_result)
    return drift_result


def get_current_vm_config(ctx, current_config_template):
    vm_id = ctx.instance.runtime_properties.get("vm_details", {}).get("id")
    compute_svc_api = os.getenv("COMPUTE_SVC_API", "True").lower() == "true"
    hostname = os.getenv("EO_URL", constants.DEFAULT_GATEWAY_DOMAIN)

    try:
        VM_details_response = vm.get_vm_details_by_vm_id(ctx, vm_id, compute_svc_api, hostname)
        ctx.logger.info(f"Successfully retrieved response for deployment ID {vm_id}: {VM_details_response.text}")

        if VM_details_response.ok:
            # 200 response
            VM_details_response = VM_details_response.json()
            current_location = VM_details_response.get("serviceTag")
            current_config_template["location"] = current_location
            return current_config_template
        elif VM_details_response.status_code == 404:
            ctx.logger.info(f"VM was deleted, for VM ID: {vm_id}: {VM_details_response.reason}")
            return None  # VM was deleted
        else:
            error_message = (
                f"Error response received while fetching VM details for VM ID {vm_id}: "
                f"Response Content: {VM_details_response.text}"
            )
            ctx.logger.info(error_message)
            raise Exception(error_message)
    except Exception as e:
        ctx.logger.error(f"an error occurred while fetching VM details for VM ID: {vm_id}, {e}")
        raise e


@operation
def update_config(ctx, **kwargs):
    from nativeedge.manager import get_rest_client

    ctx.logger.info("Validating update VM config")
    client = get_rest_client()
    dep = client.deployments.get(ctx.deployment.id)

    # properties validation
    # as some types are not supported in plugin.yaml definition,
    # such as list of custom types, enums etc
    try:
        # validate by loading config to schema
        update_vm_config = (
            get_update_vm_config(ctx.node.properties["app_vm_config"])
            if dep.blueprint_id == "application_blueprint"
            else get_update_vm_config(ctx.node.properties["vm_config"])
        )

        compute_svc_api = os.getenv("COMPUTE_SVC_API", "True").lower() == "true"

        if compute_svc_api:
            data = schema.VMUpdateDefinition().load(update_vm_config)
            deployment_id = ctx.instance.runtime_properties["deployment_id"]
            data["id"] = deployment_id
        else:
            data = schema.VMUpdateDefinition().load(update_vm_config)
        ctx.instance.runtime_properties["update_vm_config"] = data
        # NOTE: update_vm_config may contain sensitive data like cloudinit data and should not be logged
    # catch all exceptions when validating update vm config and raise as NonRecoverable to fail operation early
    except Exception as err:
        raise NonRecoverableError(f"Invalid plugin node properties: {err}")


@operation
def update_apply(ctx, **kwargs):
    # Operation is executed for the first time, will initiate VM update
    if ctx.operation.retry_number == 0:
        ctx.logger.info("Updating the VM")
        vm.update_vm(ctx)

    if vm.verify_update_vm_status(ctx):
        # After a successful update, update the 'expected_configuration'
        # so that future drift checks can compare against this configuration.
        save_vm_config_to_runtime_properties(ctx)

        ctx.logger.info("Successfully updated the VM!")


@operation
def delete(ctx, **kwargs):
    try:
        deployment_id = ctx.instance.runtime_properties["deployment_id"]
    except KeyError:
        # In case precreate failed, or create deployment api call failed, there will be no deployment_id
        # hence, delete should just do nothing instead of raise NonRecoverable error
        ctx.logger.info("No deployment id is found, nothing to delete")
        return

    if ctx.operation.retry_number == 0:
        if not vm.vm_exists(ctx, deployment_id):
            # nothing to do
            ctx.logger.info("Deployment does not exist, nothing to delete")
            return

        ctx.logger.info("Initiating the VM deletion")
        vm.delete_vm(ctx, deployment_id)
        return ctx.operation.retry(
            message="Waiting for the deployment to be deleted..",
            retry_after=constants.GENERIC_RETRY_TIMER,
        )

    try:
        ret = vm.verify_delete_vm_status(ctx, deployment_id)
        if ret == vm.DeleteVMStatus.IN_PROGRESS:
            # It will take some time until the VM is deleted, request to check status after 5 seconds
            ctx.logger.info("Deletion is still in progress")
            return ctx.operation.retry(
                message="Waiting for the deployment to be deleted..",
                retry_after=constants.VERIFY_DELETE_VM_RETRY_TIMER,
            )
        if ret == vm.DeleteVMStatus.DONE:
            ctx.logger.info("Successfully deleted the VM!")
    except requests.exceptions.ConnectionError as conErr:
        raise RecoverableError(f"Connection error: {conErr}")


@operation
def verify_vm_runstate(ctx, **kwargs):
    expected_runstate = kwargs.get("expected_runstate")
    vm.verify_vm_runstate(ctx, vm.get_vm_details(ctx, **kwargs), expected_runstate)


@operation
def validate_binary_image_config(ctx, **kwargs):
    ctx.logger.info("Validating binary image config")

    try:
        # Validate by loading binary_image_config to schema
        data = schema.BinaryUploadDefinition().load(ctx.node.properties["binary_image_config"])
        ctx.instance.runtime_properties["binary_image_config"] = data
    except ValidationError as err:
        raise NonRecoverableError(f"Invalid plugin node properties: {err}")

    # Validate auth from external repo
    if binary.validate_auth(ctx):
        ctx.logger.info("Successfully validated auth access from external repository")


@operation
def upload_binary(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        ctx.logger.info("Starting the binary upload")
        binary.upload(ctx, **kwargs)

    if binary.verify_upload_status(ctx, **kwargs):
        ctx.logger.info("Binary exists in the system")


def is_binary_image_drifted(ctx, binary_id):
    """
    Retrieve binary image details by calling the actual service with the provided binary_id.
    Logs errors but does not raise exceptions. Returns a boolean indicating whether a diff was found (404).
    """
    hostname = os.getenv("EO_URL", constants.DEFAULT_GATEWAY_DOMAIN)
    url = constants.GET_BINARY_URL.format(hostname, binary_id)

    ctx.logger.info(f"Fetching binary image details for ID {binary_id}, URL: {url}")

    try:
        # Make the GET request to fetch binary details
        response = get_request_with_code(url, common_request_headers(ctx))
        ctx.logger.info(f"Successfully retrieved response for binary ID {binary_id}: {response.text}")

        if response and response.ok:
            # A successful 200 response means no diff
            ctx.logger.info("200 response code received. No diff found.")
            return False  # No diff found
        elif response.status_code == 404:
            # A 404 response means the binary was not found, indicating a diff
            ctx.logger.warning(f"Binary ID {binary_id} not found (404). Treating as diff.")
            return True  # Diff found
        else:
            error_message = (
                f"Error fetching binary details for ID {binary_id}: "
                f"Response Status Code: {response.status_code}, Reason: {response.reason}"
            )
            ctx.logger.error(error_message)
            raise Exception(error_message)

    except Exception as e:
        # Log exceptions and treat them as non-diff
        ctx.logger.error(f"An error occurred while fetching binary details for ID {binary_id}: {e}")
        raise e


@operation
def binary_check_drift(ctx, **kwargs):
    """
    Operation to check drift between the expected and current binary image configurations.
    If a diff is found (binary not found - 404), the current config is empty.
    If no diff is found, the current config matches the expected config.
    Logs errors and raises exceptions on critical errors.
    """
    # Refresh runtime properties
    ctx.instance.refresh(force=True)
    ctx.logger.info("Instance runtime properties refreshed successfully.")

    # Retrieve binary image configuration
    BINARY_IMAGE_CONFIG_KEY = "binary_image_config"
    expected_binary_image_config = ctx.instance.runtime_properties.get(BINARY_IMAGE_CONFIG_KEY, {})
    if not expected_binary_image_config:
        raise ValueError("expected binary image config is missing from runtime properties.")
    expected_binary_image_config_json = json.dumps(expected_binary_image_config)
    ctx.logger.info(f"Expected binary image config JSON: {expected_binary_image_config_json}")

    # Retrieve binary ID
    binary_id = ctx.instance.runtime_properties.get("binary_id")
    if not binary_id:
        raise ValueError("binary_id is missing from runtime properties.")
    ctx.logger.info(f"Binary ID: {binary_id}")

    # Check for differences
    if is_binary_image_drifted(ctx, binary_id):
        ctx.logger.info("Diff found: Returning empty config.")
        current_binary_image_response_json = None
        drift_result = create_resource_drift_info(
            current_binary_image_response_json, expected_binary_image_config_json, BINARY_IMAGE_CONFIG_KEY
        )
        ctx.logger.info(f"Drift information: {drift_result}")
    else:
        ctx.logger.info("No diff found: Using expected binary image config.")
        current_binary_image_response_json = expected_binary_image_config_json
        drift_result = create_resource_drift_info(
            current_binary_image_response_json, expected_binary_image_config_json, BINARY_IMAGE_CONFIG_KEY
        )

    if drift_result is None:
        ctx.logger.info("No drift detected. Returning default empty drift result.")
        drift_result = create_empty_drift_result(BINARY_IMAGE_CONFIG_KEY)

    ctx.logger.info("Drift data : %s", drift_result)

    return drift_result


# create_empty_drift_result - Remove this condition once bug NE-53832 is fixed
def create_empty_drift_result(resource_id):

    drift_result = {
        "resource_id": resource_id,
        "description": None,
        "time": None,
        "diff": None,
        "diff_count": 0,
    }
    return drift_result


@operation
def delete_binary(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        binary_status = binary.check_binary_exist(ctx, **kwargs)
        if binary_status == binary.BinaryStatus.NOT_FOUND:
            ctx.logger.info("Binary does not exist, nothing to delete")
            return

    ctx.logger.info("Delete binary will be done in Deployment Service, skipping")


@operation
def boot_order_update(ctx, **kwargs):
    vm.boot_order_update(ctx, **kwargs)


@operation
def precreate_compose(ctx, **kwargs):
    ctx.logger.info("Validating compose config")

    try:
        # Validate by loading compose_config to schema
        data = schema.ComposeDeployDefinition().load(ctx.node.properties.get("compose_config"))
        # NOTE: compose_config may contain sensitive data like external repository's credential and should not be logged

    except ValidationError as err:
        raise NonRecoverableError(f"Invalid plugin node properties: {err}")

    # Envsubst compose yaml
    compose.envsubst(ctx, data)

    # Validate compose with Compute Service's validator
    if compose.validate_compose(ctx):
        ctx.logger.info("Successfully validated compose config")


@operation
def create_compose(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        ctx.logger.info("Starting the compose container deployment")
        compose.deploy_compose(ctx)

        return ctx.operation.retry(
            message="Waiting for the compose container to run..",
            retry_after=constants.VERIFY_CREATE_COMPOSE_RETRY_TIMER,
        )

    # Verify compose status
    if compose.verify_deploy_compose_status(ctx):
        ctx.logger.info("Successfully deployed the compose container!")


@operation
def delete_compose(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        if not compose.compose_exists(ctx):
            ctx.logger.info("Deployment does not exist, nothing to delete")
            return

        ctx.logger.info("Initiating the compose container deletion")
        compose.delete_compose(ctx)

    if compose.verify_delete_compose_status(ctx):
        ctx.logger.info("Successfully deleted the compose container")


@operation
def start_compose(ctx, **kwargs):
    if ctx.workflow_id == "install":
        ctx.logger.info("start is skipped for install workflow")
        return
    if ctx.operation.retry_number == 0:
        if not compose.compose_exists(ctx):
            ctx.logger.info("Deployment does not exist, nothing to start")
            return

        ctx.logger.info("Initiating the compose container start")
        compose.start_compose(ctx)


@operation
def poststart_compose(ctx, **kwargs):
    containers = compose.get_containers(ctx)
    ctx.instance.runtime_properties[constants.EXPECTED_CONTAINERS_KEY] = containers
    ctx.logger.info("setting %s to: %s", constants.EXPECTED_CONTAINERS_KEY, containers)


@operation
def stop_compose(ctx, **kwargs):
    if ctx.workflow_id == "uninstall":
        ctx.logger.info("stop is skipped for uninstall workflow")
        return
    if ctx.operation.retry_number == 0:
        if not compose.compose_exists(ctx):
            ctx.logger.info("Deployment does not exist, nothing to stop")
            return

        ctx.logger.info("Initiating the compose container stop")
        compose.stop_compose(ctx)


@operation
def pause_compose(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        if not compose.compose_exists(ctx):
            ctx.logger.info("Deployment does not exist, nothing to pause")
            return

        ctx.logger.info("Initiating the compose container pause")
        compose.pause_compose(
            ctx,
        )


@operation
def unpause_compose(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        if not compose.compose_exists(ctx):
            ctx.logger.info("Deployment does not exist, nothing to unpause")
            return

        ctx.logger.info("Initiating the compose container unpause")
        compose.unpause_compose(
            ctx,
        )


@operation
def restart_compose(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        if not compose.compose_exists(ctx):
            ctx.logger.info("Deployment does not exist, nothing to restart")
            return

        ctx.logger.info("Initiating the compose container restart")
        compose.restart_compose(
            ctx,
        )


@operation
def update_compose(ctx, **kwargs):
    if ctx.operation.retry_number == 0:
        if not compose.compose_exists(ctx):
            ctx.logger.info("Deployment does not exist, nothing to update")
            return

        ctx.logger.info("Initiating the compose container update")
        compose.update_compose(
            ctx,
        )


def validate_registry_config(ctx, **kwargs):
    ctx.logger.info("Validating registry config")

    try:
        # Validate by loading compose_config to schema
        data = schema.RegistryDefinition().load(ctx.node.properties.get("registry_config"))
        ctx.instance.runtime_properties["registry_config"] = data

    except ValidationError as err:
        raise NonRecoverableError(f"Invalid plugin node properties: {err}")


@operation
def registry_login(ctx, **kwargs):
    ctx.logger.info("Logging to registry")

    if registry.login(ctx):
        ctx.logger.info("Successfully login to registry")


@operation
def download_software(ctx, **kwargs):
    ctx.logger.info("Validating software download config")

    try:
        # check this is download task for oxy server or for dspo
        properties_key_name = (
            constants.OXY_DOWNLOAD_PROPERTIES_KEY
            if ctx.node.properties.get(constants.OXY_DOWNLOAD_PROPERTIES_KEY) is not None
            else constants.ORCHESTRATOR_DOWNLOAD_PROPERTIES_KEY
        )
        kwargs["properties_key_name"] = properties_key_name
        # Validate by loading oxy_server_packages or dspo_packages to schema
        download_packages = ctx.node.properties.get(properties_key_name)
        data = schema.DownloadSoftwarePackageDefinition().load(download_packages)
        ctx.instance.runtime_properties[properties_key_name] = data
    except ValidationError as err:
        raise NonRecoverableError(f"Invalid plugin node properties: {err}")

    if ctx.operation.retry_number == 0:
        ctx.logger.info("Start downloading software")
        package.download(ctx, **kwargs)

    # Monitor download status
    package.verify_download_status(ctx, **kwargs)


@operation
def update_provisioning_state(ctx, **kwargs):
    operating_system.update_provisioning_state(ctx, **kwargs)


def compose_check_drift(ctx, **kwargs):
    try:
        ctx.instance.refresh(force=True)
        expected_containers = ctx.instance.runtime_properties.get(constants.EXPECTED_CONTAINERS_KEY, {})
    except Exception as err:
        ctx.logger.error(f"Error fetching expected containers map from runtime properties: {err}")
        raise err

    if not expected_containers:
        error_message = "expected_containers is missing in runtime_properties"
        ctx.logger.error(error_message)
        raise ValueError(error_message)

    containers_resource_id = "containers_list"
    current_containers = compose.get_containers(ctx)

    drift_result = create_resource_drift_info(current_containers, expected_containers, containers_resource_id)

    # TODO: Remove this condition once bug NE-53832 is fixed
    if drift_result is None:
        ctx.logger.info("No drift detected. Returning default empty drift result.")
        drift_result = {
            "resource_id": containers_resource_id,
            "description": None,
            "time": None,
            "diff": None,
            "diff_cnt": 0,
            "prev": None,
            "curr": None,
        }
    ctx.logger.info("diff data : %s", drift_result["diff"])
    return drift_result


@operation
def generate_client_secret(ctx, **kwargs):
    client_credentials.generate_client_secret(ctx, **kwargs)


@operation
def get_certificate(ctx, **kwargs):
    client_credentials.get_certificate(ctx, **kwargs)


# Deprecated: use register_private_cloud
@operation
def apply_license(ctx, **kwargs):
    license.apply_license(ctx, **kwargs)


@operation
def remove_endpoint(ctx, **kwargs):
    endpoint.remove_endpoint(ctx, **kwargs)


@operation
def parse_vm_definition(ctx, **kwargs):
    vm.parse_vm_definition(ctx, **kwargs)


@operation
def add_outcome_cluster_endpoint(ctx, **kwargs):
    ctx.logger.info(f"add_outcome_cluster_endpoint input: {ctx.node.properties}")
    response = endpoint.add_outcome_cluster_endpoint(ctx, **kwargs)
    ctx.instance.runtime_properties[constants.OUTCOME_CLUSTER_ENDPOINT] = response


@operation
def patch_outcome_cluster_endpoint(ctx, **kwargs):
    ctx.logger.info(f"patch_outcome_cluster_endpoint input: {ctx.node.properties}")
    response = endpoint.patch_outcome_cluster_endpoint(ctx, **kwargs)
    ctx.instance.runtime_properties[constants.OUTCOME_CLUSTER_ENDPOINT] = response


@operation
def register_private_cloud(ctx, **kwargs):
    license.register_private_cloud(ctx, **kwargs)


@operation
def expand_private_cloud_node(ctx, **kwargs):
    license.expand_private_cloud_node(ctx, **kwargs)


@operation
def reduce_private_cloud_node(ctx, **kwargs):
    license.reduce_private_cloud_node(ctx, **kwargs)


@operation
def deregister_private_cloud(ctx, **kwargs):
    license.deregister_private_cloud(ctx, **kwargs)
