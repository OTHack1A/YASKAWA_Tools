#!/usr/bin/env bash
# Code-sign (and optionally notarize) the YaskawaTools macOS app bundle.
#
# Signing + notarization give the bundle integrity and let Gatekeeper run it
# without the "unidentified developer" block — the macOS equivalent of the
# Windows Authenticode step. Never commit your Developer ID or credentials.
#
# Usage:
#   IDENTITY="Developer ID Application: Your Name (TEAMID)" \
#   ./scripts/sign_macos.sh dist/YaskawaTools.app
#
# Optional notarization (requires a notarytool keychain profile named "YT"):
#   NOTARIZE=1 KEYCHAIN_PROFILE=YT ./scripts/sign_macos.sh dist/YaskawaTools.app
set -euo pipefail

APP_PATH="${1:-dist/YaskawaTools.app}"
IDENTITY="${IDENTITY:?Set IDENTITY to your 'Developer ID Application: ...' identity}"
ENTITLEMENTS="${ENTITLEMENTS:-}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH (build it first)" >&2
  exit 1
fi

echo "Signing $APP_PATH ..."
SIGN_ARGS=(--force --options runtime --timestamp --sign "$IDENTITY")
[[ -n "$ENTITLEMENTS" ]] && SIGN_ARGS+=(--entitlements "$ENTITLEMENTS")

# Sign nested code first, then the bundle, deep.
codesign "${SIGN_ARGS[@]}" --deep "$APP_PATH"

echo "Verifying signature ..."
codesign --verify --deep --strict --verbose=2 "$APP_PATH"
spctl --assess --type execute --verbose=4 "$APP_PATH" || true

if [[ "${NOTARIZE:-0}" == "1" ]]; then
  PROFILE="${KEYCHAIN_PROFILE:?Set KEYCHAIN_PROFILE for notarytool}"
  ZIP="${APP_PATH%.app}.zip"
  echo "Submitting for notarization ..."
  /usr/bin/ditto -c -k --keepParent "$APP_PATH" "$ZIP"
  xcrun notarytool submit "$ZIP" --keychain-profile "$PROFILE" --wait
  xcrun stapler staple "$APP_PATH"
  rm -f "$ZIP"
fi

echo "Done: macOS bundle signed${NOTARIZE:+ and notarized}."
