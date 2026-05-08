import xml.etree.ElementTree as ET
import os

def shrink_xml(input_path="export.xml", output_path="mini_export.xml"):
    if not os.path.exists(input_path):
        print(f"Error: Could not find '{input_path}'. Make sure it is in this folder.")
        return
        
    print(f"Shrinking {input_path} (this might take a minute for 1GB+ files)...")
    
    with open(output_path, 'wb') as out_f:
        out_f.write(b"<HealthData>\n")
        
        context = ET.iterparse(input_path, events=("end",))
        for event, elem in context:
            if elem.tag == "Workout":
                out_f.write(ET.tostring(elem))
                out_f.write(b"\n")
            elem.clear() # Clear every element from memory immediately
            
        out_f.write(b"</HealthData>\n")
    print(f"Done! Created '{output_path}'. You can now upload this tiny file to the web app.")

if __name__ == "__main__":
    shrink_xml()