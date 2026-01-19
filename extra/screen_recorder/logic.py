import urllib.parse


async def on_record_all_clicked(plugin):
    plugin.popdown()
    if plugin.is_recording:
        plugin.notifier.notify_send(
            "Recording Already Running",
            "Stop the current recording first.",
            "record",
        )
        return
    await start_recording_all(plugin)


async def start_recording_all(plugin):
    from .commands import get_wf_recorder_command

    plugin.record_processes = []
    plugin.output_files = []
    outputs = plugin.ipc.list_outputs()

    if not outputs:
        plugin.logger.error("No outputs found to record.")
        return

    for output in outputs:
        name = output["name"]
        path = plugin.os.path.join(plugin.video_dir, f"{name}{plugin.output_format}")
        plugin.output_files.append(path)

        audio_flag = plugin.wf_recorder_audio_flag if plugin.record_audio else None
        cmd = get_wf_recorder_command(
            plugin.wf_recorder_cmd, path, output_name=name, audio_flag=audio_flag
        )

        try:
            proc = await plugin.asyncio.create_subprocess_exec(*cmd)
            plugin.record_processes.append(proc)
        except Exception as e:
            plugin.logger.exception(f"Failed to start wf-recorder for {name}: {e}")

    if plugin.record_processes:
        plugin.is_recording = True
        # Set the recording icon from settings
        plugin.button.set_icon_name(
            plugin.gtk_helper.icon_exist(
                "media-playback-stop-symbolic",
                plugin.recording_icon_fallbacks,
            )
        )
        plugin.button.set_tooltip_text("Stop Recording All")


async def on_record_output_clicked(plugin, output_name):
    from .commands import get_wf_recorder_command

    plugin.popdown()
    if plugin.is_recording:
        return
    outputs = plugin.ipc.list_outputs()
    if not any(o["name"] == output_name for o in outputs):
        return
    plugin.record_processes = []
    plugin.output_files = []
    timestamp = plugin.glib.DateTime.new_now_utc().format("%Y%m%d_%H%M%S")
    path = plugin.os.path.join(
        plugin.final_dir, f"{output_name}_{timestamp}{plugin.output_format}"
    )
    plugin.output_files.append(path)
    audio_flag = plugin.wf_recorder_audio_flag if plugin.record_audio else None
    cmd = get_wf_recorder_command(
        plugin.wf_recorder_cmd,
        path,
        output_name=output_name,
        audio_flag=audio_flag,
    )
    try:
        proc = await plugin.asyncio.create_subprocess_exec(*cmd)
        plugin.record_processes.append(proc)
        plugin.is_recording = True

        plugin.button.set_icon_name(
            plugin.gtk_helper.icon_exist(
                "media-playback-stop-symbolic",
                plugin.recording_icon_fallbacks,
            )
        )
        plugin.button.set_tooltip_text("Stop Recording")
    except Exception as e:
        plugin.logger.exception(f"Failed to start wf-recorder: {e}")


async def on_record_slurp_clicked(plugin):
    from .commands import get_wf_recorder_command

    plugin.popdown()
    if plugin.is_recording:
        return
    plugin.record_processes = []
    plugin.output_files = []
    try:
        proc = await plugin.asyncio.create_subprocess_exec(
            plugin.slurp_cmd, stdout=plugin.asyncio.subprocess.PIPE
        )
        geometry_bytes, _ = await plugin.asyncio.wait_for(
            proc.communicate(), timeout=plugin.slurp_timeout_seconds
        )
        geometry = geometry_bytes.decode("utf-8").strip()
        if not geometry:
            return
    except Exception as e:
        plugin.logger.exception(f"Slurp failed: {e}")
        return
    timestamp = plugin.glib.DateTime.new_now_utc().format("%Y%m%d_%H%M%S")
    path = plugin.os.path.join(
        plugin.final_dir, f"region_{timestamp}{plugin.output_format}"
    )
    plugin.output_files.append(path)
    audio_flag = plugin.wf_recorder_audio_flag if plugin.record_audio else None
    cmd = get_wf_recorder_command(
        plugin.wf_recorder_cmd, path, geometry=geometry, audio_flag=audio_flag
    )
    try:
        proc = await plugin.asyncio.create_subprocess_exec(*cmd)
        plugin.record_processes.append(proc)
        plugin.is_recording = True
        plugin.button.set_icon_name(
            plugin.gtk_helper.icon_exist(
                plugin.main_icon_name,
                plugin.recording_icon_fallbacks,
            )
        )
    except Exception as e:
        plugin.logger.exception(f"Failed to start wf-recorder: {e}")


