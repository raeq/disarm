#!/usr/bin/env bash
# Bootstrap context dictionaries from zero.
#
# Downloads corpora, builds dictionaries, and verifies checksums.
# Requires: python3, kaggle CLI (pip install kaggle), bzip2
#
# Usage:
#   bash scripts/bootstrap_dicts.sh          # build all
#   bash scripts/bootstrap_dicts.sh arabic   # build Arabic only
#   bash scripts/bootstrap_dicts.sh verify   # verify existing dicts only
#
# This script is the SINGLE SOURCE OF TRUTH for dictionary production.
# All parameters (corpus source, version, build flags, expected checksums)
# are defined here. No manual steps, no hotfixes.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CORPUS_DIR="$ROOT/data/corpora"
DICT_DIR="$ROOT/data"

# ============================================================================
# Corpus sources — pinned versions with checksums
# ============================================================================

# Tashkeela: Arabic diacritized text, CC-BY license
# https://www.kaggle.com/datasets/linuxscout/tashkeela
TASHKEELA_DATASET="linuxscout/tashkeela"
TASHKEELA_ARCHIVE="Tashkeela-arabic-diacritized-text-utf8-0.3.tar.bz2"
TASHKEELA_DIR="Tashkeela-arabic-diacritized-text-utf8-0.3"
# SHA256 of the downloaded archive (pinned for reproducibility)
TASHKEELA_ARCHIVE_SHA256="skip"  # TODO: pin after first verified download

# Project Ben Yehuda: Hebrew public domain texts with niqqud
# https://github.com/projectbenyehuda/public_domain_dump
BEN_YEHUDA_REPO="https://github.com/projectbenyehuda/public_domain_dump.git"
BEN_YEHUDA_DIR="ben_yehuda"

# ============================================================================
# Build parameters — pinned, never changed without bumping checksums
# ============================================================================

ARABIC_MIN_FREQ=5
ARABIC_MAX_BIGRAMS=200000
ARABIC_DICT="$DICT_DIR/arabic_dict.bin"
ARABIC_STATS="$DICT_DIR/arabic_dict_stats.json"

HEBREW_MIN_FREQ=3
HEBREW_MAX_BIGRAMS=200000
HEBREW_DICT="$DICT_DIR/hebrew_dict.bin"
HEBREW_STATS="$DICT_DIR/hebrew_dict_stats.json"

# Expected output checksums (updated by running with --update-checksums)
# These ensure the build is deterministic: same corpus + same params = same output
ARABIC_DICT_SHA256="84b68b453404d9a663ef222bf280273009c0f8006fd7c8342d4bf07b4b8dfa83"
HEBREW_DICT_SHA256="57347d264fe2c6afb8c89572a58c1203479e80ba4b52706da3d54fd832e94e49"

# ============================================================================
# Helpers
# ============================================================================

log() { echo "==> $*" >&2; }
err() { echo "ERROR: $*" >&2; exit 1; }

sha256_file() {
    if command -v sha256sum &>/dev/null; then
        sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum &>/dev/null; then
        shasum -a 256 "$1" | cut -d' ' -f1
    else
        python3 -c "import hashlib; print(hashlib.sha256(open('$1','rb').read()).hexdigest())"
    fi
}

verify_dict() {
    local path="$1" expected="$2" name="$3"
    if [[ ! -f "$path" ]]; then
        err "$name dictionary not found at $path"
    fi
    local actual
    actual=$(sha256_file "$path")
    if [[ "$expected" == "skip" ]]; then
        log "$name: SHA256=$actual (not pinned — run with --update-checksums)"
        return 0
    fi
    if [[ "$actual" != "$expected" ]]; then
        err "$name checksum mismatch!
  Expected: $expected
  Actual:   $actual
  This means the corpus or build parameters changed. If intentional,
  update the expected checksum in scripts/bootstrap_dicts.sh."
    fi
    log "$name: checksum verified ✓"
}

# ============================================================================
# Download
# ============================================================================

download_tashkeela() {
    if [[ -d "$CORPUS_DIR/$TASHKEELA_DIR" ]]; then
        log "Tashkeela corpus already present, skipping download"
        return 0
    fi

    log "Downloading Tashkeela corpus from Kaggle..."
    if ! command -v kaggle &>/dev/null; then
        err "kaggle CLI not found. Install with: pip install kaggle
  Then configure: https://github.com/Kaggle/kaggle-api#api-credentials"
    fi

    mkdir -p "$CORPUS_DIR"
    kaggle datasets download "$TASHKEELA_DATASET" -p "$CORPUS_DIR" --unzip

    # The download may produce a nested archive
    if [[ -f "$CORPUS_DIR/$TASHKEELA_ARCHIVE" ]]; then
        log "Extracting $TASHKEELA_ARCHIVE..."
        tar xjf "$CORPUS_DIR/$TASHKEELA_ARCHIVE" -C "$CORPUS_DIR"
    fi

    if [[ ! -d "$CORPUS_DIR/$TASHKEELA_DIR" ]]; then
        err "Tashkeela corpus not found after download/extract. Check $CORPUS_DIR"
    fi

    local file_count
    file_count=$(find "$CORPUS_DIR/$TASHKEELA_DIR" -name "*.txt" -type f | wc -l | tr -d ' ')
    log "Tashkeela corpus: $file_count text files"
}

