#!/usr/bin/env python3
"""Verify a translated file differs from the original ONLY in comments and
docstrings (comment-only edit check).

Usage: python scripts/verify_comment_only.py <orig> <new>
Exit 0 = safe (code + all non-docstring strings identical); 1 = NOT safe.
"""
from __future__ import annotations

import ast
import sys


def strip_docstrings(tree):
    """Return a copy of the AST with docstring expression statements removed
    (Module / FunctionDef / AsyncFunctionDef / ClassDef bodies)."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:]
    return tree


def main():
    orig, new = sys.argv[1], sys.argv[2]
    a = strip_docstrings(ast.parse(open(orig, encoding="utf-8").read()))
    b = strip_docstrings(ast.parse(open(new, encoding="utf-8").read()))
    da, db = ast.dump(a), ast.dump(b)
    if da != db:
        # locate first mismatch line for debugging
        la = ast.unparse(a).splitlines()
        lb = ast.unparse(b).splitlines()
        for i, (x, y) in enumerate(zip(la, lb)):
            if x != y:
                print(f"FIRST CODE DIFF at unparse line {i}:\n  orig: {x}\n"
                      f"  new : {y}")
                break
        print("FAIL: non-docstring code differs")
        return 1
    ast.parse(open(new, encoding="utf-8").read())  # syntax re-check
    print(f"OK: {new} differs from {orig} only in comments/docstrings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
