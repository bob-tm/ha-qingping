import struct
from . import parsekeys
from datetime import datetime

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

def datetime_human(timestamp):
    return datetime.fromtimestamp(timestamp)

def parse_sensor_timestamp(sensor_data):
    return sensor_data[0] | (sensor_data[1] << 8) | (sensor_data[2] << 16) | (sensor_data[3] << 24)

def parse_real_sensor_data(real_sensor_data):
    result={}

    combined_data = real_sensor_data[0] | (real_sensor_data[1] << 8) | (real_sensor_data[2] << 16)
    temperature = ((combined_data >> 12) - 500.0) / 10.0
    result["temperature"] = temperature
    humidity = (combined_data & 0x000fff) / 10
    result["humidity"] = humidity
    co2_ppm = real_sensor_data[3] | (real_sensor_data[4] << 8)
    result["co2_ppm"] = co2_ppm
    battery = real_sensor_data[5]
    result["battery"] = battery

    return result


def parse_sensor_data(sensor_data):
    result = {}
    result["timestamp"]       = parse_sensor_timestamp(sensor_data)
    result["timestamp_human"] = datetime_human(result["timestamp"])
    result["sensor"]          = parse_real_sensor_data(sensor_data[4:])

    return result


def parse_history_sensor_data(sensor_data):
    result = {}
    result["timestamp"]       = parse_sensor_timestamp(sensor_data)
    result["timestamp_human"] = datetime_human(result["timestamp"])
    result["update_interval"] = sensor_data[4] | (sensor_data[5] << 8)
    # 6 bytes header and 6 bytes each record
    c = (len(sensor_data)-6) // 6
    for x in range(c):
        result[x] = parse_real_sensor_data(sensor_data[6 + x*6:])

    return result

def parse_v2_data(value, exportable_data):
    device = value[4]
    ts = parse_sensor_timestamp(value[0:4])
    exportable_data["timestamp"] = ts
    exportable_data["timestamp_human"] = datetime_human(ts)
    if device == 0x04: # QING_SENSOR_DATA_FORMAT_TEMP_RH_CO2
        temp, humidity, co2_ppm = struct.unpack("<hHH", value[5:11])
        exportable_data["temperature"] = temp / 10.0
        exportable_data["humidity"] = humidity / 10.0
        exportable_data["co2_ppm"] = co2_ppm
    else:
        exportable_data["unk_key_85"] = value.hex()
        #print(f"Unknown v2 data format: {device}, data: {value.hex()}")
    return exportable_data

def parse_data(input_bytes: bytearray):
    data = parsekeys.parse_keys(input_bytes)
    exportable_data = {}
    exportable_data["_header"] = str(input_bytes)[2:5]
    for key, value in data.items():
        # Historical Data
        if key == "0x03":
            hex_string = " ".join(format(byte, '02x') for byte in value)
            exportable_data["historicalData_hex"] = hex_string
            exportable_data["historicalData"] = parse_history_sensor_data(value)

        # Interval of Data Upload
        elif key == "0x04":
            exportable_data["uploadDataInterval"] = value[0] * 60

        # Interval of Data Recording
        elif key == "0x05":
            exportable_data["recordDataInterval"] = value[0]

        # Undocumented Value
        elif key == "0x06":
            exportable_data["undocumentedValue"] = str(value)

        # Unit of Temperature
        elif key == "0x19":
            exportable_data["temperatureUnit"] = "celsius" if value[0] == 0 else "fahrenheit"

        # Firmware Version
        elif key == "0x11":
            exportable_data["firmware_version"] = ''.join(chr(byte) for byte in value)

        # Real-time networking event -> Contains Sensor Data
        elif key == "0x14":
            sensor_data = parse_sensor_data(value)
            for k, v in sensor_data.items():
                exportable_data[k] = v

        # Disconnect the Device -> When this is true the device will enter into low-power mode
        elif key == "0x1d":
            exportable_data["isGoingIntoLowPowerMode"] = bool(data[key][0])

        # Hardware Version
        elif key == "0x22":
            exportable_data["hardwareVersion"] = ''.join(chr(b) for b in data[key])

        # USB Plugin Status
        elif key == "0x2c":
            exportable_data["isPluggedInToPower"] = bool(data[key][0])

        # Wireless Module Firmware Version
        elif key == "0x34":
            exportable_data["wirelessModuleFirmwareVersion"] = ''.join(chr(b) for b in data[key])

        # MCU Firmware Version
        elif key == "0x35":
            exportable_data["mcuFirmwareVersion"] = ''.join(chr(b) for b in data[key])

        # ProductID
        elif key == "0x38":
            if data[key]:
                exportable_data["productId"] = ''.join(chr(b) for b in data[key])

        # Interval of CO2 Measurement
        elif key == "0x3b":
            exportable_data["co2MeasurementInterval"] = data[key][0] * 60

        # Not Needed value
        #elif key == "0x3c":
        #    pass

        # Auto Off Time
        elif key == "0x3d":
            exportable_data["autoOffTime"] = data[key][0] * 60

        # Time setting
        elif key == "0x3e":
            exportable_data["timeMode"] = "24h" if data[key][0] == 0 else "12h"

        # CO2 ASC Switch
        elif key == "0x40":
            exportable_data["co2ASC"] = bool(data[key][0])

        # Offset CO2 by percentage
        elif key == "0x3f":
            co2_offset_percentage = data[key][0] | (data[key][1] << 8)
            exportable_data["co2OffsetPercentage"] = co2_offset_percentage / 10

        # CO2 Calibration Status
        elif key == "0x4a":
            exportable_data["co2IsBeingCalibrated"] = bool(data[key][0])

        # Offset CO2 by value
        elif key == "0x45":
            co2_offset = data[key][0] | (data[key][1] << 8)
            exportable_data["co2Offset"] = co2_offset

        # Offset Temperature by Value
        elif key == "0x46":
            temperature_offset = data[key][0] | (data[key][1] << 8)
            exportable_data["temperatureOffset"] = temperature_offset / 10

        # Offset Temperature by Percentage
        elif key == "0x47":
            temperature_offset_percentage = data[key][0] | (data[key][1] << 8)
            exportable_data["temperatureOffsetPercentage"] = temperature_offset_percentage / 10

        # Offset Humidity by value
        elif key == "0x48":
            humidity_offset = data[key][0] | (data[key][1] << 8)
            exportable_data["humidityOffset"] = humidity_offset / 10

        # Offset Humidity by percent
        elif key == "0x49":
            humidity_offset_percentage = data[key][0] | (data[key][1] << 8)
            exportable_data["humidityOffsetPercentage"] = humidity_offset_percentage / 10

        # V2 data.
        elif key == "0x85":
            exportable_data = parse_v2_data(value, exportable_data)

        else:
            #exportable_data[f"unk_key_{int(key, 16):02x}"] = f"{value.hex()} : {str(value)}"
            exportable_data[f"unk_key_{int(key, 16):02x}"] = value.hex()
            #print(f"Unknown data key: {int(key, 16):02x}")

    return exportable_data