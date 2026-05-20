#!/usr/bin/env python3
"""
Deterministic synthetic corruption scaffold for RelationReady.
- Local-only, no API calls.
- Operates on input JSONL where each row is a dict with at least:
  - case_id, candidate_id, candidate_formula (string or null)
- Produces an output JSONL with added fields: corruption_type, corrupted_formula, corruption_seed

Usage (library):
  from scripts.synthetic_corruption_scaffold import generate_corruptions_from_rows
  rows = load_jsonl(...)
  out_rows = generate_corruptions_from_rows(rows, seed=0, n_per_row=3)

Usage (CLI):
  python scripts/synthetic_corruption_scaffold.py --in input.jsonl --out out.jsonl --seed 0 --n 2

Note: Transforms are deterministic given seed. They operate on AST nodes; only syntactically valid transformations are kept.
"""
from __future__ import annotations

import argparse
import ast
import json
import random
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _collect_names_and_consts(expr_ast: ast.AST) -> Tuple[List[str], List[ast.Constant]]:
    names = []
    consts = []
    for node in ast.walk(expr_ast):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            consts.append(node)
    return list(dict.fromkeys(names)), consts


def _swap_two_names(expr_ast: ast.AST, rnd: random.Random) -> Optional[ast.AST]:
    names, _ = _collect_names_and_consts(expr_ast)
    if len(names) < 2:
        return None
    a, b = rnd.sample(names, 2)

    class Swap(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:
            if node.id == a:
                return ast.copy_location(ast.Name(id=b, ctx=node.ctx), node)
            if node.id == b:
                return ast.copy_location(ast.Name(id=a, ctx=node.ctx), node)
            return node

    return Swap().visit(expr_ast)


def _scale_numbers(expr_ast: ast.AST, rnd: random.Random) -> Optional[ast.AST]:
    _, consts = _collect_names_and_consts(expr_ast)
    if not consts:
        return None
    factor = rnd.choice([12, 1 / 12, 100, 1 / 100, 10, 1 / 10])

    class Scale(ast.NodeTransformer):
        def visit_Constant(self, node: ast.Constant) -> ast.AST:
            if isinstance(node.value, (int, float)):
                return ast.copy_location(ast.Constant(value=node.value * factor), node)
            return node

    return Scale().visit(expr_ast)


def _perturb_numbers(expr_ast: ast.AST, rnd: random.Random) -> Optional[ast.AST]:
    _, consts = _collect_names_and_consts(expr_ast)
    if not consts:
        return None
    def choice_pert(x):
        ops = [lambda v: v + 1, lambda v: v - 1, lambda v: v * 0.9, lambda v: v * 1.1]
        return rnd.choice(ops)(x)

    class Perturb(ast.NodeTransformer):
        def visit_Constant(self, node: ast.Constant) -> ast.AST:
            if isinstance(node.value, (int, float)):
                return ast.copy_location(ast.Constant(value=choice_pert(node.value)), node)
            return node

    return Perturb().visit(expr_ast)


def _delete_last_binop_term(expr_ast: ast.AST) -> Optional[ast.AST]:
    # If expression is a BinOp chain, remove the rightmost operand by returning the left side.
    if isinstance(expr_ast, ast.BinOp):
        return expr_ast.left
    return None


def _remove_final_op(expr_ast: ast.AST) -> Optional[ast.AST]:
    # If expression is BinOp, drop the highest-precedence operator by returning left side.
    return _delete_last_binop_term(expr_ast)


CORRUPTORS = [
    ("var_rebind_swap", _swap_two_names),
    ("unit_scale_inversion", _scale_numbers),
    ("arithmetic_perturbation", _perturb_numbers),
    ("relation_deletion", lambda astree, rnd: _delete_last_binop_term(astree)),
    ("final_after_process_omit", lambda astree, rnd: _remove_final_op(astree)),
]


def _try_parse(expr: str) -> Optional[ast.AST]:
    try:
        tree = ast.parse(expr, mode="eval")
        return tree.body
    except SyntaxError:
        return None


def _ast_to_source(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def generate_corruptions_from_row(row: Dict[str, Any], seed: int = 0, n_per_row: int = 2) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    formula = row.get("candidate_formula")
    if not formula:
        return out
    base_ast = _try_parse(formula)
    if base_ast is None:
        return out
    rnd = random.Random(seed)

    # deterministic sequence: iterate corruptors in a RNG-determined order
    for i in range(n_per_row):
        rnd_local = random.Random(seed + i)
        order = list(range(len(CORRUPTORS)))
        rnd_local.shuffle(order)
        for idx in order:
            name, fn = CORRUPTORS[idx]
            new_ast = fn(deepcopy(base_ast), rnd_local)
            if new_ast is None:
                continue
            src = _ast_to_source(new_ast)
            if not src:
                continue
            # Keep only syntactically valid corrupted formulas
            if _try_parse(src) is None:
                continue
            out_row = deepcopy(row)
            out_row["corruption_type"] = name
            out_row["corrupted_formula"] = src
            out_row["corruption_seed"] = seed + i
            out_row["corruption_index"] = i
            out.append(out_row)
            break  # one corruption per i
    return out


def generate_corruptions_from_rows(rows: Iterable[Dict[str, Any]], seed: int = 0, n_per_row: int = 2) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        out.extend(generate_corruptions_from_row(row, seed=seed + idx, n_per_row=n_per_row))
    return out


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n", type=int, default=2, help="Number of corruptions per row")
    args = ap.parse_args(argv)

    rows = load_jsonl(args.in_path)
    out_rows = generate_corruptions_from_rows(rows, seed=args.seed, n_per_row=args.n)
    write_jsonl(args.out_path, out_rows)


if __name__ == "__main__":
    main()
