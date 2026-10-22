"""Convert the textbook's audited math subset into portable Markdown text.

No math renderer or external package is required. Unsupported syntax fails closed.
Original LaTeX remains recoverable in Git history. Omit --write for a dry run.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "theta": "θ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "kappa": "κ", "eta": "η",
    "phi": "φ", "omega": "ω", "Delta": "Δ", "Lambda": "Λ", "Sigma": "Σ",
    "Pi": "Π", "Phi": "Φ", "Omega": "Ω", "Gamma": "Γ", "Theta": "Θ",
    "chi": "χ", "ell": "ℓ", "infty": "∞", "partial": "∂", "nabla": "∇",
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠",
    "approx": "≈", "lesssim": "≲", "in": "∈", "subseteq": "⊆",
    "times": "×", "cdot": "·", "pm": "±", "propto": "∝", "perp": "⊥",
    "cup": "∪", "cap": "∩", "bigcup": "⋃", "sum": "∑", "prod": "∏",
    "int": "∫", "mid": "|", "sim": "~", "to": "→", "rightarrow": "→",
    "longrightarrow": "→", "Rightarrow": "⇒", "Longleftrightarrow": "⇔",
    "downarrow": "↓", "succeq": "⪰", "succ": "≻", "star": "★", "top": "T",
    "ldots": "…", "cdots": "⋯", "vdots": "⋮", "lceil": "⌈", "rceil": "⌉",
    "|": "‖", "{": "{", "}": "}", "%": "%", "_": "_",
}
FUNCTIONS = {"max", "min", "arg", "dim", "det", "cos", "sin", "log", "ln", "exp", "lim", "inf", "sup", "bmod"}
CAL = {"C": "𝒞", "N": "𝒩", "R": "ℛ", "D": "𝒟", "L": "ℒ", "F": "ℱ", "H": "ℋ"}
BB = {"R": "ℝ", "E": "𝔼", "P": "ℙ", "N": "ℕ", "C": "ℂ"}
FENCE = re.compile(r"(^[ \t]*```[^\n]*\n.*?^[ \t]*```[^\n]*(?:\n|$))", re.M | re.S)
INLINE_CODE = re.compile(r"(`+)(.*?)\1", re.S)
DISPLAY = re.compile(r"^[ \t]*\$\$[ \t]*\n(.*?)^[ \t]*\$\$[ \t]*$", re.M | re.S)
INLINE_MATH = re.compile(r"(?<!\$)\$([^\n$]+)\$(?!\$)")


class MathReader:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.definitions = []

    def skip_space(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def argument(self):
        self.skip_space()
        if self.pos >= len(self.text):
            raise ValueError("missing argument")
        if self.text[self.pos] == "{":
            self.pos += 1
            value = self.sequence("}")
            if self.pos >= len(self.text) or self.text[self.pos] != "}":
                raise ValueError("unclosed group")
            self.pos += 1
            return value
        return self.atom()

    def raw_group(self):
        self.skip_space()
        if self.pos >= len(self.text) or self.text[self.pos] != "{":
            raise ValueError("expected braced name")
        end = self.text.find("}", self.pos)
        if end < 0:
            raise ValueError("unclosed name")
        value = self.text[self.pos + 1:end]
        self.pos = end + 1
        return value

    def script(self, marker, value):
        value = value.strip()
        if len(value) == 1 or re.fullmatch(r"[A-Za-z0-9]+", value):
            return marker + value
        return marker + "(" + value + ")"

    def atom(self):
        char = self.text[self.pos]
        self.pos += 1
        if char == "{":
            self.pos -= 1
            return "(" + self.argument() + ")"
        if char != "\\":
            if char == "}":
                raise ValueError("unexpected closing brace")
            return char
        if self.pos >= len(self.text):
            raise ValueError("trailing backslash")
        match = re.match(r"[A-Za-z]+", self.text[self.pos:])
        if match:
            command = match.group()
            self.pos += len(command)
        else:
            command = self.text[self.pos]
            self.pos += 1
        if command in SYMBOLS:
            return SYMBOLS[command]
        if command in FUNCTIONS:
            return command + " "
        if command in ("left", "right", "rm"):
            return ""
        if command in ("quad", "qquad", ",", ";", " "):
            return " "
        if command in ("frac", "tfrac"):
            numerator, denominator = self.argument(), self.argument()
            return "((" + numerator + ") / (" + denominator + "))"
        if command == "sqrt":
            return "sqrt(" + self.argument() + ")"
        if command == "binom":
            return "C(" + self.argument() + ", " + self.argument() + ")"
        if command in ("text", "mathrm", "operatorname"):
            return self.argument()
        if command == "mathbf":
            value = self.argument()
            return "𝟏" if value == "1" else "bold(" + value + ")"
        if command in ("mathbb", "mathcal"):
            value = self.argument()
            mapping = BB if command == "mathbb" else CAL
            if value not in mapping:
                raise ValueError("unmapped math alphabet: " + value)
            return mapping[value]
        if command in ("bar", "hat", "widehat", "tilde", "widetilde"):
            value = self.argument()
            accent = {"bar": "\u0304", "hat": "\u0302", "widehat": "\u0302",
                      "tilde": "\u0303", "widetilde": "\u0303"}[command]
            return value + accent if len(value) == 1 else command + "(" + value + ")"
        if command == "boxed":
            return self.argument()
        if command == "xrightarrow":
            return "→[" + self.argument() + "] "
        if command == "overset":
            label, base = self.argument(), self.argument()
            return base + "[" + label + "] "
        if command == "underbrace":
            value = self.argument()
            self.skip_space()
            if self.pos >= len(self.text) or self.text[self.pos] != "_":
                raise ValueError("underbrace requires its label")
            self.pos += 1
            label = self.argument()
            self.definitions.append(label + " = " + value)
            return label + " "
        if command == "begin":
            name = self.raw_group()
            if name not in ("pmatrix", "smallmatrix", "cases"):
                raise ValueError("unsupported environment: " + name)
            terminator = "\\end{" + name + "}"
            end = self.text.find(terminator, self.pos)
            if end < 0:
                raise ValueError("unclosed environment")
            content = self.text[self.pos:end]
            self.pos = end + len(terminator)
            rows = re.split(r"\\\\", content)
            rendered = []
            for row in rows:
                if not row.strip():
                    continue
                cells = [convert_math(cell) for cell in row.split("&")]
                if name == "cases":
                    if len(cells) != 2:
                        raise ValueError("cases requires a value and a condition")
                    result, condition = cells
                    result = result.rstrip(",")
                    rendered.append(result + "，" + ("当 " if condition != "否则" else "") + condition)
                else:
                    rendered.append("[" + ", ".join(cells) + "]")
            if name == "cases":
                return "分段{ " + "；".join(rendered) + " }"
            return "[" + "; ".join(rendered) + "]"
        raise ValueError("unsupported command: \\" + command)

    def sequence(self, stop=None):
        output = []
        while self.pos < len(self.text):
            if stop is not None and self.text[self.pos] == stop:
                break
            if self.text[self.pos] in "_^":
                marker = self.text[self.pos]
                self.pos += 1
                output.append(self.script(marker, self.argument()))
                if self.pos < len(self.text) and (self.text[self.pos].isalnum() or self.text[self.pos] == "\\"):
                    output.append(" ")
                continue
            if self.text[self.pos].isspace():
                self.skip_space()
                output.append(" ")
                continue
            output.append(self.atom())
        return "".join(output).strip()


def convert_math(source):
    reader = MathReader(source)
    result = reader.sequence()
    if reader.pos != len(source):
        raise ValueError("unconsumed input")
    result = re.sub(r"[ \t\n]+", " ", result).strip()
    result = result.replace("arg max", "argmax").replace("arg min", "argmin")
    result = re.sub(r"\s*([=≤≥≠≈≲∈⊆×·±∝⊥⪰≻⇒⇔])\s*", r" \1 ", result)
    result = re.sub(r"\b(max|min|cos|sin|log|ln|exp|det) +\(", r"\1(", result)
    if reader.definitions:
        result += "\n" + "\n".join(reader.definitions)
    return result.strip()


def inline_code(value):
    if "`" in value:
        raise ValueError("backtick inside a mathematical expression")
    return "`" + value + "`"


def convert_document(text):
    counts = {"display": 0, "inline": 0}
    records = []
    parts = FENCE.split(text)
    def prose(value):
        pieces, pos = [], 0
        for match in INLINE_CODE.finditer(value):
            pieces.append(plain(value[pos:match.start()]))
            pieces.append(match.group())
            pos = match.end()
        pieces.append(plain(value[pos:]))
        return "".join(pieces)
    def plain(value):
        def replace_display(match):
            original = match.group(1).strip()
            rendered = convert_math(original)
            counts["display"] += 1
            records.append({"kind": "display", "source": original, "text": rendered})
            return "```text\n" + rendered + "\n```"
        value = DISPLAY.sub(replace_display, value)
        def replace_inline(match):
            rendered = convert_math(match.group(1))
            counts["inline"] += 1
            records.append({"kind": "inline", "source": match.group(1), "text": rendered})
            line_start = value.rfind("\n", 0, match.start()) + 1
            if value[line_start:match.start()].lstrip().startswith("|"):
                rendered = rendered.replace("|", r"\|")
            return inline_code(rendered)
        return INLINE_MATH.sub(replace_inline, value)
    for i in range(0, len(parts), 2):
        parts[i] = prose(parts[i])
    return "".join(parts), counts, records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    planned, audit = [], []
    for path in args.files:
        before = path.read_text(encoding="utf-8")
        after, counts, records = convert_document(before)
        original_code = FENCE.findall(before)
        remaining = iter(FENCE.findall(after))
        for old in original_code:
            if not any(candidate == old for candidate in remaining):
                raise ValueError("existing code changed: " + str(path))
        second, again, _ = convert_document(after)
        if second != after or any(again.values()):
            raise ValueError("conversion is not idempotent")
        planned.append((path, after))
        audit.append({"file": str(path), "counts": counts, "formulas": records})
        print(json.dumps({"file": str(path), **counts}, ensure_ascii=True))
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.write:
        for path, after in planned:
            path.write_text(after, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
