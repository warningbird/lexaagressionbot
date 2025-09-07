def format_in_style(core_message: str, style: str = "toxic") -> str:
    footer = ""
    if style == "toxic":
        footer = "\n\nДОЛБОЕБЫ, вы вообще читаете? Долбоёбы, соберитесь. ДОЛБОЕБЫ, не тупите."
    return f"{core_message}{footer}"


