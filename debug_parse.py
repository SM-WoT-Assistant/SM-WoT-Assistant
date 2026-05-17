#!/usr/bin/env python3
import os, xml.etree.ElementTree as ET, json

BASE = r"D:\!WORK\WOT\WOTtraner\WORK\WoT_Assistant_4.0\tmp\tth_work"

print("Base:", BASE)
print("Exists:", os.path.exists(BASE))

# Test parsing one file
test_file = os.path.join(BASE, "ussr_0", "R01_IS.xml")
print("Test file:", test_file)
print("Test file exists:", os.path.exists(test_file))

if os.path.exists(test_file):
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
    print("Content length:", len(content))
    print("First 50 chars:", content[:50])
    
    # Parse
    content = content.replace(' xmlns:xmlref="http://bwt/xmlref"', '')
    try:
        root = ET.fromstring(content)
        print("Root tag:", root.tag)
        crew = root.find("crew")
        print("Crew found:", crew is not None)
    except Exception as e:
        print("Parse error:", e)