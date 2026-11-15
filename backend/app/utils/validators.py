def validate_full_name(value: str) -> str:
    """Trim names and reject values that are empty or whitespace-only."""
    cleaned_value = value.strip()
    if not cleaned_value:
        raise ValueError("Full name cannot be blank.")
    return cleaned_value
