#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ContractForge — Terminal Shell Script
#  Usage:
#    ./contractforge.sh                      (interactive menu)
#    ./contractforge.sh run contract.txt
#    ./contractforge.sh run contract.docx  MyContract
#    ./contractforge.sh run contract.docx  MyContract  ./output
#    ./contractforge.sh demo
#    ./contractforge.sh check
#    ./contractforge.sh setup
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV="$BACKEND_DIR/venv"
PYTHON="$VENV/bin/python"
CLI="$SCRIPT_DIR/cli.py"

# ── Colours ────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'
C='\033[0;36m'; B='\033[1m';    D='\033[2m'; N='\033[0m'

banner() {
  echo -e "${C}"
  echo "  ╔══════════════════════════════════════════════════════╗"
  echo "  ║  ${B}ContractForge${N}${C} — E-Contract → Smart Contract           ║"
  echo "  ║  ${D}NLP · Knowledge Graph · Solidity 0.8.16 · qwen2.5:7b${N}${C}  ║"
  echo "  ╚══════════════════════════════════════════════════════╝"
  echo -e "${N}"
}

info()    { echo -e "  ${C}→${N}  $*"; }
success() { echo -e "  ${G}✓${N}  $*"; }
warn()    { echo -e "  ${Y}⚠${N}  $*"; }
error()   { echo -e "  ${R}✗${N}  $*"; }
die()     { error "$*"; exit 1; }

# ── Setup: create venv + install deps ─────────────────────────
cmd_setup() {
  banner
  echo -e "${B}  Setup${N}\n"

  [ -d "$BACKEND_DIR" ] || die "backend/ directory not found. Run from econtract-system/ root."

  info "Creating Python virtual environment..."
  python3 -m venv "$VENV" || die "Failed to create venv. Is python3-venv installed?"
  success "venv created at $VENV"

  info "Upgrading pip..."
  "$PYTHON" -m pip install --upgrade pip --quiet

  if [ -f "$BACKEND_DIR/requirements.txt" ]; then
    info "Installing Python dependencies from requirements.txt..."
    "$PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" --quiet && \
      success "Dependencies installed" || warn "Some packages failed — check requirements.txt"
  else
    info "No requirements.txt found — installing core packages..."
    "$PYTHON" -m pip install spacy networkx matplotlib python-docx requests solcx --quiet && \
      success "Core packages installed" || warn "Some packages failed"
    "$PYTHON" -m spacy download en_core_web_sm --quiet 2>/dev/null && \
      success "spaCy model en_core_web_sm installed" || warn "spaCy model install skipped"
  fi

  info "Installing Solidity compiler 0.8.16..."
  "$PYTHON" -c "import solcx; solcx.install_solc('0.8.16', show_progress=False)" 2>/dev/null && \
    success "solc 0.8.16 ready" || warn "solc install skipped (will retry at runtime)"

  echo ""
  success "Setup complete! Run:  ./contractforge.sh demo"
  echo ""
}

# ── Ensure setup has been run ──────────────────────────────────
require_venv() {
  if [ ! -f "$PYTHON" ]; then
    warn "Virtual environment not found. Running setup first...\n"
    cmd_setup
  fi
}

# ── check command ──────────────────────────────────────────────
cmd_check() {
  require_venv
  "$PYTHON" "$CLI" check
}



# ── run command ────────────────────────────────────────────────
cmd_run() {
  require_venv

  local file="${1:-}"
  local name="${2:-}"
  local out="${3:-}"

  # Validate file
  if [ -z "$file" ]; then
    error "No file specified."
    echo -e "  Usage: ${C}./contractforge.sh run <file> [name] [output_dir]${N}"
    echo -e "  Example: ${D}./contractforge.sh run contract.txt ServiceAgreement ./results${N}"
    exit 1
  fi

  if [ ! -e "$file" ]; then
    die "File not found: $file"
  fi

  # Build python args
  local py_args="--file \"$file\""
  [ -n "$name" ] && py_args="$py_args --name \"$name\""
  [ -n "$out"  ] && py_args="$py_args --output \"$out\""

  eval "$PYTHON \"$CLI\" run $py_args"
}