async def on_stop_and_join_clicked(plugin):
    if not plugin.is_recording:
        return
    await stop_recorders(plugin)
    valid_output_files = [f for f in plugin.output_files if plugin.os.path.exists(f)]
    num_files = len(valid_output_files)
    canonical_path = plugin.os.path.realpath(plugin.final_dir)
    directory_uri = f"file://{urllib.parse.quote(canonical_path)}"
    if num_files > 1:
        plugin.global_loop.create_task(join_with_ffmpeg(plugin))
    elif num_files == 1:
        plugin.notifier.notify_send(
            "Recording Complete",
            f"Video saved to: {valid_output_files[0]}",
            "record",
            hints={"uri": directory_uri},
        )


async def stop_recorders(plugin):
    plugin.popdown()
    if not plugin.record_processes:
        return

    for p in plugin.record_processes:
        try:
            p.terminate()
        except Exception:
            pass

    stop_tasks = [plugin.asyncio.create_task(p.wait()) for p in plugin.record_processes]
    await plugin.asyncio.wait(stop_tasks, timeout=5)

    plugin.record_processes.clear()
    plugin.is_recording = False

    # If we are NOT about to join (e.g. only 1 file), reset icon now.
    # If we are joining, join_with_ffmpeg should handle the final reset.
    if len(plugin.output_files) <= 1:
        plugin.button.set_icon_name(
            plugin.gtk_helper.icon_exist(
                plugin.main_icon_name,
                plugin.main_icon_fallbacks,
            )
        )
        plugin.button.set_tooltip_text("Start Screen Recording")


async def join_with_ffmpeg(plugin):
    from .commands import get_ffmpeg_join_command
    import shutil

    files_to_join = [
        f
        for f in plugin.output_files
        if plugin.os.path.exists(f) and f.startswith(plugin.video_dir)
    ]
    if not files_to_join:
        return
    outputs = plugin.ipc.list_outputs()
    geometries = [o["geometry"] for o in outputs if "geometry" in o]
    if not geometries:
        return
    min_height = min(g["height"] for g in geometries)
    num_outputs = len(files_to_join)
    timestamp = plugin.glib.DateTime.new_now_utc().format("%Y%m%d_%H%M%S")
    out_path = plugin.os.path.join(
        plugin.final_dir, f"joined_{timestamp}{plugin.output_format}"
    )
    filter_parts = []
    input_v = ""
    for i in range(num_outputs):
        filter_parts.append(f"[{i}:v]scale=-1:{min_height},setsar=1[v{i}]")
        input_v += f"[v{i}]"
    if num_outputs > 1:
        filter_parts.append(f"{input_v}hstack=inputs={num_outputs}[v_out]")
    else:
        filter_parts[-1] += "[v_out]"
    filter_complex = ";".join(filter_parts)

    cmd = get_ffmpeg_join_command(
        plugin.ffmpeg_cmd,
        plugin.ffmpeg_vsync,
        files_to_join,
        filter_complex,
        plugin.ffmpeg_vcodec,
        plugin.ffmpeg_crf,
        plugin.ffmpeg_preset,
        out_path,
        record_audio=plugin.record_audio,
    )

    try:
        proc = await plugin.asyncio.create_subprocess_exec(
            *cmd, stderr=plugin.asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if proc.returncode == 0:
            directory_uri = f"file://{urllib.parse.quote(plugin.os.path.realpath(plugin.final_dir))}"
            plugin.notifier.notify_send(
                "Recording Complete",
                f"Videos joined: {out_path}",
                "record",
                hints={"uri": directory_uri},
            )
    except Exception as e:
        plugin.logger.exception(f"FFmpeg error: {e}")

    try:
        shutil.rmtree(plugin.video_dir)
    except Exception:
        pass
    plugin._setup_directories()
