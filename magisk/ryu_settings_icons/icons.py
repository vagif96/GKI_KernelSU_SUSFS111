# Preference key -> (Material Design Icons name from @mdi/js, background colour ARGB)
# Colours follow the HyperOS main settings palette.
BLUE = "#ff3482ff"
GREEN = "#ff1dcd3a"
YELLOW = "#ffffb21d"
ORANGE = "#ffff8a1d"
RED = "#fffa382e"
GRAY = "#ff8c9db0"
PURPLE = "#ff8a63ff"
TEAL = "#ff12b5c4"
PINK = "#ffff4f8b"

ICONS = {
    # Настройки системы
    "date_time_settings": ("mdiClockTimeFour", BLUE),
    "language_settings": ("mdiWeb", TEAL),
    "locale_settings": ("mdiFlag", ORANGE),
    # Специальные функции
    "circle_to_search_switch": ("mdiMagnifyScan", BLUE),
    "back_strap": ("mdiGestureDoubleTap", PURPLE),
    "game_booster": ("mdiGamepadVariant", RED),
    "beauty_fc_assistant": ("mdiFaceWomanShimmer", PINK),
    "conversation_assistant": ("mdiForum", GREEN),
    "securitycenter_sidebar_box": ("mdiDockRight", BLUE),
    "taplus_settings": ("mdiGestureTapHold", ORANGE),
    "smart_clipboard_settings": ("mdiClipboardText", TEAL),
    "freeform_guide_settings": ("mdiPictureInPictureTopRight", PURPLE),
    "mi_wallet_settings": ("mdiWallet", ORANGE),
    "screen_recorder": ("mdiRecordRec", RED),
    "miui_desktop_mode_settings": ("mdiMonitor", BLUE),
    "external_ram": ("mdiMemory", GREEN),
    "parental_control": ("mdiShieldAccount", YELLOW),
    "kid_space_settings": ("mdiBabyFaceOutline", YELLOW),
    "edge_settings": ("mdiHandBackRight", GRAY),
    "speaker_settings": ("mdiSpeaker", TEAL),
    "easy_mode_pref": ("mdiFormatSize", ORANGE),
    "led_settings": ("mdiLightbulbOn", YELLOW),
    "video_tool_box": ("mdiMovieOpen", RED),
    "quick_reply": ("mdiMessageReplyText", GREEN),
    "color_lamp_settings": ("mdiPalette", PURPLE),
    "second_space": ("mdiLayers", BLUE),
    "slider_display": ("mdiTune", GRAY),
    "color_led_settings": ("mdiLedStripVariant", PURPLE),
    "color_game_led_settings": ("mdiLedOn", PINK),
    "health_global": ("mdiHeartPulse", RED),
    "shoulder_key_settings": ("mdiGamepad", RED),
    "miui_voip_assistant_screen": ("mdiPhoneInTalk", GREEN),
    "glove_mode_settings": ("mdiHandBackLeft", GRAY),
    # Аккаунты
    "user_settings": ("@existing:ic_multiple_users", None),
    "account_sync_settings": ("mdiSync", BLUE),
    "enterprise_mode_settings": ("mdiBriefcase", GRAY),
    # Для разработчиков
    "ai_caption": ("mdiClosedCaption", BLUE),
    "extension_function_settings": ("mdiPuzzle", PURPLE),
    "development_settings": ("mdiCodeBraces", GRAY),
}