# ── Multi-page document processing ─────────────────────────────
cmd_run_multi() {
  require_venv

  local file="${1:-}"
  local name="${2:-}"
  local out="${3:-}"

  # Validate file
  if [ -z "$file" ]; then
    error "No file specified."
    echo -e "  Usage: ${C}./contractforge.sh run-multi <file.docx> [name] [output_dir]${N}"
    echo -e "  Example: ${D}./contractforge.sh run-multi contracts.docx MyContracts${N}"
    exit 1
  fi

  if [ ! -e "$file" ]; then
    die "File not found: $file"
  fi

  # Check if file is DOCX
  if [[ ! "$file" =~ \.docx$ ]]; then
    warn "run-multi works best with .docx files (multi-page Word documents)"
  fi

  # Build python args
  local py_args="--file \"$file\""
  [ -n "$name" ] && py_args="$py_args --name \"$name\""
  [ -n "$out"  ] && py_args="$py_args --output \"$out\""

  eval "$PYTHON \"$CLI\" run-multi $py_args"
}

# ── interactive menu ───────────────────────────────────────────
interactive_menu() {
  banner
  echo -e "  ${B}What would you like to do?${N}\n"
  echo -e "    ${C}1${N}  Process an e-contract file"
  echo -e "    ${C}2${N}  Run demo (built-in sample contract)"
  echo -e "    ${C}3${N}  Check dependencies"
  echo -e "    ${C}4${N}  Run setup / install dependencies"
  echo -e "    ${C}5${N}  Exit\n"
  read -rp "  Enter choice [1-5]: " choice

  case "$choice" in
    1)
      echo ""
      read -rp "  $(echo -e ${C})E-contract file path$(echo -e ${N}) (.txt/.docx/.png/.jpg or folder): " file
      read -rp "  $(echo -e ${C})Contract name$(echo -e ${N}) (press Enter for auto): " name
      read -rp "  $(echo -e ${C})Output directory$(echo -e ${N}) (press Enter for default): " outdir
      echo ""
      cmd_run "$file" "$name" "$outdir"
      ;;
    2) echo ""; cmd_demo ;;
    3) echo ""; cmd_check ;;
    4) echo ""; cmd_setup ;;
    5) echo ""; exit 0 ;;
    *) error "Invalid choice"; interactive_menu ;;
  esac
}

# ── Entry point ────────────────────────────────────────────────
case "${1:-}" in
  run)       shift; cmd_run       "$@" ;;
  run-multi) shift; cmd_run_multi "$@" ;;
  demo)      shift; cmd_demo      "$@" ;;
  check)     shift; cmd_check           ;;
  setup)     shift; cmd_setup           ;;
  "")              interactive_menu     ;;
  *)
    banner
    echo -e "  ${B}Usage:${N}"
    echo -e "    ${C}./contractforge.sh${N}                                interactive menu"
    echo -e "    ${C}./contractforge.sh setup${N}                          install dependencies"
    echo -e "    ${C}./contractforge.sh run <file>${N}                      process single e-contract"
    echo -e "    ${C}./contractforge.sh run <file> <name>${N}               with contract name"
    echo -e "    ${C}./contractforge.sh run <file> <name> <outdir>${N}     with output dir"
    echo -e "    ${C}./contractforge.sh run-multi <file.docx>${N}           process multi-page DOCX (one contract per page)"
    echo -e "    ${C}./contractforge.sh run-multi <file> <name>${N}         with base name for pages"
    echo -e "    ${C}./contractforge.sh demo${N}                            built-in sample"
    echo -e "    ${C}./contractforge.sh check${N}                           dependency check"
    echo ""
    echo -e "  ${B}Supported input formats:${N}"
    echo -e "    ${D}Single-page: .txt  .docx  .png  .jpg  .jpeg  folder/${N}"
    echo -e "    ${D}Multi-page:  .docx (detects and splits automatically)${N}"
    echo ""
    ;;
esac