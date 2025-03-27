import subprocess
import os
import time
from enum import Enum

#adb shell setenforce 0

APP_ON_DEVICE_PACKAGE_NAME = "com.lunarg.gfxreconstruct.replay"
#APP_ON_DEVICE_PACKAGE_NAME = "com.google.android.gapid.arm64v8a"


def run_adb(command):
    full_command = f"adb {command}"
    try:
        result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
        result.check_returncode()  # Raise CalledProcessError if return code is non-zero
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {full_command}")
        print(f"Return code: {e.returncode}")
        print(f"Standard Output: {e.stdout}")
        print(f"Standard Error: {e.stderr}")
        exit(-1)

def run_adb_shell(command):
    full_command = f"shell {command}"
    return run_adb(full_command)

def has_result(shell_command):
    process_check = subprocess.run(
            f"adb shell {shell_command}",
            shell=True,
            capture_output=True,
            text=True
        )
        
    if process_check.stdout:
        return True
    return False
 
def start_agi_launch_producer():
    run_adb_shell("setprop debug.graphics.gpu.profiler.perfetto 1")
    print("Pushing agi_launch_producer...", end='', flush=True)
    run_adb("push apk/arm64/agi_launch_producer /data/local/tmp")
    run_adb_shell("chmod +x /data/local/tmp/agi_launch_producer")
    print("Starting agi_launch_producer in background...", end='', flush=True)
    try:
        run_adb_shell("nohup /data/local/tmp/agi_launch_producer > /dev/null 2>&1 &")
        time.sleep(1.5) # Give it a bit more time to potentially fail or start
        pid_check = subprocess.run(
            "adb shell pidof agi_launch_producer",
            shell=True, capture_output=True, text=True, timeout=5
        )
        if pid_check.returncode == 0 and pid_check.stdout.strip():
            print(f" Done (PID: {pid_check.stdout.strip()}).")
            return True
        print(" Failed (Process not found after start attempt).")
    except Exception as e:
        print(f"\nError starting agi_launch_producer: {e}")
    return False

def stop_agi_launch_producer():
    print("Stopping agi_launch_producer...", end='', flush=True)
    run_adb_shell("setprop debug.graphics.gpu.profiler.perfetto 0")
    try:
        pid_check = subprocess.run(
            "adb shell pidof agi_launch_producer",
            shell=True, capture_output=True, text=True, timeout=5
        )
        if pid_check.returncode == 0 and pid_check.stdout.strip():
            pid = pid_check.stdout.strip()
            run_adb_shell(f"kill -9 {pid}")
            print(" done.")
        else:
            print(" agi_launch_producer not found.")
    except Exception as e:
        print(f"\nError during stop_agi_launch_producer: {e}")
    return 

def install_apk(apk_path):
    print(f"Installing {apk_path}...", end='', flush=True);
    run_adb(f"install -g -t -r --force-queryable {apk_path}")
    print("Done.")
    return
    
def install_apks():
    if not has_result("cmd package list packages | grep com.google.android.gapid.arm64v8a"):
        install_apk("apk/arm64/gapid-arm64-v8a.apk")
    if not has_result("cmd package list packages | grep com.lunarg.gfxreconstruct.replay"):
        install_apk("apk/arm64/replay-release.apk")
    if not has_result('cmd package list packages | grep -E "^package:com.google.sokatoa$"'):
        install_apk("apk/arm64/signed_sokatoa.apk")
    run_adb_shell("appops set com.lunarg.gfxreconstruct.replay MANAGE_EXTERNAL_STORAGE allow")
    return

def add_to_global_setting(setting_name, new_value):
    try:
        # Get the current value of the setting
        result = run_adb_shell(f"settings get global {setting_name}")
        current_value = result.stdout.strip()

        # Check if the setting exists and handle "null" string
        if current_value == "null":
            updated_value = new_value
        elif new_value in current_value.split(':'):
            print(f"Value '{new_value}' already exists in setting '{setting_name}'. Skipping.")
            return
        else:
            updated_value = f"{current_value}:{new_value}"        

        # Put the updated value back into the setting
        run_adb_shell(f"settings put global {setting_name} {updated_value}")
        print(f"Successfully added '{new_value}' to setting '{setting_name}'. New value: '{updated_value}'")

    except subprocess.CalledProcessError as e:
        print(f"Error updating setting '{setting_name}': {e}")

GFXR_MODE_NONE = 1
GFXR_MODE_TRACKING = 2
GFXR_MODE_CAPTURE = 3
GFXR_MODE_TRACKING_ASSISSTED = 4
GFXR_MODE_CAPTURE_ASSISSTED = 5

