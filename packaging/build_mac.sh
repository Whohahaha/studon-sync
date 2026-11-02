#!/bin/zsh
# Builds dist/StudOn Sync.app and signs it with a STABLE identity, so macOS Keychain
# "Always Allow" survives rebuilds (ad-hoc signatures change with every build).
#
# Identity: $SIGN_IDENTITY if set (e.g. "Developer ID Application: Name (TEAMID)" from the
# login keychain), otherwise a self-signed "StudOn Sync Local Signing" certificate that this
# script creates once in a separate keychain under ~/Library/Application Support/StudOn Sync/signing/.
# That keychain is NOT added to the search list and needs no admin rights; the self-signed
# certificate is only good for this computer (other users still see the "unidentified developer" dialog).
set -euo pipefail
SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"
ROOT="${SCRIPT_DIR:h}"
APP="$ROOT/dist/StudOn Sync.app"
BUNDLE_ID="de.fau.studon-sync"
LOCAL_NAME="StudOn Sync Local Signing"
SIGN_DIR="$HOME/Library/Application Support/StudOn Sync/signing"
KC="$SIGN_DIR/signing.keychain-db"

ensure_local_identity() {
  mkdir -p "$SIGN_DIR"
  chmod 700 "$SIGN_DIR"
  [[ -f "$SIGN_DIR/kc-pass" ]] || { openssl rand -hex 24 > "$SIGN_DIR/kc-pass"; chmod 600 "$SIGN_DIR/kc-pass"; }
  local pass; pass=$(cat "$SIGN_DIR/kc-pass")
  if [[ ! -f "$KC" ]]; then
    local tmp; tmp=$(mktemp -d)
    cat > "$tmp/cert.cnf" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = $LOCAL_NAME
[ext]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
EOF
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout "$tmp/key.pem" -out "$tmp/cert.pem" -config "$tmp/cert.cnf" 2>/dev/null
    openssl pkcs12 -export -legacy -inkey "$tmp/key.pem" -in "$tmp/cert.pem" -out "$tmp/id.p12" -passout "pass:$pass" -name "$LOCAL_NAME" 2>/dev/null
    security create-keychain -p "$pass" "$KC"
    security set-keychain-settings "$KC"   # no auto-lock
    security unlock-keychain -p "$pass" "$KC"
    security import "$tmp/id.p12" -k "$KC" -P "$pass" -T /usr/bin/codesign >/dev/null
    security set-key-partition-list -S apple-tool:,apple: -s -k "$pass" "$KC" >/dev/null
    rm -rf "$tmp"
  fi
  security unlock-keychain -p "$pass" "$KC"
}

../.venv/bin/pyinstaller --noconfirm --distpath ../dist --workpath ../build studon-sync.spec

if [[ -n "${SIGN_IDENTITY:-}" ]]; then
  codesign --force --deep --timestamp --options runtime --identifier "$BUNDLE_ID" -s "$SIGN_IDENTITY" "$APP"
else
  ensure_local_identity
  codesign --force --deep --keychain "$KC" --identifier "$BUNDLE_ID" -s "$LOCAL_NAME" "$APP"
fi
codesign --verify --deep "$APP"
codesign -d -r- "$APP" 2>&1 | grep designated
du -sh "$APP"
