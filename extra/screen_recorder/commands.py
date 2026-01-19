def get_ffmpeg_join_command(
    ffmpeg_cmd,
    vsync,
    files,
    filter_complex,
    vcodec,
    crf,
    preset,
    out_path,
    record_audio=False,
):
    cmd = [
        ffmpeg_cmd,
        "-vsync",
        vsync,
    ]
    for f in files:
        cmd.extend(["-i", f])

    final_filter = filter_complex
    if record_audio:
        # amerge=inputs=X combines the audio streams from all input files
        audio_streams = "".join(f"[{i}:a]" for i in range(len(files)))
        audio_filter = f"{audio_streams}amerge=inputs={len(files)}[aout]"
        final_filter = f"{filter_complex};{audio_filter}"

    cmd.extend(
        [
            "-filter_complex",
            final_filter,
            "-map",
            "[v_out]",
            "-c:v",
            vcodec,
            "-crf",
            crf,
            "-preset",
            preset,
        ]
    )

    if record_audio:
        cmd.extend(["-map", "[aout]"])

    cmd.append(out_path)
    return cmd


def get_wf_recorder_command(
    cmd_path, output_path, output_name=None, geometry=None, audio_flag=None
):
    """
    Constructs the wf-recorder command.
    Documentation notes:
    - Use --file for output path.
    - Use --audio to enable sound.
    - Use -g for geometry.
    - Use -o for specific output name.
    """
    cmd = [cmd_path, "--file", output_path]

    if output_name:
        cmd.extend(["-o", output_name])

    if geometry:
        cmd.extend(["-g", geometry])

    if audio_flag:
        # Passing the '--audio' flag here
        cmd.append(audio_flag)

    return cmd
