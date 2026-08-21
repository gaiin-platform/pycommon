import json
import re
from typing import Any


def is_lzw_compressed_format(data: Any) -> bool:
    """
    Check if the input data could possibly be in LZW compressed format.

    Args:
        data: The data to check

    Returns:
        bool: True if data could be LZW compressed, False otherwise
    """
    # Check if data is a list or tuple
    if not isinstance(data, (list, tuple)):
        return False

    # Empty data is not valid LZW compressed format
    if not data:
        return False

    # All elements should be integers
    if not all(isinstance(item, int) for item in data):
        return False

    # All codes should be non-negative
    if not all(code >= 0 for code in data):
        return False

    # First code should be in initial dictionary range (0-255)
    if data[0] > 255:
        return False

    # Check for reasonable progression - codes should generally increase
    # but we allow some flexibility since codes can be reused
    # Allow for more flexible bounds as LZW can have wider code ranges
    max_expected_code = 256 + len(data) * 50  # More generous estimate
    if any(code > max_expected_code for code in data):
        return False

    return True


def lzw_uncompress(compressed_data):
    if not compressed_data:
        return ""

    dictionary = {i: chr(i) for i in range(256)}  # Build initial dictionary

    decompressed_string = ""
    previous_entry = dictionary.get(compressed_data[0])
    if not previous_entry:
        raise ValueError("Invalid compressed data: First entry not found in dictionary")

    decompressed_string += previous_entry
    next_code = 256

    for code in compressed_data[1:]:
        if code in dictionary:
            current_entry = dictionary[code]
        elif code == next_code:
            current_entry = previous_entry + previous_entry[0]
        else:
            raise ValueError("Invalid compressed data: Entry for code not found")

        decompressed_string += current_entry
        dictionary[next_code] = previous_entry + current_entry[0]
        next_code += 1
        previous_entry = current_entry

    # Postprocessing to convert tagged Unicode characters back to original form
    unicode_pattern = re.compile(r"U\+([0-9a-f]{4})", re.IGNORECASE)
    output = unicode_pattern.sub(
        lambda m: chr(int(m.group(1), 16)), decompressed_string
    )
    try:
        # Ensure the decompressed string is parsed into a dictionary
        return json.loads(output)
    except json.JSONDecodeError:
        raise ValueError("Failed to parse JSON from decompressed string")


def lzw_compress(str_input):
    if not str_input:
        return []

    # Initialize the dictionary with single-character mappings
    dictionary = {chr(i): i for i in range(256)}
    next_code = 256
    compressed_output = []

    # Preprocessing to convert Unicode characters to a unique format
    processed_input = "".join(
        [f"U+{ord(char):04x}" if ord(char) > 255 else char for char in str_input]
    )

    current_pattern = ""
    for character in processed_input:
        new_pattern = current_pattern + character
        if new_pattern in dictionary:
            current_pattern = new_pattern
        else:
            compressed_output.append(dictionary[current_pattern])
            dictionary[new_pattern] = next_code
            next_code += 1
            current_pattern = character

    if current_pattern != "":
        compressed_output.append(dictionary[current_pattern])
    else:  # pragma: no cover
        # This branch is logically unreachable in the LZW algorithm
        # because current_pattern will always contain at least the last character
        pass

    return compressed_output


def safe_compress(data):
    """
    Safely attempt to compress data. If compression fails, return the original data.

    Args:
        data: The data to attempt compression on

    Returns:
        The compressed data if successful, otherwise the original data
    """
    try:
        # If data is already a string, try to compress it
        if isinstance(data, str):
            compressed = lzw_compress(data)
            # Only return compressed if it actually reduces size meaningfully
            if len(compressed) < len(data) * 0.8:  # 20% size reduction threshold
                return compressed
            return data

        # If data is not a string, try to convert to JSON and compress
        elif isinstance(data, (dict, list, int, float, bool)) or data is None:
            json_str = json.dumps(data)
            compressed = lzw_compress(json_str)
            # Only return compressed if it reduces size meaningfully
            if len(compressed) < len(json_str) * 0.8:
                return compressed
            return data

    except Exception:
        # If anything goes wrong, just return the original data
        pass

    return data
