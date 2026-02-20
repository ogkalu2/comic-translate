# Qt Translation Compilation Workflow

This workflow automatically compiles Qt translation files (`.ts` → `.qm`) when translation source files are updated.

## How It Works

### Triggers
The workflow runs when:
1. **Push events** - When `.ts` files in `resources/translations/` are modified
2. **Pull requests** - When PRs modify `.ts` files
3. **Manual trigger** - Via GitHub Actions UI (workflow_dispatch)

### What It Does

1. **Detects Changes**: Monitors `resources/translations/*.ts` files
2. **Compiles Translations**: Uses `pyside6-lrelease` to compile all `.ts` files to `.qm` format
3. **Auto-commits** (on push): Commits compiled `.qm` files back to the repository
4. **Uploads Artifacts** (on PR): Provides compiled files as downloadable artifacts for review

### Workflow Steps

```yaml
1. Checkout repository
2. Set up Python 3.12
3. Install PySide6 (provides pyside6-lrelease tool)
4. Compile all .ts files to .qm format
5. Check if compiled files changed
6. [Push only] Commit and push compiled files
7. [PR only] Upload compiled files as artifacts
```

### Output Location

Compiled files are saved to: `resources/translations/compiled/*.qm`

### Commit Message

Auto-commits use: `chore: Auto-compile Qt translation files [skip ci]`

The `[skip ci]` tag prevents infinite loops by skipping CI on the auto-commit.

## Usage

### For Contributors

When you update translation files:

1. Edit `.ts` files in `resources/translations/`
2. Commit and push your changes
3. The workflow automatically compiles and commits `.qm` files
4. Pull the auto-committed changes: `git pull`

### For Pull Requests

1. Submit PR with `.ts` file changes
2. Workflow compiles translations and uploads as artifacts
3. Reviewers can download and test compiled translations
4. After merge, the workflow will auto-commit on the main branch

### Manual Compilation (Local)

If you prefer to compile locally:

```bash
# Compile a specific translation file
pyside6-lrelease resources/translations/ct_zh-HK.ts -qm resources/translations/compiled/ct_zh-HK.qm

# Compile all translation files
for ts_file in resources/translations/*.ts; do
  filename=$(basename "$ts_file" .ts)
  pyside6-lrelease "$ts_file" -qm "resources/translations/compiled/${filename}.qm"
done
```

## Supported Languages

Current translation files:
- `ct_ko.ts` - Korean (한국어)
- `ct_fr.ts` - French (Français)
- `ct_zh-CN.ts` - Simplified Chinese (简体中文)
- `ct_zh-HK.ts` - Hong Kong Chinese (繁體中文-香港)
- `ct_zh-TW.ts` - Taiwan Chinese (繁體中文-台灣)
- `ct_ru.ts` - Russian (русский)
- `ct_de.ts` - German (Deutsch)
- `ct_es.ts` - Spanish (Español)
- `ct_it.ts` - Italian (Italiano)
- `ct_tr.ts` - Turkish (Türkçe)

## Troubleshooting

### Workflow Fails to Compile

**Issue**: `pyside6-lrelease: command not found`

**Solution**: Ensure PySide6 is properly installed in the workflow. Check the "Install PySide6" step.

### Compiled Files Not Committed

**Issue**: Changes detected but not committed

**Solution**:
- Check if the workflow has write permissions
- Verify `GITHUB_TOKEN` has necessary permissions
- Check if branch protection rules prevent auto-commits

### Infinite Loop of Commits

**Issue**: Workflow keeps triggering itself

**Solution**: The `[skip ci]` tag in the commit message prevents this. Ensure it's present in the commit message.

## Permissions Required

The workflow needs:
- `contents: write` - To commit compiled files
- `pull-requests: read` - To detect PR changes

These are provided by the default `GITHUB_TOKEN`.

## Notes

- Compiled `.qm` files are binary and should be committed to the repository
- The workflow uses `fetch-depth: 0` to ensure full git history for proper diffing
- Artifacts are retained for 7 days on pull requests
- The workflow is optimized to only run when translation files actually change
