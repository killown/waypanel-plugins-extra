def setup_plugin_settings(plugin):
    """Registers all settings for the Screen Recorder plugin."""

    # Execution Commands
    plugin.wf_recorder_cmd = plugin.get_plugin_setting_add_hint(
        ["commands", "wf_recorder_cmd"],
        "wf-recorder",
        "The executable path for the Wayfire screen recorder utility.",
    )

    plugin.slurp_cmd = plugin.get_plugin_setting_add_hint(
        ["commands", "slurp_cmd"],
        "slurp",
        "The executable path for the slurp region selection tool.",
    )

    plugin.ffmpeg_cmd = plugin.get_plugin_setting_add_hint(
        ["commands", "ffmpeg_cmd"],
        "ffmpeg",
        "The executable path for the FFmpeg video processing utility.",
    )

    # Recording Options
    plugin.wf_recorder_audio_flag = plugin.get_plugin_setting_add_hint(
        ["recording", "audio_flag"],
        "--audio",
        "The flag passed to wf-recorder to enable audio recording.",
    )

    plugin.output_format = plugin.get_plugin_setting_add_hint(
        ["recording", "output_format"],
        ".mp4",
        "The file extension and format for recorded videos.",
    )

    plugin.slurp_timeout_seconds = plugin.get_plugin_setting_add_hint(
        ["recording", "slurp_timeout_seconds"],
        5,
        "Timeout for slurp to wait for a region selection.",
    )

    plugin.record_audio_default = plugin.get_plugin_setting_add_hint(
        ["recording", "record_audio_default"],
        False,
        "Default state for the 'Record Audio' toggle.",
    )

    # FFmpeg Joining Settings
    plugin.ffmpeg_vsync = plugin.get_plugin_setting_add_hint(
        ["ffmpeg", "vsync_value"],
        "2",
        "The '-vsync' value used during FFmpeg joining.",
    )

    plugin.ffmpeg_vcodec = plugin.get_plugin_setting_add_hint(
        ["ffmpeg", "video_codec"],
        "libx264",
        "The video codec used by FFmpeg for joining.",
    )

    plugin.ffmpeg_crf = plugin.get_plugin_setting_add_hint(
        ["ffmpeg", "crf_value"],
        "23",
        "The Constant Rate Factor (CRF) used by FFmpeg.",
    )

    plugin.ffmpeg_preset = plugin.get_plugin_setting_add_hint(
        ["ffmpeg", "preset"],
        "veryfast",
        "The encoding preset used by FFmpeg.",
    )

    # Icon Fallbacks
    plugin.main_icon_name = plugin.get_plugin_setting_add_hint(
        ["icons", "main_icon_name"],
        "screen_recorder",
        "Primary icon name for the button when not recording.",
    )

    plugin.main_icon_fallbacks = plugin.get_plugin_setting_add_hint(
        ["icons", "main_icon_fallbacks"],
        [
            "deepin-screen-recorder-symbolic",
            "simplescreenrecorder-panel",
            "media-record-symbolic",
        ],
        "Fallback icon names when recorder is stopped.",
    )

    plugin.recording_icon_fallbacks = plugin.get_plugin_setting_add_hint(
        ["icons", "recording_icon_fallbacks"],
        [
            "simplescreenrecorder-recording",
            "media-playback-stop-symbolic",
        ],
        "Icon names to use when the recorder is active.",
    )

    # Directory Settings
    plugin.temp_dir_format = plugin.get_plugin_setting_add_hint(
        ["paths", "temp_dir_format"],
        "/tmp/wfrec_{pid}",
        "Format string for the temporary directory path.",
    )

    plugin.videos_dir_fallback = plugin.get_plugin_setting_add_hint(
        ["paths", "videos_dir_fallback"],
        "Videos",
        "Fallback subdirectory if XDG_VIDEOS_DIR is not defined.",
    )
