from __future__ import annotations
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data.canonicalize import Canonicalizer
parser = argparse.ArgumentParser()
parser.add_argument("--chunk-size", type=int, default=250000)
args = parser.parse_args()
Canonicalizer().materialize_all(chunk_size=args.chunk_size)
