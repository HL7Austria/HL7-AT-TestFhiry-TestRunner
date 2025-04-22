import json
import os


def read_config_file(configuration_key):
    base_dir = os.path.dirname(__file__)
    config_path = os.path.join(base_dir, 'config.json')
    # Load config file
    try:
        with open(config_path, "r") as file:
            config = json.load(file)
            return config[configuration_key][0]
    except FileNotFoundError:
        print("Error: 'config.json' file not found.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse 'config.json': {e}")
        exit(1)

