
def construct_bdy(tracker: any) -> str:
     """
     Construct the body recursivly?? or what exactly do I need to writ where?

     <?xml>
     <testsuites time="soundso">
        <testsuite name="TestScript" classname="TestScript" time=""/>
            <testcase name="soundso" classname="phase" assertions="" time=""/>
     
     """
     result = """<?xml version="1.0" encoding="UTF-8"?>"""
     print()

def save_xml(body: str, filepath: str):
    """saves an xml-file with body"""

    if not filepath.endswith(".xml"):
         filepath += ".xml"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
               f.write(body)
    except Exception as e:
        raise
