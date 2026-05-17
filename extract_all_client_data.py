import os
import zipfile
import subprocess
import shutil

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

def decode_with_orion():
    """Крок 2: Декодувати XML через PjOrion"""
    
    folders_to_decode = [
        "extracted_data/common",
        "extracted_data/ussr", 
        "extracted_data/usa",
        "extracted_data/germany",
    ]
    
    orion_path = os.path.join(BASE_DIR, "tools", "orion", "PjOrion.exe")
    
    for folder in folders_to_decode:
        folder_path = os.path.join(BASE_DIR, folder)
        if not os.path.exists(folder_path):
            print(f"\n[2] Skipping {folder} (not found)")
            continue
            
        print(f"\n[2] Decoding {folder}...")
        
        cmd = f'cmd /c start /MIN /wait "" "{orion_path}" "--unpack-folder="{folder_path}" "--exit"'
        subprocess.call(cmd, shell=True)
        
    print("\n[2] Decode complete!")

def main():
    print("=" * 60)
    print("EXTRACT AND DECODE ALL CLIENT DATA")
    print("=" * 60)
    
    extract_all_packages()
    decode_with_orion()
    
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)

if __name__ == "__main__":
    main()