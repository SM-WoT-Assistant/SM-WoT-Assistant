# WoT Assistant Minimap Detection Testing Guide

## Overview
This document outlines all tests needed to validate the minimap detection implementation.

## Pre-Test Setup

1. **Enable Console Output**: Monitor console for debug messages during testing
2. **Enable Auto Features**: 
   - ⚙ Settings → Enable "🔄 Auto Sync Filters"
   - ⚙ Settings → Enable "⚡ Auto Toggle Battle Mode"
3. **Log Path**: Verify WoT log path is set in ⚙ Settings → WoT Log Path

## Test Case 1: Auto Mode Toggle on Minimap Appearance

### Objective
Verify that battle mode toggles automatically when minimap appears (~2s after battle starts loading)

### Pre-Conditions
- Application in EDITOR mode
- "⚡ Auto Toggle Battle Mode" enabled
- "🔄 Auto Sync Filters" enabled or disabled (doesn't matter for this test)

### Steps
1. Start World of Tanks
2. Enter queue for a battle
3. Click "Play" to enter battle
4. **Observe timing**:
   - T+0s: "Loading space..." appears in console
   - T+2s: "Мініматп з'явилася" appears in console (new message!)
   - T+2-3s: Application switches to BATTLE MODE automatically
   - T+~9s: Battle starts, minimap/countdown countdown timer visible

### Expected Result
✅ Application toggles to NORM (battle) mode ~2 seconds after "Loading space" appears, when minimap becomes visible

### Actual Result
[User fills this in after testing]

### Console Output (Expected)
```
[SYNC] Виявлено карту в логу: map_id=95_lost_city, mode=ctf
[BATTLE] Мініматп з'явилася: map_id=95_lost_city, mode=ctf
[BATTLE] Перехід до боєвого режиму...
```

---

## Test Case 2: Map/Filter Auto-Sync During Battle Load

### Objective
Verify that map selection and filter sync when battle is detected (independent of mode toggle)

### Pre-Conditions
- "🔄 Auto Sync Filters" enabled
- Application in EDITOR mode
- A known map selected in UI (e.g., "Karelia")

### Steps
1. Have a different map in battle queue (e.g., "Lost City")
2. Enter battle, observe console during load
3. Check that map selector updates to match battle map

### Expected Result
✅ Map selector updates to match battle map within 1-2 seconds of "Loading space" event
✅ Filter/mode updates to match battle arena type
✅ Status bar shows: "[AUTO] Виявлено: [map name] ([map_id])"

### Console Output (Expected)
```
[SYNC] Виявлено карту в логу: map_id=95_lost_city, mode=ctf
[SYNC] Синхронізація фільтрів: ctf -> Standard
[SYNC] Available maps: ['Karelia', 'Sacred Valley', 'Lost City', ...]
[SYNC] map_id='95_lost_city', ui_mode='Standard', target_name='Lost City'
[AUTO] Виявлено: Lost City (95_lost_city)
```

---

## Test Case 3: Window State Restoration on Toggle

### Objective
Verify that window size, position, and transparency preserve when switching modes

### Pre-Conditions
- Application running
- In EDITOR mode

### Steps
1. **Set EDITOR window state**:
   - Position: Move window to specific location (e.g., X:100, Y:100)
   - Size: Resize to (e.g., 800×930)
   - Transparency: Set alpha to 0.7 using Settings

2. **Toggle to BATTLE mode**:
   - Press Button or Hotkey to enter battle
   - Observe window size/position change (should be different for battle mode)

3. **Verify EDITOR state restoration**:
   - Toggle back to EDITOR mode
   - Check if window returns to exact position from Step 1
   - Check size and transparency match

### Expected Result
✅ Window returns to exact position (X:100, Y:100) within +/- 5 pixels
✅ Window returns to exact size (800×930) within +/- 5 pixels
✅ Transparency (alpha) returns to 0.7

### Measurement Method
```python
# Add this to main.py temporarily to see exact values
def log_window_state(self):
    x, y = self.root.winfo_x(), self.root.winfo_y()
    w, h = self.w, self.h
    alpha = self.alpha
    print(f"[WINDOW] X={x}, Y={y}, W={w}, H={h}, Alpha={alpha}")
```

---

## Test Case 4: Return to Editor with Battle Map After Battle Ends

### Objective
Verify that after battle ends and returning to hangar, app switches back to EDITOR mode with correct map selected

### Pre-Conditions
- "⚡ Auto Toggle Battle Mode" enabled
- Known starting map (e.g., "Karelia")
- Battle map is different (e.g., "Lost City")

### Steps
1. Start in EDITOR mode with "Karelia" selected
2. Enter a battle with "Lost City"
3. Application switches to BATTLE mode (test 1)
4. Play the battle
5. Return to hangar (battle ends)
6. **Observe**:
   - Console shows "[BATTLE] Поверненння в ангар"
   - Application switches back to EDITOR mode
   - Map selector shows "Lost City"
   - Window returns to EDITOR size/position
   - Filter/mode set to battle arena type

### Expected Result
✅ Application switches back to EDITOR mode within 1-2s of hangar detection
✅ Map selector shows "Lost City"
✅ Window position/size match EDITOR saved settings
✅ Status bar shows map selection details

### Console Output (Expected)
```
[SYNC] Loading space: spaces/hangar_v4
[BATTLE] Поверненння в ангар. Остання карта: 95_lost_city
[BATTLE] Переключаємось до режиму РЕДАГУВАННЯ з картою: 95_lost_city
[BATTLE] Синхронізація карти після повернення: 95_lost_city
```

---

## Test Case 5: Disabling Auto Features

### Objective
Verify that disabling auto features stops automatic toggles

### Test 5a: Disable Auto Mode Toggle
**Steps**:
1. Disable "⚡ Auto Toggle Battle Mode" in Settings
2. Enter a battle
3. Observe console: Should see "[BATTLE] Авто перехід до режиму бою вимкнено"
4. Application should NOT switch to BATTLE mode
5. Status bar should indicate auto-toggle is disabled

**Expected Result**:
✅ Application remains in EDITOR mode
✅ No automatic mode switch occurs

### Test 5b: Disable Auto Map Sync
**Steps**:
1. Disable "🔄 Auto Sync Filters" in Settings
2. Enter a battle with different map
3. Observe console: Should see "[SYNC] Авто-синхронізація вимкнена"
4. Map selector should NOT update to battle map

**Expected Result**:
✅ Map selector stays at previously selected map
✅ No automatic filter sync occurs

---

## Test Case 6: Error Handling

### Test 6a: Invalid Log Path
**Steps**:
1. Set WoT log path to non-existent location
2. Load application
3. Try to enter a battle

**Expected Result**:
✅ Console shows "[LOG] ПОМИЛКА: Лог не знайдено"
✅ Features gracefully fail without crashing

### Test 6b: Unicode/Special Characters in Map Names
**Steps**:
1. Enter battle on a map with special characters in name
2. Monitor console for map name translation

**Expected Result**:
✅ Map names correctly translated
✅ Filter sync works despite special characters

---

## Regression Testing

### Test R1: Normal Mode Toggle (F hotkey)
**Steps**:
1. Press F hotkey or mode toggle button in EDITOR mode
2. Application should switch to BATTLE mode (manual toggle)
3. Window should resize to BATTLE dimensions
4. Press F again, should return to EDITOR mode

**Expected Result**:
✅ Manual toggle still works correctly
✅ Window state restoration works
✅ No interference from auto-toggle feature

### Test R2: Settings Persistence
**Steps**:
1. Set unique window position/size/transparency for EDITOR
2. Set unique position/size/transparency for BATTLE
3. Toggle between modes several times
4. Close application
5. Reopen application
6. Verify both modes restore to saved settings

**Expected Result**:
✅ All settings persist across application restarts
✅ No mixing of EDITOR/BATTLE settings

---

## Performance Testing

### Test P1: Log File Monitoring Overhead
**Objective**: Verify log watching doesn't cause excessive CPU usage

**Steps**:
1. Open Task Manager → Performance tab
2. Monitor python.exe CPU usage during battle
3. Expected CPU usage: <5% when idle, <15% while monitoring logs

**Expected Result**:
✅ CPU usage remains low
✅ Log monitoring is efficient

---

## Debug Logging

To enable detailed debug output, add these lines to main.py after LogWatcher initialization:

```python
# Debug: Print all minimap detection events
def debug_log_events(self):
    print(f"[DEBUG] Mode: {self.mode}, Auto-Battle: {self.auto_battle_var.get()}, Auto-Sync: {self.auto_sync_var.get()}")
    print(f"[DEBUG] Last Battle: {self.last_battle_map}/{self.last_battle_mode}")
    print(f"[DEBUG] Window: X={self.root.winfo_x()}, Y={self.root.winfo_y()}, W={self.w}, H={self.h}")
```

Call this in console: `app.debug_log_events()` to see current state.

---

## Known Issues & Workarounds

### Issue 1: Mode Toggle Not Triggering
**Symptom**: Minimap appears but mode doesn't toggle
**Diagnosis**:
- Check console for "[BATTLE] Авто перехід до режиму бою вимкнено"
- Verify auto_battle_var is enabled in settings.json
**Workaround**: Manually press F hotkey to toggle

### Issue 2: Window Position Lost
**Symptom**: After toggle, window appears at different position
**Diagnosis**:
- Check settings.json has "edit_x", "edit_y", "norm_x", "norm_y" entries
- Verify these values are valid (not negative or >5000)
**Workaround**: Manually position window and save settings

### Issue 3: Map Not Syncing
**Symptom**: Battle starts but map selector doesn't update
**Diagnosis**:
- Check console: "[SYNC] map_id='...', target_name='...'"
- Verify target_name is in available maps list
**Workaround**: Manually select correct map

---

## Test Results Summary

| Test Case | Status | Notes | Date |
|-----------|--------|-------|------|
| 1 - Auto Mode Toggle | ☐ PASS ☐ FAIL | | |
| 2 - Filter Sync | ☐ PASS ☐ FAIL | | |
| 3 - Window State | ☐ PASS ☐ FAIL | | |
| 4 - Return to Editor | ☐ PASS ☐ FAIL | | |
| 5a - Disable Toggle | ☐ PASS ☐ FAIL | | |
| 5b - Disable Sync | ☐ PASS ☐ FAIL | | |
| 6a - Invalid Log | ☐ PASS ☐ FAIL | | |
| 6b - Unicode Maps | ☐ PASS ☐ FAIL | | |
| R1 - Manual Toggle | ☐ PASS ☐ FAIL | | |
| R2 - Settings | ☐ PASS ☐ FAIL | | |
| P1 - CPU Usage | ☐ PASS ☐ FAIL | | |

---

## Sign-Off

- Tester Name: _____________________
- Date: _____________________  
- All Critical Tests Passed: ☐ YES ☐ NO
- Ready for Production: ☐ YES ☐ NO
