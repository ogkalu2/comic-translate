#!/bin/sh
# Create a folder (named dmg) to prepare our DMG in (if it doesn't already exist).
mkdir -p dist/dmg
# Empty the dmg folder.
rm -r dist/dmg/*
# Copy the app bundle to the dmg folder.
cp -r "dist/Comic Translate.app" dist/dmg
# If the DMG already exists, delete it.
test -f "dist/Comic Translate.dmg" && rm "dist/Comic Translate.dmg"
create-dmg \
  --volname "Comic Translate" \
  --volicon "resources/icons/icon.icns" \
  --icon-size 100 \
  --icon "Comic Translate.app" 175 120 \
  --hide-extension "Comic Translate.app" \
  --app-drop-link 425 120 \
  "dist/Comic Translate.dmg" \
  "dist/dmg/"