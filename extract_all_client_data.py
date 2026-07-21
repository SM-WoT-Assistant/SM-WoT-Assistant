import os
import zipfile
import subprocess
import shutil
from pathlib import Path
from decode_xml import WotXmlParser

BASE_DIR = os.getcwd()
WOT_PATH = r"C:\Games\World_of_Tanks_EU"

def extract_all_packages():
    """Крок 1: Розпакувати всі потрібні .pkg файли"""
    
    packages_needed = {
        "scripts.pkg": "extracted_data",
        "gui-part1.pkg": "extracted_gui",
    }
    
    pkg_dir = os.path.join(WOT_PATH, "res", "packages")
    
    for pkg_name, output_subdir in packages_needed.items():
        pkg_path = os.path.join(pkg_dir, pkg_name)
        output_dir = os.path.join(BASE_DIR, output_subdir)
        
        print(f"\n[1] Extracting {pkg_name}...")
        
        if not os.path.exists(pkg_path):
            print(f"  ERROR: {pkg_path} not found!")
            continue
            
        if os.path.exists(output_dir):
            print(f"  Already extracted: {output_dir}")
            continue
            
        os.makedirs(output_dir, exist_ok=True)
        
        with zipfile.ZipFile(pkg_path, 'r') as z:
            z.extractall(output_dir)
            print(f"  Extracted to: {output_dir}")

def decode_with_python():
    """Крок 2: Декодувати XML через Python"""
    
    folders_to_decode = [
        "extracted_data/common",
        "extracted_data/ussr", 
        "extracted_data/usa",
        "extracted_data/germany",
    ]
    
    decoder = WotXmlParser()
    total_decoded = 0
    
    for folder in folders_to_decode:
        folder_path = os.path.join(BASE_DIR, folder)
        if not os.path.exists(folder_path):
            print(f"\n[2] Skipping {folder} (not found)")
            continue
            
        print(f"\n[2] Decoding {folder}...")
        
        xml_files = list(Path(folder_path).rglob("*.xml"))
        decoded = 0
        
        for xml_file in xml_files:
            try:
                if decoder.decode_file(str(xml_file), str(xml_file)):
                    decoded += 1
            except Exception as e:
                pass
        
        print(f"  Decoded: {decoded} files")
        total_decoded += decoded
    
    print(f"\n[2] Total decoded: {total_decoded} files")

def main():
    print("=" * 60)
    print("EXTRACT AND DECODE ALL CLIENT DATA")
    print("=" * 60)
    
    extract_all_packages()
    decode_with_python()
    
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)

if __name__ == "__main__":
    main()