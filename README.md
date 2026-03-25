# Verisol — Terminal CLI

Convert e-contracts to Solidity smart contracts entirely from the terminal.
No GUI, no browser — just a shell script.

## Quick Start

```bash
# 1. One-time setup
chmod +x contractforge.sh
./contractforge.sh setup

# 2. Process your e-contract
./contractforge.sh run contract.txt
./contractforge.sh run contract.docx  MyContract
./contractforge.sh run contract.docx  MyContract  ./output
./contractforge.sh run scan.png       ScannedContract

# 3. Or run the built-in demo
./contractforge.sh demo

# 4. Interactive menu (no arguments)
./contractforge.sh
```

## Commands

| Command | Description |
|---------|-------------|
| `./contractforge.sh` | Interactive menu |
| `./contractforge.sh setup` | Install all Python deps + spaCy model + solc |
| `./contractforge.sh run <file>` | Process e-contract |
| `./contractforge.sh run <file> <name>` | With contract name |
| `./contractforge.sh run <file> <name> <outdir>` | With output dir |
| `./contractforge.sh demo` | Run built-in sample |
| `./contractforge.sh check` | Check all dependencies |

## Supported Input Formats

- `.txt` — plain text
- `.docx` — Word document (paragraphs + tables)
- `.png` / `.jpg` / `.jpeg` — scanned image (OCR)
- Folder — multiple .txt/.docx files processed in order

## Output Files (saved to `./contractforge_output/<name>/`)

```
contractforge_output/
└── ServiceAgreement/
    ├── ServiceAgreement.sol          ← generated smart contract (v0.8.16)
    ├── accuracy_results.json         ← KG comparison metrics + refinement log
    ├── econtract_kg.png              ← e-contract knowledge graph image
    ├── smartcontract_kg_initial.png  ← initial SC knowledge graph
    ├── smartcontract_kg_final.png    ← final SC knowledge graph
    └── ServiceAgreement_results.zip  ← everything bundled
```

## Pipeline

```
E-Contract file
    │
    ▼  Algorithm 1 (NLP + spaCy + 11 legal entity types)
E-Contract KG
    │
    ▼  Algorithm 2 (KG → Solidity 0.8.16)
Smart Contract
    │
    ▼  Algorithm 2 (AST → KG)
Smart Contract KG
    │
    ▼  Algorithm 3 (node + edge + type coverage comparison)
Accuracy Score
    │
  ≥100%? ──YES──▶  Save .sol
    │NO
    ▼  Algorithm 4 (Ollama qwen2.5-coder-7b, max 5 iterations)
Refined Smart Contract ──▶ re-compare ──▶ Save .sol
```

## Prerequisites

- Python 3.10+
- Ollama running with qwen2.5-coder-7b: `ollama pull qwen2.5-coder-7b && ollama serve`
- Tesseract OCR (for image input): `sudo apt install tesseract-ocr`

## Project Structure

```
econtract-system/
├── contractforge.sh     ← main shell script (entry point)
├── cli.py               ← Python CLI pipeline
├── backend/
│   ├── core/
│   │   ├── econtract_kg.py      Algorithm 1
│   │   ├── smartcontract_kg.py  Algorithm 2
│   │   └── kg_comparison.py     Algorithm 3 & 4
│   ├── requirements.txt
│   └── run.py
└── README.md
```
