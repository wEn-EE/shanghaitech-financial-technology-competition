"""Normalize textbook dollar math for the tested VS Code/GitHub subset.

Only math regions are edited. Existing code is preserved. No dependencies.
Use --write to apply; default mode only reports proposed changes.
"""
from pathlib import Path
import argparse
import re

FENCE = re.compile(r"(^[ \t]*```[^\n]*\n.*?^[ \t]*```[^\n]*(?:\n|$))", re.M | re.S)
INLINE_CODE = re.compile(r"(`+)(.*?)\1", re.S)
MATH = re.compile(r"^\$\$[ \t]*\n(?P<display>.*?)^\$\$[ \t]*$|(?<!\$)\$(?P<inline>[^\n$]+)\$(?!\$)", re.M | re.S)
NAMES = {'Var','Cov','diag','rank','SE','tr','MSE','Binomial','offset',
         'atol','rtol','span','sgn','Bernoulli','VaR','Bias','FDR'}


def normalize_formula(source):
    def named(match):
        name = match[1]
        if name not in NAMES:
            raise ValueError('Review operator spacing/limits before replacing: '+name)
        return r'\mathrm{' + name + '}'
    value = re.sub(r'\\operatorname\{([^{}]+)\}', named, source)
    if r'\operatorname' in value:
        raise ValueError('Unsupported operatorname form; manual review required')
    value = value.replace(r'\{', r'\lbrace ').replace(r'\}', r'\rbrace ')
    value = value.replace(r'\|', r'\Vert ')
    value = re.sub(r'\{\\rm\s+([A-Za-z]+)\}', lambda m: r'{\mathrm{'+m[1]+'}}', value)
    # A bare equals line can be interpreted as a Setext heading by Markdown.
    value = re.sub(r'(?m)^\s*=\s*\n', '= ', value)
    return '\n'.join(line.rstrip() for line in value.strip().splitlines())


def transform_document(text):
    records = []
    def plain(part):
        def replace(match):
            kind = 'display' if match['display'] is not None else 'inline'
            before = match[kind]
            after = normalize_formula(before)
            records.append({'kind':kind,'source':after,'original':before.strip()})
            if kind == 'display':
                return '$$\n'+after+'\n$$'
            left = ' ' if match.start() and not part[match.start()-1].isspace() else ''
            right = ' ' if match.end()<len(part) and not part[match.end()].isspace() else ''
            return left+'$'+after+'$'+right
        return MATH.sub(replace, part)
    def prose(part):
        output, pos = [], 0
        for m in INLINE_CODE.finditer(part):
            output.extend([plain(part[pos:m.start()]),m[0]])
            pos=m.end()
        output.append(plain(part[pos:]))
        return ''.join(output)
    parts=FENCE.split(text)
    for i in range(0,len(parts),2):
        parts[i]=prose(parts[i])
    return ''.join(parts), records


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files',nargs='+',type=Path)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    for path in args.files:
        original=path.read_text(encoding='utf-8')
        formatted, records=transform_document(original)
        assert FENCE.findall(original)==FENCE.findall(formatted)
        assert transform_document(formatted)[0]==formatted
        print(path, len(records), 'formulas;', 'changed' if original!=formatted else 'unchanged')
        if args.write:
            path.write_text(formatted,encoding='utf-8',newline='\n')
