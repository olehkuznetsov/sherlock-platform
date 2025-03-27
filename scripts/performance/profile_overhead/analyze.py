import glob
import os
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from perfetto.trace_processor import TraceProcessor

def query_value_int(tp: TraceProcessor, sql_query: str) -> int:
    """
    Executes an SQL query on a Perfetto trace and returns a single value.

    Args:
        tp: The TraceProcessor instance.
        sql_query: The SQL query to execute.

    Returns:
        The single value returned by the query, or 0 if no rows are found.

    Raises:
        ValueError: If the query returns more than one row or more than one column.
    """
    qr_it = tp.query(sql_query)
    try:
        row = next(qr_it)
    except StopIteration:
        return 0  # No rows found

    try:
        next(qr_it)
        raise ValueError("Query returned more than one row.")
    except StopIteration:
        pass

    if len(vars(row)) > 1:
      raise ValueError("Query returned more than one column")

    value = getattr(row, next(iter(vars(row))))
    return 0 if value is None else value

replay_frames_period_ms_sql = """
select (MAX(s.ts) - MIN(s.ts)) / 1000000 as dur_ms from slice s, track t where s.track_id=t.id AND t.name like 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%'
"""

replay_period_ms_sql = """
select (MAX(ts + dur) - (select MIN(s.ts) from thread_state s, thread t, process p WHERE p.name="com.lunarg.gfxreconstruct.replay" AND s.state="Running" AND t.id=s.utid AND t.upid=p.upid))/1000000 as dur_ms from thread_state
"""

process_cpu_time_ms_sql = """
select 
  SUM(s.dur)/1000000 as dur_ms from thread_state s, thread t, process p 
WHERE 
  s.state="Running" 
  AND p.name="{process_name}"
  AND t.id=s.utid 
  AND t.upid=p.upid 
 AND s.ts >= (select MIN(s.ts) from slice s, track t where s.track_id=t.id AND t.name like 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%')
  AND s.ts < (select MAX(s.ts) from slice s, track t where s.track_id=t.id AND t.name like 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%')
"""

kworkers_cpu_time_ms_sql = """
select 
  SUM(s.dur)/1000000 as dur_ms from thread_state s, thread t, process p 
WHERE 
  s.state="Running" 
  AND p.name LIKE "kworker%"
  AND t.id=s.utid 
  AND t.upid=p.upid 
 AND s.ts >= (select MIN(s.ts) from slice s, track t where s.track_id=t.id AND t.name like 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%')
  AND s.ts < (select MAX(s.ts) from slice s, track t where s.track_id=t.id AND t.name like 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%')
"""

all_cpu_time_ms_sql = """
select 
  SUM(s.dur)/1000000 as dur_ms from thread_state s
WHERE 
  s.state="Running" 
 AND s.ts >= (select MIN(s.ts) from slice s, track t where s.track_id=t.id AND t.name like 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%')
  AND s.ts < (select MAX(s.ts) from slice s, track t where s.track_id=t.id AND t.name like 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%')
"""

cpu_count_sql = """
SELECT COUNT(DISTINCT cpu)
  FROM counter c, cpu_counter_track t
WHERE c.track_id = t.id
  AND t.name = 'cpufreq'
  AND c.ts <= (select MIN(s.ts) from slice s, track t where s.track_id=t.id AND t.name like 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%')
"""

cpu_avg_freq_sql = """
SELECT AVG(value) AS freq
  FROM counter c, cpu_counter_track t
WHERE c.track_id = t.id
  AND t.name = 'cpufreq'
  AND c.ts <= (select MIN(s.ts) from slice s, track t where s.track_id=t.id AND t.name like '%APP_0 com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%')
"""

replay_frames_count_sql = """
SELECT COUNT(*)
FROM slice s
JOIN track t ON s.track_id = t.id
WHERE t.name LIKE 'APP_% com.lunarg.gfxreconstruct.replay/android.app.NativeActivity%'
"""

def process_perfetto_file(file):
    """Processes a single Perfetto file and returns the extracted data."""
    print(f"Processing {file}")
    if True:
        tp = TraceProcessor(trace=file)

        trace_size = os.path.getsize(file) / 1024
        if trace_size == 0:
            print(f"Skipped empty {file}")
            return
        
        base_name, attempt_str = os.path.splitext(os.path.basename(file))[0].rsplit('_', 1)
        
        row = {'Test name': f"|{os.path.basename(file)}", 'base_name': base_name}
