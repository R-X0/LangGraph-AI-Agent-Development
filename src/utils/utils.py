import json

def save_data_into_json(file_name, jsons, merge=True):
    if merge:
        data = []
        for json_obj in jsons:
            if isinstance(json_obj, list):
                data.extend(json_obj)
            elif isinstance(json_obj, dict):
                data.append(json_obj)
    else:
        data = jsons

    with open(f"{file_name}.json", "w") as file:
        json.dump(data, file, indent=4)