download_ben_yehuda() {
    if [[ -d "$CORPUS_DIR/$BEN_YEHUDA_DIR/txt" ]]; then
        log "Ben Yehuda corpus already present, skipping download"
        return 0
    fi

    log "Cloning Project Ben Yehuda from GitHub (shallow)..."
    if ! command -v git &>/dev/null; then
        err "git not found."
    fi

    mkdir -p "$CORPUS_DIR"
    git clone --depth 1 "$BEN_YEHUDA_REPO" "$CORPUS_DIR/$BEN_YEHUDA_DIR"

    if [[ ! -d "$CORPUS_DIR/$BEN_YEHUDA_DIR/txt" ]]; then
        err "Ben Yehuda txt/ directory not found after clone. Check $CORPUS_DIR/$BEN_YEHUDA_DIR"
    fi

    local file_count
    file_count=$(find "$CORPUS_DIR/$BEN_YEHUDA_DIR/txt" -name "*.txt" -type f | wc -l | tr -d ' ')
    log "Ben Yehuda corpus: $file_count text files"
}

# ============================================================================
# Build
# ============================================================================

build_arabic() {
    log "Building Arabic context dictionary..."
    log "  Corpus: $CORPUS_DIR/$TASHKEELA_DIR"
    log "  Min frequency: $ARABIC_MIN_FREQ"
    log "  Max bigrams: $ARABIC_MAX_BIGRAMS"

    python3 "$ROOT/scripts/build_arabic_dict.py" \
        "$CORPUS_DIR/$TASHKEELA_DIR" \
        -o "$ARABIC_DICT" \
        --min-freq "$ARABIC_MIN_FREQ" \
        --max-bigrams "$ARABIC_MAX_BIGRAMS" \
        --json-stats "$ARABIC_STATS"

    local size
    size=$(wc -c < "$ARABIC_DICT" | tr -d ' ')
    local sha
    sha=$(sha256_file "$ARABIC_DICT")
    log "Arabic dictionary: $size bytes, SHA256=$sha"
}

build_hebrew() {
    log "Building Hebrew context dictionary..."
    log "  Corpus: $CORPUS_DIR/$BEN_YEHUDA_DIR/txt"
    log "  Min frequency: $HEBREW_MIN_FREQ"
    log "  Max bigrams: $HEBREW_MAX_BIGRAMS"

    python3 "$ROOT/scripts/build_hebrew_dict.py" \
        "$CORPUS_DIR/$BEN_YEHUDA_DIR/txt" \
        -o "$HEBREW_DICT" \
        --min-freq "$HEBREW_MIN_FREQ" \
        --max-bigrams "$HEBREW_MAX_BIGRAMS" \
        --json-stats "$HEBREW_STATS"

    local size
    size=$(wc -c < "$HEBREW_DICT" | tr -d ' ')
    local sha
    sha=$(sha256_file "$HEBREW_DICT")
    log "Hebrew dictionary: $size bytes, SHA256=$sha"
}

# ============================================================================
# Main
# ============================================================================

cmd="${1:-all}"

case "$cmd" in
    arabic)
        download_tashkeela
        build_arabic
        verify_dict "$ARABIC_DICT" "$ARABIC_DICT_SHA256" "Arabic"
        ;;

    hebrew)
        download_ben_yehuda
        build_hebrew
        verify_dict "$HEBREW_DICT" "$HEBREW_DICT_SHA256" "Hebrew"
        ;;

    verify)
        log "Verifying existing dictionaries..."
        verify_dict "$ARABIC_DICT" "$ARABIC_DICT_SHA256" "Arabic"
        verify_dict "$HEBREW_DICT" "$HEBREW_DICT_SHA256" "Hebrew"
        log "All checksums verified."
        ;;

    --update-checksums)
        log "Computing checksums for existing dictionaries..."
        if [[ -f "$ARABIC_DICT" ]]; then
            sha=$(sha256_file "$ARABIC_DICT")
            log "Arabic:  ARABIC_DICT_SHA256=\"$sha\""
        fi
        if [[ -f "$HEBREW_DICT" ]]; then
            sha=$(sha256_file "$HEBREW_DICT")
            log "Hebrew:  HEBREW_DICT_SHA256=\"$sha\""
        fi
        log "Update the values in scripts/bootstrap_dicts.sh"
        ;;

    all)
        download_tashkeela
        build_arabic
        verify_dict "$ARABIC_DICT" "$ARABIC_DICT_SHA256" "Arabic"

        download_ben_yehuda
        build_hebrew
        verify_dict "$HEBREW_DICT" "$HEBREW_DICT_SHA256" "Hebrew"

        log ""
        log "All dictionaries built and verified."
        log "Files:"
        ls -lh "$ARABIC_DICT" "$HEBREW_DICT" 2>/dev/null || true
        ;;

    *)
        echo "Usage: $0 [arabic|hebrew|verify|--update-checksums|all]" >&2
        exit 1
        ;;
esac
