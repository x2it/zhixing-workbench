import os

manifest = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         IgnorableNamespaces="uap">
  <Identity Name="DAD0384E.595150F4F75BE"
            Publisher="CN=856DEE8D-D8FF-4895-A3B1-4155E3824692"
            Version="3.1.0.0" />

  <Properties>
    <DisplayName>知行工作台</DisplayName>
    <PublisherDisplayName>知行工作室</PublisherDisplayName>
    <Logo>AppFiles/_internal/app_icon.png</Logo>
  </Properties>

  <Resources>
    <Resource Language="zh-cn" />
  </Resources>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>

  <Applications>
    <Application Id="App"
                  Executable="AppFiles/ZhixingWorkbench.exe"
                  EntryPoint="Windows.FullTrustApp">
      <uap:VisualElements DisplayName="知行工作台"
                          Description="桌面效率工具"
                          BackgroundColor="transparent"
                          Square150x150Logo="AppFiles/_internal/app_icon.png"
                          Square44x44Logo="AppFiles/_internal/app_icon.png" />
    </Application>
  </Applications>
</Package>
"""

path = r"C:\Users\Administrator\Documents\trae_projects\zhixing_workbench\source\msix_staging\AppxManifest.xml"
with open(path, "w", encoding="utf-8") as f:
    f.write(manifest)
print(f"Manifest updated: {os.path.getsize(path)} bytes")
print(f"New Publisher: CN=856DEE8D-D8FF-4895-A3B1-4155E3824692")
print(f"New Name: DAD0384E.595150F4F75BE")
