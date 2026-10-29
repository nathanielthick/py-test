#!/usr/bin/env python3
"""
wirelist_to_instructions.py

Converts a comma-separated wire list into a WIRE instruction block, using a
CUSTOM_LABELS file to translate connector/pin labels into machine points.

Wire list (one wire per line, either end may be a label or a machine point):
    _j1-52,P1-1
    j3-36,P2-1

Label file (machine point, label):
    CUSTOM_LABELS
    BEGIN
         J1-52, _J1-52
         J2-17, P1-1
    END

Resolution rules for each wire end (case-insensitive):
    1. If it matches a machine point in the label file (e.g. j3-36 -> J3-36),
       it is used as-is.
    2. Otherwise, if it matches a label (e.g. _j1-52 or P1-1), it is translated
       to that label's machine point.
    3. Otherwise, if it looks like a machine point (J<n>-<pin>, no underscore),
       it is used as-is even though the label file doesn't list it.
    4. Otherwise it is reported as unresolved and the wire is skipped; all
       other wires are still written.

Usage:
    python wirelist_to_instructions.py wires.csv labels.txt
    python wirelist_to_instructions.py wires.csv labels.txt -o out.txt -r 5.0
"""

import argparse
import re
import sys

MACHINE_POINT = re.compile(r"^J\d+-[A-Z0-9]+$")


def parse_labels(path):
    """Return (label -> machine point, set of machine points), keys uppercased."""
    label_to_point = {}
    points = set()
    in_section = False
    in_block = False

    with open(path, encoding="utf-8-sig") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            upper = line.upper()

            if upper == "CUSTOM_LABELS":
                in_section = True
                continue
            if in_section and upper == "BEGIN":
                in_block = True
                continue
            if in_block and upper == "END":
                break
            if not in_block:
                continue

            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                print(f"Warning: label file line {lineno} not understood: {line}",
                      file=sys.stderr)
                continue

            point, label = parts[0].upper(), parts[1].upper()
            if label in label_to_point and label_to_point[label] != point:
                print(f"Warning: label {label} assigned to both "
                      f"{label_to_point[label]} and {point}; using {point}",
                      file=sys.stderr)
            label_to_point[label] = point
            points.add(point)

    if not in_block:
        sys.exit(f"Error: no CUSTOM_LABELS / BEGIN block found in {path}")
    return label_to_point, points


def resolve(name, label_to_point, points):
    """Return the machine point for a wire end, or None if unknown."""
    key = name.strip().upper()
    if key in points:
        if key in label_to_point and label_to_point[key] != key:
            print(f"Warning: {key} is both a machine point and a label "
                  f"(for {label_to_point[key]}); treating it as the machine point",
                  file=sys.stderr)
        return key
    if key in label_to_point:
        return label_to_point[key]
    # Machine points (J<n>-<pin>, no underscore) don't need to appear in the
    # label file - assemblies won't list every point.
    if MACHINE_POINT.match(key):
        return key
    return None


def build_instructions(wire_path, label_to_point, points, ohms):
    lines = []
    errors = 0

    with open(wire_path, encoding="utf-8-sig") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                print(f"Warning: wire list line {lineno} not understood: {line}",
                      file=sys.stderr)
                errors += 1
                continue

            a, b = parts[0], parts[1]
            pa = resolve(a, label_to_point, points)
            pb = resolve(b, label_to_point, points)

            missing = [n for n, p in ((a, pa), (b, pb)) if p is None]
            if missing:
                print(f"Error: wire list line {lineno} ({line}): "
                      f"unknown point/label {', '.join(missing)}; wire skipped",
                      file=sys.stderr)
                errors += 1
                continue

            lines.append(f"    WIRE,   {(pa + ','):<7} {(pb + ','):<6} {ohms:.1f} Ohm")

    return lines, errors


def main():
    ap = argparse.ArgumentParser(description="Convert a wire list into WIRE instructions.")
    ap.add_argument("wirelist", help="comma-separated wire list file")
    ap.add_argument("labels", help="file containing the CUSTOM_LABELS block")
    ap.add_argument("-o", "--output", help="output file (default: print to screen)")
    ap.add_argument("-r", "--resistance", type=float, default=10.0,
                    help="resistance in ohms for each wire (default: 10.0)")
    args = ap.parse_args()

    label_to_point, points = parse_labels(args.labels)
    wires, errors = build_instructions(args.wirelist, label_to_point, points,
                                       args.resistance)

    text = "INSTRUCTIONS\nBEGIN\n" + "\n".join(wires) + ("\n" if wires else "") + "END\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Wrote {len(wires)} wire(s) to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)

    if errors:
        print(f"{errors} line(s) had problems - see messages above.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
