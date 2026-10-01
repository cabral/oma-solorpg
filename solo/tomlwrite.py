"""Writing TOML: the standard library reads it and does not write it.

`dump_toml` turns nested dicts and lists into the file a pack holds, in the order the dict
has, with `Inline` tables on one line (time = { shift = 1 }) and arrays of tables as [[...]].
"""

import re

from .packs import toml_string


class Inline(dict):
    """A table written on one line: time = { shift = 1 }."""


def dump_toml(data, comments=()):
    lines = [f"# {line}".rstrip() for line in comments]
    _emit(lines, (), data)
    return "\n".join(lines).strip("\n") + "\n"


def _emit(lines, path, data):
    plain = [(k, v) for k, v in data.items() if not _is_table(v) and not _is_array(v)]
    tables = [(k, v) for k, v in data.items() if _is_table(v)]
    arrays = [(k, v) for k, v in data.items() if _is_array(v)]
    if path and (plain or not (tables or arrays)):
        lines += ["", f"[{'.'.join(map(_key, path))}]"]
    for k, v in plain:
        if isinstance(v, list) and len(v) > 1 and all(isinstance(item, Inline) for item in v):
            lines += [f"{_key(k)} = [", *[f"  {_value(item)}," for item in v], "]"]  # a table's rows, one to a line
        else:
            lines.append(f"{_key(k)} = {_value(v)}")
    for key, value in tables:
        _emit(lines, (*path, key), value)
    for key, items in arrays:
        for item in items:
            lines += ["", f"[[{'.'.join(map(_key, (*path, key)))}]]"]
            lines += [f"{_key(k)} = {_value(v)}" for k, v in item.items()]


def _is_table(value):
    return isinstance(value, dict) and not isinstance(value, Inline)


def _is_array(value):
    return isinstance(value, list) and bool(value) and all(_is_table(v) for v in value)


def _key(key):
    return key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else toml_string(key)


def _value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, dict):
        return "{ " + ", ".join(f"{_key(k)} = {_value(v)}" for k, v in value.items()) + " }" if value else "{}"
    elif isinstance(value, list):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    else:
        return toml_string(value)
