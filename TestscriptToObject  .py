import GetTestscript
from fhir.resources.testscript import TestScript

import GetTestscript
from fhir.resources.testscript import TestScript
import requests


def create_objects(testscripts_raw):
    """
    Parses raw JSON strings into TestScript objects.
    Returns two dictionaries: valid objects and failed parses.
    """
    testscripts_objects = {}
    failed_scripts = {}

    for filename, content in testscripts_raw.items():
        try:
            testscripts_objects[filename] = TestScript.model_validate_json(content)
        except Exception as e:
            failed_scripts[filename] = str(e)

    if failed_scripts:
        print("\nSkipped TestScripts due to validation errors:")
        for filename, error in failed_scripts.items():
            print(f"  {filename}: {error}")
    else:
        print("\nAll TestScripts were successfully loaded.")

    return testscripts_objects, failed_scripts
def inspect_testscript(ts_object, filename):
    """
    Inspects and prints the structure of a given TestScript object.
    Shows all test blocks and their actions (operation/assert).
    """
    print(f"\n📄 Inspecting: {filename}")

    if not ts_object.test:
        print("  ⚠ No tests defined.")
        return

    for i, test in enumerate(ts_object.test):
        print(f"   Test {i + 1}: {test.name} — {test.description}")

        for j, action in enumerate(test.action):
            print(f"    🔸 Action {j + 1}:")
            if action.operation:
                op = action.operation
                print(f"      Operation: {op.type.code} {op.resource}")
            elif action.assert_fhir:
                a = action.assert_fhir
                print(f"      Assert: {a.description}")
            else:
                print("      ⚠ Unknown action type")


# Main program
if __name__ == "__main__":
    testscripts_raw = GetTestscript.load_testscripts()
    testscripts_objects, failed_scripts = create_objects(testscripts_raw)

    for filename, ts_object in testscripts_objects.items():
        inspect_testscript(ts_object, filename)

