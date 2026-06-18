from impl.test_script_evaluator.result_tracker import ResultTracker
from bs4 import BeautifulSoup
def construct_body(tracker: ResultTracker) -> str:
    """
     Construct the body recursivly?? or what exactly do I need to writ where?

     <?xml>
     <testsuites time="soundso">
        <testsuite name="TestScript" classname="TestScript" time="">
            <testcase name="soundso" classname="phase" assertions="" time="">
                <system-out> INFO </system-out>
                <skipped message="jkn"/> --> wenn ein test als skip geflagged wird
                <failure message="errormessage" type="Errortype">
                    stack trace?? vlt wenns mehrere failure gibt, sollte es eig. nd bei direkten failure oder?? vlt. bei stoptestonfail
                </failure>
                <error message="wäre glb ich TesScriptError" type=""/>
    "testscript_results": [
    {
      "name": "HL7\u00ae AT Core TestScript - Patient Update",
      "url": "http://hl7.at/fhir/HL7ATCoreProfiles/4.0.1/TestScript/testscript-patient-update-at-core",
      "outcome": "pass",
      "timestamp": "2026-06-17T11:10:35.103368",
      "outcomes": [
        {
          "class_type": "Setup",
          "name": "Setup",
          "time_spent": 0.20143604278564453,
          "assertion_count": 0,
          "result": "pass",
          "message": "Setup successful",
          "error_type": null
        },
        {
    """
    result = f"""<?xml version="1.0" encoding="UTF-8"?>
    <testsuites time="{tracker.current_test_run.timestamp}">"""
    for testscrpt in tracker.current_test_run.testscript_results:
        result += f"""<testsuit name="{testscrpt.name}" classname="TestScript" time="{testscrpt.timestamp}">\n"""
        for phase in testscrpt.outcomes:
            result += f"""<testcase name="{phase.name}" classname="{phase.class_type}" assertions="{phase.assertion_count}" time="{phase.time_spent}">\n"""
            if phase.result == "fail":
                if phase.error_type == "TestScriptError":
                    result += f"""<error message="{phase.message}" type="{phase.error_type}"/>\n"""
                else:
                    result += f"""<failure message="{phase.message}" type="{phase.error_type}"/>\n"""
            elif phase.result == "skip":
                result += f"""<skipped message="{phase.message}"/>\n"""
            else:
                result += f"""<system-out>{phase.message}</system-out>\n"""
            result+= "</testcase>\n"
        result +="</testsuit> \n"
    result+="</testsuites>"

    bs = BeautifulSoup(result, "xml")
    print(bs.prettify())

def save_xml(body: str, filepath: str):
    """saves an xml-file with body"""

    if not filepath.endswith(".xml"):
         filepath += ".xml"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
               f.write(body)
    except Exception as e:
        raise