AGI_NONE = 1
AGI_LAYER = 2

SOKATOA_NONE = 1
SOKATOA_LAYER = 2

def run_app_on_device(device_gfxr_replay_path):
    if APP_ON_DEVICE_PACKAGE_NAME == 'com.google.android.gapid.arm64v8a':
        run_adb_shell("am start -S -W -a android.intent.action.MAIN com.google.android.gapid.arm64v8a/com.google.android.gapid.VkSampleActivity")
        return
    gfxrecon_cmd = f"python3 gfxr/scripts/gfxrecon.py replay {device_gfxr_replay_path}"
    subprocess.run(gfxrecon_cmd, shell=True, check=True)

def set_gfxr_mode(gfxr_mode):
    if gfxr_mode == GFXR_MODE_TRACKING or gfxr_mode == GFXR_MODE_CAPTURE or gfxr_mode == GFXR_MODE_TRACKING_ASSISSTED or gfxr_mode == GFXR_MODE_CAPTURE_ASSISSTED:
        if gfxr_mode == GFXR_MODE_TRACKING or gfxr_mode == GFXR_MODE_CAPTURE:
            run_adb_shell("setprop debug.gfxrecon.memory_tracking_mode page_guard")
        if gfxr_mode == GFXR_MODE_TRACKING_ASSISSTED or gfxr_mode == GFXR_MODE_CAPTURE_ASSISSTED:
            run_adb_shell("setprop debug.gfxrecon.memory_tracking_mode assisted")
        add_to_global_setting("gpu_debug_layers", "VK_LAYER_LUNARG_gfxreconstruct")
        add_to_global_setting("gpu_debug_layer_app", "com.lunarg.gfxreconstruct.replay")
    run_adb_shell(f"setprop debug.gfxrecon.capture_android_trigger {gfxr_mode == GFXR_MODE_CAPTURE}")

def set_agi_mode(agi_mode):
    if agi_mode == AGI_LAYER:
        add_to_global_setting("gpu_debug_layers", "CPUTiming")
        add_to_global_setting("gpu_debug_layer_app", "com.google.android.gapid.arm64v8a")

def set_sokatoa_mode(sokatoa_mode):
    if sokatoa_mode == SOKATOA_LAYER:
        add_to_global_setting("gpu_debug_layers", "VK_LAYER_GOOGLE_sokatoa")
        add_to_global_setting("gpu_debug_layer_app", "com.google.sokatoa")
        run_adb_shell("setprop debug.sokatoa.perfetto.enabled true")
        run_adb_shell("setprop debug.sokatoa.gfxr.enabled false")
        run_adb_shell("setprop debug.sokatoa.start.frame 50")
        run_adb_shell("setprop debug.sokatoa.end.frame 100")
        run_adb_shell("setprop debug.sokatoa.frame.offset 0")        

