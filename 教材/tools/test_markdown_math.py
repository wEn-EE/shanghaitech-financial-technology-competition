import unittest
from markdown_math import convert_math, convert_document


class MarkdownMathTests(unittest.TestCase):
    def test_nested_fraction_scope(self):
        source = r"\frac{1+\frac{x}{y}}{z^2}"
        result = convert_math(source)
        for x, y, z in ((2., 3., 4.), (-1., 2., .5), (0., -3., 7.)):
            actual = eval(result.replace("^", "**"), {"__builtins__": {}}, {"x": x, "y": y, "z": z})
            self.assertAlmostEqual(actual, (1 + x / y) / z**2)

    def test_unbraced_fraction_arguments(self):
        self.assertEqual(convert_math(r"\frac12"), "((1) / (2))")
        self.assertEqual(convert_math(r"\frac1n"), "((1) / (n))")

    def test_indices_bounds_and_grouping(self):
        self.assertEqual(convert_math(r"\sum_{i=1}^{n-1}x_iy_i"), "∑_(i = 1)^(n-1) x_i y_i")
        self.assertEqual(convert_math(r"x_i\sigma_i^{-1}"), "x_i σ_i^(-1)")

    def test_matrix_rows_preserved(self):
        result = convert_math(r"\begin{pmatrix}1&2&3\\4&5&6\end{pmatrix}")
        self.assertEqual(result, "[[1, 2, 3]; [4, 5, 6]]")

    def test_set_braces_and_norm_are_distinct(self):
        self.assertEqual(convert_math(r"\mathcal N(M)=\{x:Mx=0\}"), "𝒩(M) = {x:Mx = 0}")
        self.assertEqual(convert_math(r"\|x\|_2"), "‖x‖_2")

    def test_labels_become_explicit_definitions(self):
        self.assertEqual(convert_math(r"M=\underbrace{A}_L\underbrace{B}_U"), "M = L U\nL = A\nU = B")

    def test_cases_keep_conditions(self):
        self.assertEqual(convert_math(r"\begin{cases}1,&x>0\\0,&\text{否则}\end{cases}"),
                         "分段{ 1，当 x>0；0，否则 }")

    def test_unknown_or_broken_syntax_fails(self):
        for source in (r"\unknown{x}", r"\frac{a}{", r"a}", r"\begin{matrix}a\end{matrix}"):
            with self.assertRaises(ValueError):
                convert_math(source)

    def test_code_preserved_and_conversion_idempotent(self):
        code = '```python\nvalue = "$x$"\n```\n'
        original = code + 'Literal `$x$`; math $x^2$.\n\n$$\na\n=\nb\n$$\n'
        converted, counts, _ = convert_document(original)
        self.assertTrue(converted.startswith(code))
        self.assertIn('Literal `$x$`', converted)
        self.assertIn('```text\na = b\n```', converted)
        self.assertEqual(counts, {"display": 1, "inline": 1})
        again, counts, _ = convert_document(converted)
        self.assertEqual(again, converted)
        self.assertEqual(counts, {"display": 0, "inline": 0})


if __name__ == "__main__":
    unittest.main()
