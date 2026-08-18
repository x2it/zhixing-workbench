import os
import hashlib
import zipfile

def create_msix():
    staging_dir = r"C:\Users\Administrator\Documents\trae_projects\zhixing_workbench\source\msix_staging"
    output_file = r"C:\Users\Administrator\Documents\trae_projects\zhixing_workbench\source\dist\ZhixingWorkbench_v3.1.0.msix"
    
    # Remove existing output
    if os.path.exists(output_file):
        os.remove(output_file)
    
    # Collect all files and compute their hashes for block map
    files_data = []
    
    for root, dirs, files in os.walk(staging_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, staging_dir).replace("\\", "/")
            
            with open(full_path, "rb") as f:
                content = f.read()
                sha256_hash = hashlib.sha256(content).hexdigest()
            
            files_data.append({
                "path": rel_path,
                "hash": sha256_hash,
                "size": len(content),
                "content": content
            })
    
    # Remove old empty AppxBlockMap.xml if exists
    files_data = [f for f in files_data if f['path'] != 'AppxBlockMap.xml']
    
    # Create AppxBlockMap.xml
    block_map_items = []
    for f in files_data:
        block_map_items.append(f"""  <File Name="{f['path']}" Size="{f['size']}" BlockMapOffset="0">
    <Block Size="{f['size']}" Hash="{f['hash']}" />
  </File>""")
    
    block_map_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<BlockMap xmlns="http://schemas.microsoft.com/appx/2010/blockmap" HashMethod="http://www.w3.org/2001/04/xmlenc#sha256">
{chr(10).join(block_map_items)}
</BlockMap>"""
    
    # Add block map to files
    block_map_content = block_map_xml.encode("utf-8")
    block_map_hash = hashlib.sha256(block_map_content).hexdigest()
    files_data.append({
        "path": "AppxBlockMap.xml",
        "hash": block_map_hash,
        "size": len(block_map_content),
        "content": block_map_content
    })
    
    # Create ZIP (MSIX)
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files_data:
            zf.writestr(f['path'], f['content'], zipfile.ZIP_DEFLATED)
    
    print(f"MSIX created: {output_file}")
    print(f"Size: {os.path.getsize(output_file):,} bytes ({os.path.getsize(output_file)/1024/1024:.2f} MB)")
    print(f"Files packed: {len(files_data)}")

if __name__ == "__main__":
    create_msix()
