; SM WoT Assistant NSIS Installer
; Build: makensis installer.nsi

!define PRODUCT_NAME "SM WoT Assistant"
!define PRODUCT_VERSION "1.0.45"
!define PRODUCT_PUBLISHER "SM WoT Assistant"
!define PRODUCT_WEB_SITE ""
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\SM WoT Assistant v${PRODUCT_VERSION}.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"

SetCompressor lzma

Icon "dist\SM WoT Assistant\_internal\icon.ico"
UninstallIcon "dist\SM WoT Assistant\_internal\icon.ico"

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
    Delete "$INSTDIR\SM WoT Assistant v*.exe"
    File /r "dist\SM WoT Assistant\*.*"

    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    Delete "$DESKTOP\SM WoT Assistant.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\SM WoT Assistant.lnk"
    Delete "$DESKTOP\SM WoT Assistant v*.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\SM WoT Assistant v*.lnk"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\SM WoT Assistant v${PRODUCT_VERSION}.lnk" "$INSTDIR\SM WoT Assistant Launcher.exe" "" "$INSTDIR\_internal\icon.ico"
    CreateShortCut "$DESKTOP\SM WoT Assistant v${PRODUCT_VERSION}.lnk" "$INSTDIR\SM WoT Assistant Launcher.exe" "" "$INSTDIR\_internal\icon.ico"

    WriteRegStr HKCU "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\SM WoT Assistant v${PRODUCT_VERSION}.exe"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME} ${PRODUCT_VERSION}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\SM WoT Assistant v${PRODUCT_VERSION}.exe"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoRepair" 1

    WriteUninstaller "$INSTDIR\uninst.exe"

    System::Call 'shell32.dll::SHChangeNotify(i 0x08000000, i 0, i 0, i 0)'
SectionEnd

Section "Uninstall"
    MessageBox MB_YESNO|MB_ICONQUESTION \
        "Delete tactical schemes, settings, and cached data?$\n$\nClick YES to remove all user data. Click NO to keep your schemes for future reinstall." \
        IDNO skip_data
    RMDir /r "$APPDATA\SM WoT Assistant"
    skip_data:
    RMDir /r "$INSTDIR"
    Delete "$DESKTOP\SM WoT Assistant.lnk"
    Delete "$DESKTOP\SM WoT Assistant v${PRODUCT_VERSION}.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\SM WoT Assistant.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\SM WoT Assistant v${PRODUCT_VERSION}.lnk"
    RMDir /r "$SMPROGRAMS\${PRODUCT_NAME}"
    DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"
    DeleteRegKey HKCU "${PRODUCT_DIR_REGKEY}"
SectionEnd
