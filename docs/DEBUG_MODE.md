# DEBUG MODE for File Processing

## Overview
DEBUG_MODE is an environment variable that limits file processing during user initialization to save API costs during development and testing.

## How It Works

When `DEBUG_MODE=true` is set in your `.env` file:

1. **File Fetching**: The system still traverses your entire Google Drive structure
2. **File Filtering**: After fetching, it filters to only **non-folder files**
3. **Sorting**: Files are sorted by `modified_time` (most recent first)
4. **Limiting**: Only the **latest 50 files** are processed
5. **Processing**: These 50 files are downloaded, processed, and embedded

This significantly reduces:
- Google Drive API calls (downloading only 50 files)
- OpenAI API costs (creating embeddings for only 50 files)
- Processing time

## Usage

### Enable DEBUG_MODE

Add to your `.env` file:
```bash
DEBUG_MODE=true
```

### Disable DEBUG_MODE (Production)

Either remove the line from `.env` or set:
```bash
DEBUG_MODE=false
```

## What Gets Limited

- ✅ **Files**: Limited to 50 most recent files
- ❌ **Emails**: NOT limited (all emails from last 90 days are processed)
- ❌ **Calendar Events**: NOT limited (all future events are processed)

## Console Output

When DEBUG_MODE is enabled, you'll see console output:
```
[DEBUG MODE ENABLED] Will process only latest 50 files
[DEBUG MODE] Limited to 50 most recent files
```

## Example Comparison

### Without DEBUG_MODE
```
User has 1,000 files in Drive
→ Downloads all 1,000 files
→ Processes all 1,000 files
→ Creates embeddings for all 1,000 files
→ Higher API costs
```

### With DEBUG_MODE
```
User has 1,000 files in Drive
→ Fetches metadata for all 1,000 files
→ Filters to 50 most recently modified files
→ Downloads only those 50 files
→ Processes only those 50 files
→ Creates embeddings for only 50 files
→ Lower API costs
```

## Best Practices

1. **Development**: Always use `DEBUG_MODE=true` during development
2. **Testing**: Use `DEBUG_MODE=true` when testing with test accounts
3. **Production**: Set `DEBUG_MODE=false` or remove the variable for production users
4. **New Users**: For new user testing, enable DEBUG_MODE to avoid processing thousands of files

## Technical Details

The limitation is implemented in:
- `backend/retrieval_service/google_api_utils.py`: `fetch_drive_all_files(debug_mode=False)`
- `backend/app.py`: Reads `DEBUG_MODE` from environment and passes to initialization

The files are sorted by `modified_time` in descending order (newest first), ensuring you're testing with the most recent files in the user's Drive.
