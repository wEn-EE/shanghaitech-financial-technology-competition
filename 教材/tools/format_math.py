"""Normalize textbook math for the tested VS Code/GitHub subset.

Only math regions are edited. Existing code is preserved. No dependencies.
Use --write to apply; default mode only reports proposed changes.
"""
from pathlib import Path
import argparse
import re
import textwrap

FENCE = re.compile(r"(^[ \t]*```[^\n]*\n.*?^[ \t]*```[^\n]*(?:\n|$))", re.M | re.S)
INLINE_CODE = re.compile(r"(`+)(.*?)\1", re.S)
MATH = re.compile(r"^\$\$[ \t]*\n(?P<display>.*?)^\$\$[ \t]*$|(?<!\$)\$(?P<inline>[^\n$]+)\$(?!\$)", re.M | re.S)
NAMES = {'Var','Cov','diag','rank','SE','tr','MSE','Binomial','offset',
         'atol','rtol','span','sgn','Bernoulli','VaR','Bias','FDR'}
MATH_FENCE = re.compile(r'^(?P<indent>[ \t]*)```math[ \t]*\n(?P<body>.*?)^[ \t]*```[ \t]*(?P<end>\n|$)', re.M | re.S)


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
    def block(source, indent='', end=''):
        value = normalize_formula(source)
        return indent+'```math\n'+textwrap.indent(value,indent)+'\n'+indent+'```'+end
    def plain(part):
        def replace(match):
            kind = 'display' if match['display'] is not None else 'inline'
            before = match[kind]
            after = normalize_formula(before)
            if kind == 'inline':
                # Word commands survive Markdown's punctuation-escape pass.
                for old,new in [(r'\,',r'\thinspace '),(r'\;',r'\thickspace '),
                                (r'\:',r'\medspace '),(r'\!',r'\negthinspace '),
                                (r'\left|',r'\left\lvert '),(r'\right|',r'\right\rvert ')]:
                    after=after.replace(old,new)
                after=after.replace('*',r'\ast ').replace('<',r'\lt ').replace('>',r'\gt ')
                after=after.rstrip()
                if r'\begin{' in after or r'\%' in after:
                    raise ValueError('Move inline matrices/escaped percentages to a display block: '+before)
            records.append({'kind':kind,'source':after,'original':before.strip()})
            if kind == 'display':
                return block(after)
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
    for i,part in enumerate(parts):
        if i%2==0:
            parts[i]=prose(part)
        else:
            m=MATH_FENCE.fullmatch(part)
            if m:
                before=textwrap.dedent(m['body']).strip()
                after=normalize_formula(before)
                records.append({'kind':'display','source':after,'original':before})
                parts[i]=block(after,m['indent'],m['end'])
    return ''.join(parts), records


def code_fences(text):
    """Return program/example fences, excluding rendered math fences."""
    return [part for part in FENCE.findall(text) if not MATH_FENCE.fullmatch(part)]


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files',nargs='+',type=Path)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    for path in args.files:
        original=path.read_text(encoding='utf-8')
        formatted, records=transform_document(original)
        assert code_fences(original)==code_fences(formatted)
        assert transform_document(formatted)[0]==formatted
        print(path, len(records), 'formulas;', 'changed' if original!=formatted else 'unchanged')
        if args.write:
            path.write_text(formatted,encoding='utf-8',newline='\n')