#        row['CPUs'] = query_value_int(tp, cpu_count_sql)
        cpu_freq = query_value_int(tp, cpu_avg_freq_sql) / 1000000.0;
#        if cpu_freq < 3.1:
#            shutil.move(file, "slow/")
#            return
        row['\"Game\" s'] = round(query_value_int(tp, process_cpu_time_ms_sql.format(process_name='com.lunarg.gfxreconstruct.replay')) / 1000.0, 2)
        analyzed_part_duration_ms = query_value_int(tp, replay_frames_period_ms_sql)
        if analyzed_part_duration_ms == 0:
            print(f"!!!analyzed_part_duration_ms == 0 for {file}");
            
        percent_k = 100.0 / analyzed_part_duration_ms
        replay_frames = query_value_int(tp, replay_frames_count_sql)
        replay_duration_s = query_value_int(tp, replay_period_ms_sql) / 1000.0

        if replay_duration_s == 0:
            print(f"!!!replay_duration_s == 0 for {file}");
        row['FPS'] = round(replay_frames / (analyzed_part_duration_ms / 1000.0), 2);
#        row['Replay duration s'] = round(query_value_int(tp, replay_period_ms_sql) / 1000.0, 2)
        row['Replay frames'] = replay_frames
        row['Perfetto size KB/s'] = round(trace_size / replay_duration_s, 1)
        row['Used CPU time %'] = round(percent_k * query_value_int(tp, all_cpu_time_ms_sql), 2)
        row['\"Game\" %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='com.lunarg.gfxreconstruct.replay')), 2)
        row['agi_launch_producer %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='./tmp/agi_launch_producer')), 2)
        row['traced %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='/system/bin/traced')), 2)
        row['traced_probes %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='/system/bin/traced_probes')), 2)
        row['kworkers %'] = round(percent_k * query_value_int(tp, kworkers_cpu_time_ms_sql), 2)
        row['mali-gpuq-kthread %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='mali-gpuq-kthread')), 2)
        row['surfaceflinger %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='/system/bin/surfaceflinger')), 2)
        row['android.hardware.power.stats-service.pixel %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='/vendor/bin/hw/android.hardware.power.stats-service.pixel')), 2)
        row['android.hardware.power-service.pixel-libperfmgr %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='/vendor/bin/hw/android.hardware.power-service.pixel-libperfmgr')), 2)
        row['logd %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='/system/bin/logd')), 2)
        row['logcat %'] = round(percent_k * query_value_int(tp, process_cpu_time_ms_sql.format(process_name='logcat')), 2)

        # ... add more queries and data extraction here ...
        row['Analyzed part duration s'] = round(analyzed_part_duration_ms / 1000.0, 2)
        row['CPUs'] = query_value_int(tp, cpu_count_sql)
        row['CPU max freq MHz'] = round(cpu_freq, 2)

        return row
   
data = {}
perfetto_files = glob.glob("perfetto_results/*.perfetto")

with ThreadPoolExecutor(max_workers=64) as executor:
    futures = {executor.submit(process_perfetto_file, file): file for file in perfetto_files}

    for future in as_completed(futures):
        file = futures[future]
        row = future.result()
        if row:
            base_name = row['base_name']
            del row['base_name']
            if base_name not in data:
                data[base_name] = {'Test name': base_name, 'attempts': []}
            data[base_name]['attempts'].append(row)

# Calculate averages for each base name
for base_name, base_data in data.items():
    attempts = base_data['attempts']
    avg_row = {}
    for key in attempts[0].keys():
        try:
            avg_row[key] = round(sum(attempt[key] for attempt in attempts) / len(attempts), 1)
        except (KeyError, TypeError):
            avg_row[key] = "N/A"
    avg_row['Test name'] = base_name
    data[base_name]['avg'] = avg_row

output_data = []
for base_name, base_data in data.items():
    output_data.append(base_data['avg'])
    output_data.extend(base_data['attempts'])

def sort_by_base_name_and_game(row):
    test_name = row["Test name"]
    base_name = test_name.split("~")[0]
    return (base_name, float(row['"Game" s']))

output_data.sort(key=sort_by_base_name_and_game)

with open('perfetto_data.csv', 'w', newline='') as csvfile:
    fieldnames = output_data[0].keys() if output_data else []
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_data)

print("Done")