def omit_none(value):
    """
    When django serializes a form, it inserts None values for empty fields. This
    is contrary to what Pydantic expects, which is for the field to not be set at all
    if the default is desired. None is an explicit value.
    This function recursively omits None values from dictionaries and lists."""
    if isinstance(value, dict):
        return {
            key: omit_none(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [omit_none(item) for item in value]
    return value
