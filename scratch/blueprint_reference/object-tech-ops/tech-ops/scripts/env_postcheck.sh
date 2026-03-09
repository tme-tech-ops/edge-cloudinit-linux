#!/bin/bash

OFFLINE_PACKAGE_NAME="swfs-save.tar.gz"
OFFLINE_PACKAGE_UPLOADED="false"
OFFLINE_PACKAGE_URL="N/A"
SWFS_RUNNING="false"

mgmt_ip=$(hostname -I | awk '{print $1}')

# Default port values
SWFS_ADMIN_PORT="${SWFS_ADMIN_PORT:-443}"
SWFS_MASTER_PORT="${SWFS_MASTER_PORT:-9333}"
SWFS_FILER_PORT="${SWFS_FILER_PORT:-8888}"
SWFS_S3_PORT="${SWFS_S3_PORT:-8333}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"

ctx logger info "Post install check started."

# Primary health check: verify the seaweed-mini container is running
container_running=$(sudo docker inspect --format '{{.State.Running}}' seaweed-mini 2>/dev/null || echo "false")

if [[ "$container_running" == "true" ]]; then
  ctx logger info "SeaweedFS container (seaweed-mini) is running."
  SWFS_RUNNING="true"
  SWFS_ADMIN_URL="https://$mgmt_ip:$SWFS_ADMIN_PORT"
  SWFS_FILER_URL="https://$mgmt_ip:$SWFS_FILER_PORT"
  SWFS_MASTER_URL="https://$mgmt_ip:$SWFS_MASTER_PORT"
  SWFS_S3_URL="https://$mgmt_ip:$SWFS_S3_PORT"
  grafana_running=$(sudo docker inspect --format '{{.State.Running}}' grafana 2>/dev/null || echo "false")
  if [[ "$grafana_running" == "true" ]]; then
    SWFS_GRAFANA_URL="https://$mgmt_ip:$GRAFANA_PORT"
  else
    SWFS_GRAFANA_URL="N/A"
  fi
else
  ctx logger info "SeaweedFS container (seaweed-mini) is not running."
  SWFS_RUNNING="false"
  SWFS_ADMIN_URL="N/A"
  SWFS_FILER_URL="N/A"
  SWFS_MASTER_URL="N/A"
  SWFS_S3_URL="N/A"
  SWFS_GRAFANA_URL="N/A"
  SWFS_USER="N/A"
  SWFS_PASSWORD="N/A"
fi

# Offline package upload logic
if [[ -f ~/"${OFFLINE_PACKAGE_NAME}" ]]; then
  ctx logger info "Offline package found: ${OFFLINE_PACKAGE_NAME}"
  ctx logger info "Upload package: $UPLOAD_OFFLINE_PACKAGE"
  if [[ ${UPLOAD_OFFLINE_PACKAGE,,} == "true" ]]; then
    ctx logger info "Uploading offline package..."
    new_offline_package_name="$(date +%Y%m%d%H%M)-${OFFLINE_PACKAGE_NAME}"
    mv ~/"${OFFLINE_PACKAGE_NAME}" ~/"${new_offline_package_name}"
    if [[ -z $UPLOAD_BASE_URL || -z $UPLOAD_OFFLINE_PACKAGE_USER || -z $UPLOAD_OFFLINE_PACKAGE_PASSWORD ]]; then
      ctx logger info "UPLOAD_BASE_URL, UPLOAD_OFFLINE_PACKAGE_USER, or UPLOAD_OFFLINE_PACKAGE_PASSWORD is missing."
      exit 1
    else
      OFFLINE_PACKAGE_URL="${UPLOAD_BASE_URL}${new_offline_package_name}"
      curl -ku "${UPLOAD_OFFLINE_PACKAGE_USER}:${UPLOAD_OFFLINE_PACKAGE_PASSWORD}" \
        -X POST "$OFFLINE_PACKAGE_URL" \
        -F "file=@$HOME/${new_offline_package_name}"
      if [[ $? -ne 0 ]]; then
        ctx logger info "Failed to upload offline package."
        exit 1
      fi
    fi
    OFFLINE_PACKAGE_UPLOADED="true"
    OFFLINE_PACKAGE_NAME="$new_offline_package_name"
    ctx logger info "Offline package uploaded to $OFFLINE_PACKAGE_URL."
  fi
else
  ctx logger info "Offline package (${OFFLINE_PACKAGE_NAME}) not found. Skipping upload."
  OFFLINE_PACKAGE_NAME="N/A"
fi

ctx logger info "Post install check completed."
ctx instance runtime-properties capabilities.swfs_running "$SWFS_RUNNING"
ctx instance runtime-properties capabilities.swfs_admin_url "$SWFS_ADMIN_URL"
ctx instance runtime-properties capabilities.swfs_filer_url "$SWFS_FILER_URL"
ctx instance runtime-properties capabilities.swfs_master_url "$SWFS_MASTER_URL"
ctx instance runtime-properties capabilities.swfs_s3_url "$SWFS_S3_URL"
ctx instance runtime-properties capabilities.swfs_grafana_url "$SWFS_GRAFANA_URL"
ctx instance runtime-properties capabilities.swfs_username "$SWFS_USER"
ctx instance runtime-properties capabilities.swfs_password "$SWFS_PASSWORD"
ctx instance runtime-properties capabilities.offline_package_name "$OFFLINE_PACKAGE_NAME"
ctx instance runtime-properties capabilities.offline_package_uploaded "$OFFLINE_PACKAGE_UPLOADED"
ctx instance runtime-properties capabilities.offline_package_url "$OFFLINE_PACKAGE_URL"
