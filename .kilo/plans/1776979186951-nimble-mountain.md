# Wot Assistant Plan - nimble-mountain

## Goal
Fix the search functionality in the SETUP section (ai_stats view) to allow immediate text input without blocking while filtering processes.

## Current Issue
When typing in the search box, letters appear delayed because the `refresh_ai_view()` method is called synchronously on every keystroke via `trace_add("write")` on the search variable. This blocks the UI thread during filtering, causing unresponsiveness in text entry.

## Proposed Solution
Implement debounced search filtering:
- Add a timer to delay the actual filtering/refresh operation
- Cancel previous timer on new keystroke to prevent unnecessary work
- Allow immediate text input while scheduling background filtering

## Implementation Steps

### 1. Modify StatsAI.__init__()
- Add `self._search_timer = None` to initialize the debounce timer

### 2. Update _on_search_changed()
- Cancel any existing timer before scheduling a new one
- Schedule `self._perform_search()` with a 300ms delay using `self.root.after()`

### 3. Add _perform_search() method
- Move the filtering logic from `_on_search_changed()` into this new method
- This method will be called after the debounce delay

### 4. Test the changes
- Ensure text appears immediately when typing
- Verify filtering works correctly after typing pauses
- Check performance with large tank database

## Benefits
- Immediate UI responsiveness during typing
- Reduced unnecessary filtering calls during rapid typing
- Better user experience in the SETUP section search

## Files to Modify
- `stats_ai.py`: Add debounce timer and update search change handler</content>
<parameter name="filePath">D:\!WORK\WOT\WOTtraner\WORK\SETUP S MAPS WoT Assistant_1.00\.kilo\plans\1776979186951-nimble-mountain.md