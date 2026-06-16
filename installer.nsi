; SM WoT Assistant NSIS Installer
; Build: makensis installer.nsi

!define PRODUCT_NAME "SM WoT Assistant"
!define PRODUCT_VERSION "1.0.4"
!define PRODUCT_PUBLISHER "SM WoT Assistant"
!define PRODUCT_WEB_SITE ""
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\SM WoT Assistant.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

SetCompressor lzma

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "dist\SM_WoT_Assistant_Setup_v${PRODUCT_VERSION}.exe"
InstallDir "$LOCALAPPDATA\SM WoT Assistant"
InstallDirRegKey HKCU "${PRODUCT_DIR_REGKEY}" ""
RequestExecutionLevel user

Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "dist\SM WoT Assistant\*.*"

    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\SM WoT Assistant.exe"
    CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\SM WoT Assistant.exe"

    WriteRegStr HKCU "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\SM WoT Assistant.exe"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoRepair" 1

    WriteUninstaller "$INSTDIR\uninst.exe"

    System::Call 'shell32.dll::SHChangeNotify(i 0x08000000, i 0, i 0, i 0)'
SectionEnd

Section "Uninstall"
    RMDir /r "$INSTDIR"
    Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
    DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKCU "${PRODUCT_DIR_REGKEY}"
SectionEnd
