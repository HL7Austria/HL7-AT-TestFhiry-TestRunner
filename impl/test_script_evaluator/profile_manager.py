import json
from pathlib import Path

class ProfileManager:
    def __init__(self):
        self.profiles = []  # List for (name, id)

    def add_profile(self, profile_data, filename):
        """
        Adds a profile to the list if it has a valid StructureDefinition
        """
        if profile_data.get("resourceType") == "StructureDefinition":
            profile_id = profile_data.get("id")
            self.profiles.append((filename, profile_id))

    def make_profile_list(self, folder_path):
        """
        Iterates through all *.json files in the specified folder
        and saves valid StructureDefinition profiles
        """
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Folder not found: {folder_path}")

        for file in path.iterdir():
            if file.is_file():  # Only actual files, not folders
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)  # The file will only be accepted as JSON if its content is correct
                    self.add_profile(data, file.stem)
                except Exception as e:
                    print(f"Errors in processing of {file}: {e}")

    def get_profiles(self):
        """Returns the list of saved profiles."""
        return self.profiles