def run_benchmark(gfxr_replay_path, device_gfxr_replay_path, perfetto_config, perfetto_result_path, gfxr_mode=GFXR_MODE_NONE, agi_mode=AGI_NONE, sokatoa_mode=SOKATOA_NONE):
    PERFETTO_SESSION_ID = "session4345"

    print(f'Pushing \"{gfxr_replay_path}\"... ', end='', flush=True)
    run_adb(f"push --sync \"{gfxr_replay_path}\" /sdcard/Download/")
    print('done.')

    run_adb_shell("settings put global enable_gpu_debug_layers 0")
    run_adb_shell("settings delete global gpu_debug_layers")
    run_adb_shell("settings delete global gpu_debug_layer_app")
    run_adb_shell(f"settings put global gpu_debug_app {APP_ON_DEVICE_PACKAGE_NAME}")

    set_gfxr_mode(gfxr_mode)
    set_agi_mode(agi_mode)
    set_sokatoa_mode(sokatoa_mode)

    if run_adb_shell("settings get global gpu_debug_app").stdout.strip() != "None":
        run_adb_shell("settings put global enable_gpu_debug_layers 1")

    run_adb(f"push perfetto_configs/{perfetto_config} /data/misc/perfetto-configs/perfetto.txt")
    run_adb_shell(
        f"perfetto --txt -c /data/misc/perfetto-configs/perfetto.txt -o /data/misc/perfetto-traces/result.perfetto --detach={PERFETTO_SESSION_ID}"
    )
    
    time.sleep(1)

    run_adb_shell("cmd power set-fixed-performance-mode-enabled true")
    
    # Run gfxrecon replay
    run_app_on_device(device_gfxr_replay_path) 
    
    while True:
        process_check = subprocess.run(
            f"adb shell ps | grep {APP_ON_DEVICE_PACKAGE_NAME}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if not process_check.stdout:
            print("done. Stopping perfetto.")
            break
        else:
            print(".", end='', flush=True)
            time.sleep(2)

    run_adb_shell("cmd power set-fixed-performance-mode-enabled false")
    
    run_adb_shell(f"perfetto --attach={PERFETTO_SESSION_ID} --stop")
    run_adb(f"pull /data/misc/perfetto-traces/result.perfetto {perfetto_result_path}")
    if gfxr_mode == GFXR_MODE_CAPTURE:
        run_adb_shell(f"rm /sdcard/Download/test*.gfxr")

    run_adb_shell("settings put global enable_gpu_debug_layers 0")
    run_adb_shell("settings delete global gpu_debug_layers")
    run_adb_shell("settings delete global gpu_debug_app")
    return

device_model = run_adb_shell("getprop ro.product.model").stdout.strip()
print(f"Device model: {device_model}")

replay_fnames = [
#    'vampire_survivors.gfxr',
    'roblox.gfxr',
#     'asphalt9.gfxr'
]

gfxr_modes = [
    GFXR_MODE_NONE,
#    GFXR_MODE_CAPTURE,
#    GFXR_MODE_TRACKING,
#    GFXR_MODE_CAPTURE_ASSISSTED,
#    GFXR_MODE_TRACKING_ASSISSTED
]

agi_modes = [
#    AGI_NONE,
    AGI_LAYER
]    

sokatoa_modes = [
    SOKATOA_NONE,
#    SOKATOA_LAYER
]    

perfetto_configs = [
#    'perfetto-config-min.txt',
    'perfetto-config-5-counters.txt',
#    'perfetto-config-100-counters.txt',
#    'perfetto-config-348-counters.txt',
#    'perfetto-config-base.txt',
#    'perfetto-config-base-noVkCommandBuffer.txt',
]

install_apks()
start_agi_launch_producer()

for attempt in range(1, 2):  # Attemtps
    for replay_fname in replay_fnames:
        for perfetto_config in perfetto_configs:
            for gfxr_mode in gfxr_modes:
                for agi_mode in agi_modes:
                    for sokatoa_mode in sokatoa_modes:
                        # Construct the base output file name
                        base_name = os.path.splitext(replay_fname)[0]  # Remove .gfxr extension

                        if gfxr_mode == GFXR_MODE_NONE:
                            gfxr_mode_str = ""
                        elif gfxr_mode == GFXR_MODE_CAPTURE:
                            gfxr_mode_str = "_gfxr_capture"
                        elif gfxr_mode == GFXR_MODE_TRACKING:
                            gfxr_mode_str = "_gfxr_tracking"
                        elif gfxr_mode == GFXR_MODE_CAPTURE_ASSISSTED:
                            gfxr_mode_str = "_gfxr_capture_assisted"
                        elif gfxr_mode == GFXR_MODE_TRACKING_ASSISSTED:
                            gfxr_mode_str = "_gfxr_tracking_assisted"

                        if agi_mode == AGI_NONE:
                            agi_mode_str = ""
                        elif agi_mode == AGI_LAYER:
                            agi_mode_str = "_agi"

                        if sokatoa_mode == SOKATOA_NONE:
                            sokatoa_mode_str = ""
                        elif sokatoa_mode == SOKATOA_LAYER:
                            sokatoa_mode_str = "_sokatoa"

                        # Add Perfetto config to the output file name
                        perfetto_config_name = os.path.splitext(perfetto_config)[0]  # Remove .txt extension
                        perfetto_config_name = perfetto_config_name.replace("perfetto-config-", "") # Remove "perfetto-config-" prefix

                        # Create the final output file path with attempt number
                        perfetto_result_path = f"perfetto_results/{base_name}~{perfetto_config_name}{gfxr_mode_str}{agi_mode_str}{sokatoa_mode_str}_{attempt}.perfetto"
                        print(perfetto_result_path)

                        if os.path.exists(perfetto_result_path):
        #                    print(f"Skipping {perfetto_result_path} (already exists)")
                            continue

                        # Run the benchmark
                        run_benchmark(
                            gfxr_replay_path=f"tests/{device_model}/{replay_fname}",
                            device_gfxr_replay_path=f"/sdcard/Download/{replay_fname}",
                            perfetto_config=perfetto_config,
                            perfetto_result_path=f"{perfetto_result_path}",
                            gfxr_mode=gfxr_mode,
                            agi_mode=agi_mode,
                            sokatoa_mode=sokatoa_mode
                        )
                        print(f"Done {perfetto_result_path}")

                        time.sleep(10)

stop_agi_launch_producer()
