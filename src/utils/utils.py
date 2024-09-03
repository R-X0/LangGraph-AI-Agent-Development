# src/utils.py
import json

def save_data_into_json(file_name, jsons, merge=True):
    data = []
    if merge:
        for json_obj in jsons:
            data += json_obj
    else:
        data = jsons

    with open(f"{file_name}.json", "w") as file:
        json.dump(data, file, indent=4)