#!/bin/bash

#TARGET=com.poncle.vampiresurvivors
TARGET=com.roblox.client
GFXR_REPLAY_NAME=roblox

echo "Target package name: $TARGET"
echo "Result capture name: $GFXR_REPLAY_NAME.gfxr"

# Get device model
MODEL=$(adb shell getprop ro.product.model)
echo "Device model: $MODEL"

# Setup GFXReconstruct capture prerequisites
echo "Installing replay APK..."
adb install apk/arm64/replay-release.apk
echo "Granting permissions..."
adb shell pm grant ${TARGET} android.permission.WRITE_EXTERNAL_STORAGE
adb shell appops set com.lunarg.gfxreconstruct.replay MANAGE_EXTERNAL_STORAGE allow
echo "Setting GFXReconstruct properties..."
TEMP_CAPTURE_BASE="/sdcard/Download/${GFXR_REPLAY_NAME}_temp"
adb shell setprop debug.gfxrecon.capture_file "${TEMP_CAPTURE_BASE}"
adb shell settings put global gpu_debug_app ${TARGET}
adb shell settings put global enable_gpu_debug_layers 1
adb shell settings put global gpu_debug_layers VK_LAYER_LUNARG_gfxreconstruct
adb shell settings put global gpu_debug_layer_app com.lunarg.gfxreconstruct.replay

echo "Restart ${TARGET} application and select scene to capture"
read -n 1 -s -r -p "Press any key to start capture..."
adb shell setprop debug.gfxrecon.capture_android_trigger true

echo
read -n 1 -s -r -p "Press any key to stop capture..."
adb shell setprop debug.gfxrecon.capture_android_trigger false

echo "Waiting a moment for capture file finalization..."
sleep 5

DESTINATION_DIR="tests/${MODEL}"
echo "Creating local directory: ${DESTINATION_DIR}"
mkdir -p "${DESTINATION_DIR}"

# Find the exact name of the capture file on the device.
# GFXReconstruct appends timestamps (e.g., _temp_001.gfxr).
echo "Searching for capture file on device (pattern: ${TEMP_CAPTURE_BASE}*)..."
SOURCE_FULL_PATH=$(adb shell find /sdcard/Download/ -maxdepth 1 -name "${GFXR_REPLAY_NAME}_temp*" -print -quit | tr -d '\r\n')

# Check if a file was found
if [ -z "$SOURCE_FULL_PATH" ]; then
  echo "Error: No capture file found matching /sdcard/Download/${GFXR_REPLAY_NAME}_temp*"
  exit 1 # Exit with an error code
fi

DESTINATION_FILE="${DESTINATION_DIR}/${GFXR_REPLAY_NAME}.gfxr"

echo "Found capture file: ${SOURCE_FULL_PATH}"
echo "Pulling file to local path: ${DESTINATION_FILE}"
adb pull "${SOURCE_FULL_PATH}" "${DESTINATION_FILE}"

# Check if adb pull was successful (exit status $? should be 0)
if [ $? -eq 0 ]; then
  echo "Pull successful."
  adb shell rm "${SOURCE_FULL_PATH}"
else
  echo "Error: adb pull failed."
  exit 1
fi

