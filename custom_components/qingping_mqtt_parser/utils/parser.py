from . import parsekeys

DataKey = [
    "historicalData",
    "uploadDataInterval",
    "recordDataInterval",
    "undocumentedValue",
    "temperatureUnit",
    "firmware_version",
    "timestamp",
    "temperature",
    "humidity",
    "co2_ppm",
    "battery",
    "isGoingIntoLowPowerMode",
    "hardwareVersion",
    "isPluggedInToPower",
    "wirelessModuleFirmwareVersion",
    "mcuFirmwareVersion",
    "productId",
    "co2MeasurementInterval",
    "autoOffTime",
    "timeMode",
    "co2ASC",
    "co2OffsetPercentage",
    "co2IsBeingCalibrated",
    "co2Offset",
    "temperatureOffset",
    "temperatureOffsetPercentage",
    "humidityOffset",
    "humidityOffsetPercentage"
]

def parse_data(input_bytes: bytearray):
    data = parsekeys.parse_keys(input_bytes)
    exportable_data = {}
    exportable_data["_header"] = str(input_bytes)[2:5]
    for key, value in data.items():
        if key == "0x03":
            hex_string = " ".join(format(byte, '02x') for byte in value)
            exportable_data["historicalData"] = hex_string
        elif key == "0x04":
            exportable_data["uploadDataInterval"] = value[0] * 60
        elif key == "0x05":
            exportable_data["recordDataInterval"] = value[0]
        elif key == "0x06":
            exportable_data["undocumentedValue"] = str(value)
        elif key == "0x19":
            exportable_data["temperatureUnit"] = "celsius" if value[0] == 0 else "fahrenheit"
        elif key == "0x11":
            exportable_data["firmware_version"] = ''.join(chr(byte) for byte in value)
        elif key == "0x14":
            sensor_data = value
            timestamp = sensor_data[0] | (sensor_data[1] << 8) | (sensor_data[2] << 16) | (sensor_data[3] << 24)
            exportable_data["timestamp"] = timestamp
            real_sensor_data = sensor_data[4:]
            combined_data = real_sensor_data[0] | (real_sensor_data[1] << 8) | (real_sensor_data[2] << 16)
            temperature = ((combined_data >> 12) - 500.0) / 10.0
            exportable_data["temperature"] = temperature
            humidity = (combined_data & 0x000fff) / 10
            exportable_data["humidity"] = humidity
            co2_ppm = real_sensor_data[3] | (real_sensor_data[4] << 8)
            exportable_data["co2_ppm"] = co2_ppm
            battery = real_sensor_data[5]
            exportable_data["battery"] = battery
        if key == "0x1d":
            exportable_data["isGoingIntoLowPowerMode"] = bool(data[key][0])
        elif key == "0x22":
            exportable_data["hardwareVersion"] = ''.join(chr(b) for b in data[key])
        elif key == "0x2c":
            exportable_data["isPluggedInToPower"] = bool(data[key][0])
        elif key == "0x34":
            exportable_data["wirelessModuleFirmwareVersion"] = ''.join(chr(b) for b in data[key])
        elif key == "0x35":
            exportable_data["mcuFirmwareVersion"] = ''.join(chr(b) for b in data[key])
        elif key == "0x38":
            if data[key]:
                exportable_data["productId"] = ''.join(chr(b) for b in data[key])
        elif key == "0x3b":
            exportable_data["co2MeasurementInterval"] = data[key][0] * 60
        elif key == "0x3c":
            pass
        elif key == "0x3d":
            exportable_data["autoOffTime"] = data[key][0] * 60
        elif key == "0x3e":
            exportable_data["timeMode"] = "24h" if data[key][0] == 0 else "12h"
        elif key == "0x40":
            exportable_data["co2ASC"] = bool(data[key][0])
        elif key == "0x3f":
            co2_offset_percentage = data[key][0] | (data[key][1] << 8)
            exportable_data["co2OffsetPercentage"] = co2_offset_percentage / 10
        elif key == "0x4a":
            exportable_data["co2IsBeingCalibrated"] = bool(data[key][0])
        elif key == "0x45":
            co2_offset = data[key][0] | (data[key][1] << 8)
            exportable_data["co2Offset"] = co2_offset
        elif key == "0x46":
            temperature_offset = data[key][0] | (data[key][1] << 8)
            exportable_data["temperatureOffset"] = temperature_offset / 10
        elif key == "0x47":
            temperature_offset_percentage = data[key][0] | (data[key][1] << 8)
            exportable_data["temperatureOffsetPercentage"] = temperature_offset_percentage / 10
        elif key == "0x48":
            humidity_offset = data[key][0] | (data[key][1] << 8)
            exportable_data["humidityOffset"] = humidity_offset / 10
        elif key == "0x49":
            humidity_offset_percentage = data[key][0] | (data[key][1] << 8)
            exportable_data["humidityOffsetPercentage"] = humidity_offset_percentage / 10

        else:
            #exportable_data[f"unk_key_{int(key, 16):02x}"] = f"{value.hex()} : {str(value)}"
            exportable_data[f"unk_key_{int(key, 16):02x}"] = value.hex()
            #print(f"Unknown data key: {int(key, 16):02x}")

    return exportable_data
