def parse_keys(bytes):
    payload_length = bytes[3] | (bytes[4] << 8)
    data = {}
    # Start at 5 because the first 5 bytes are the protocol header and payload length
    i = 5
    while i < payload_length - 1:
        key = bytes[i]
        length = bytes[i + 1] | (bytes[i + 2] << 8)
        value = bytes[i + 3:i + 3 + length]
        data[f"0x{key:02x}"] = value
        i += 3 + length
    return data