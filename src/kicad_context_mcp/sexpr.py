"""Minimal S-expression reader for KiCad .kicad_pcb / .kicad_sch files.

We only need it for the PCB layer/stackup summary; connectivity comes from the
exported netlist XML. So this stays small: tokenize, build nested lists.
"""

import re

_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()]+')


def parse(text: str):
    """Parse one or more top-level S-expressions into nested lists.

    Atoms are returned as strings (quotes stripped, escapes resolved).
    A list's first element is its tag, e.g. ['layers', ...].
    """
    tokens = _TOKEN.findall(text)
    pos = 0

    def read():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok == "(":
            lst = []
            while tokens[pos] != ")":
                lst.append(read())
            pos += 1  # consume ')'
            return lst
        if tok.startswith('"'):
            return tok[1:-1].encode().decode("unicode_escape")
        return tok

    forms = []
    while pos < len(tokens):
        forms.append(read())
    return forms[0] if len(forms) == 1 else forms


def find_all(node, tag):
    """Yield every sub-list whose first element == tag (recursive)."""
    if isinstance(node, list):
        if node and node[0] == tag:
            yield node
        for child in node:
            yield from find_all(child, tag)


def first(node, tag):
    """First sub-list with the given tag, or None."""
    return next(find_all(node, tag), None)


if __name__ == "__main__":
    t = '(kicad_pcb (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) (footprint "x"))'
    doc = parse(t)
    assert doc[0] == "kicad_pcb"
    layers = first(doc, "layers")
    assert len(layers) == 3  # 'layers' + 2 layer defs
    assert layers[1][1] == "F.Cu"  # quoted atom unescaped
    assert len(list(find_all(doc, "footprint"))) == 1
    print("sexpr ok")
