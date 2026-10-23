"""Regression checks for Markdown/math boundary failures observed on GitHub."""
import unittest
from format_math import transform_document, code_fences
from check_github_math import compare


class MathBoundaryTests(unittest.TestCase):
    def test_display_transport_protection(self):
        source = '$$\nN=\\begin{pmatrix}821&27\\\\26&125\\end{pmatrix}\n$$\n'
        value, records = transform_document(source)
        self.assertIn('```math\n', value)
        self.assertEqual(records[0]['source'], r'N=\begin{pmatrix}821&27\\26&125\end{pmatrix}')
        self.assertEqual(transform_document(value)[0], value)

    def test_inline_safe_commands(self):
        source = r'例如 $x>0$ ， $X^{*(b)}$ ， $\int f(x)\,dx$ 。'
        value, _ = transform_document(source)
        self.assertIn(r'$x\gt 0$', value)
        self.assertIn(r'$X^{\ast (b)}$', value)
        self.assertIn(r'\thinspace dx', value)
        self.assertEqual(transform_document(value)[0], value)

    def test_program_code_is_unchanged(self):
        source = '```python\nprint("$x$", "\\\\")\n```\n\n$$\nx^2\n$$\n'
        value, _ = transform_document(source)
        self.assertEqual(code_fences(source), code_fences(value))

    def test_list_math_indentation(self):
        source = '4. 问题：\n\n   ```math\n   M=\\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}\n   ```\n\n   解释。\n'
        value, records = transform_document(source)
        self.assertEqual(value, source)
        self.assertEqual(len(records), 1)

    def test_inline_matrix_requires_editorial_move(self):
        with self.assertRaises(ValueError):
            transform_document(r'矩阵 $M=\begin{pmatrix}1&2\\3&4\end{pmatrix}$ 。')

    def test_transport_detects_lost_matrix_separator(self):
        source = '```math\nM=\\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}\n```'
        good = '<math-renderer>$$M=\\begin{pmatrix}1&amp;2\\\\3&amp;4\\end{pmatrix}$$</math-renderer>'
        self.assertFalse(compare(source, good)['missing_or_changed'])
        bad = good.replace('\\\\3', '\\3')
        self.assertTrue(compare(source, bad)['missing_or_changed'])

    def test_transport_detects_unrecognized_inline(self):
        result = compare('价格为 $P_t$ 。', '<p>价格为 $P_t$ 。</p>')
        self.assertEqual(result['expected'], 1)
        self.assertEqual(result['recognized'], 0)

    def test_escaped_percentage_survives_math_fence(self):
        source = '```math\nr=1\\%,\\qquad \\text{jump\\_alert}=1\n```\n'
        value, records = transform_document(source)
        self.assertEqual(value, source)
        self.assertIn(r'\%', records[0]['source'])


if __name__ == '__main__':
    unittest.main()
