"""Unit tests for ConfluenceConverter."""
import sys
import unittest
from pathlib import Path

# Allow importing md2markup from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from md2markup import ConfluenceConverter

FIXTURES = Path(__file__).parent / 'fixtures'


def conv(text: str) -> str:
    return ConfluenceConverter().convert(text)


class TestHeadings(unittest.TestCase):
    def test_h1(self):
        self.assertEqual(conv('# Hello'), 'h1. Hello')

    def test_h3(self):
        self.assertEqual(conv('### Title'), 'h3. Title')

    def test_h6(self):
        self.assertEqual(conv('###### Deep'), 'h6. Deep')


class TestHorizontalRule(unittest.TestCase):
    def test_dashes(self):
        self.assertEqual(conv('---'), '----')

    def test_stars(self):
        self.assertEqual(conv('***'), '----')

    def test_underscores(self):
        self.assertEqual(conv('___'), '----')


class TestBlockquote(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(conv('> Hello'), 'bq. Hello')

    def test_nested_flattened(self):
        self.assertEqual(conv('> > deep'), 'bq. deep')


class TestInlineFormatting(unittest.TestCase):
    def test_bold_stars(self):
        self.assertEqual(conv('**bold**'), '*bold*')

    def test_bold_underscores(self):
        self.assertEqual(conv('__bold__'), '*bold*')

    def test_italic_star(self):
        self.assertEqual(conv('*italic*'), '_italic_')

    def test_italic_underscore(self):
        self.assertEqual(conv('_italic_'), '_italic_')

    def test_bold_italic(self):
        self.assertEqual(conv('***bold italic***'), '*_bold italic_*')

    def test_strikethrough(self):
        self.assertEqual(conv('~~strike~~'), '-strike-')

    def test_inline_code(self):
        self.assertEqual(conv('`code`'), '{{code}}')

    def test_mixed(self):
        result = conv('**bold** and *italic*')
        self.assertEqual(result, '*bold* and _italic_')


class TestLinks(unittest.TestCase):
    def test_link(self):
        self.assertEqual(conv('[text](https://example.com)'), '[text|https://example.com]')

    def test_image(self):
        self.assertEqual(conv('![alt](https://example.com/img.png)'), '!https://example.com/img.png!')

    def test_link_with_underscore_in_url(self):
        # Underscores in URLs must NOT be converted to italics
        result = conv('[link](https://example.com/some_path/file_name)')
        self.assertEqual(result, '[link|https://example.com/some_path/file_name]')


class TestCodeBlocks(unittest.TestCase):
    def test_fenced_with_lang(self):
        md = '```python\nprint("hi")\n```'
        expected = '{code:language=python}\nprint("hi")\n{code}'
        self.assertEqual(conv(md), expected)

    def test_fenced_no_lang(self):
        md = '```\nplain code\n```'
        expected = '{code}\nplain code\n{code}'
        self.assertEqual(conv(md), expected)

    def test_tilde_fence(self):
        md = '~~~js\nconsole.log(1);\n~~~'
        expected = '{code:language=js}\nconsole.log(1);\n{code}'
        self.assertEqual(conv(md), expected)

    def test_code_block_not_inline_formatted(self):
        # Bold markers inside code block must not be converted
        md = '```\n**not bold**\n```'
        result = conv(md)
        self.assertIn('**not bold**', result)


class TestUnorderedList(unittest.TestCase):
    def test_simple(self):
        md = '- item 1\n- item 2'
        expected = '* item 1\n* item 2'
        self.assertEqual(conv(md), expected)

    def test_nested(self):
        md = '- item\n  - nested'
        expected = '* item\n** nested'
        self.assertEqual(conv(md), expected)

    def test_deep_nested(self):
        md = '- a\n  - b\n    - c'
        expected = '* a\n** b\n*** c'
        self.assertEqual(conv(md), expected)


class TestOrderedList(unittest.TestCase):
    def test_simple(self):
        md = '1. first\n2. second'
        expected = '# first\n# second'
        self.assertEqual(conv(md), expected)

    def test_nested(self):
        md = '1. first\n   1. nested'
        expected = '# first\n## nested'
        self.assertEqual(conv(md), expected)


class TestMixedList(unittest.TestCase):
    def test_ul_then_ol(self):
        md = '- bullet\n  1. numbered'
        expected = '* bullet\n*# numbered'
        self.assertEqual(conv(md), expected)


class TestTaskList(unittest.TestCase):
    def test_unchecked(self):
        self.assertEqual(conv('- [ ] todo'), '* ( ) todo')

    def test_checked(self):
        self.assertEqual(conv('- [x] done'), '* (/) done')

    def test_checked_uppercase(self):
        self.assertEqual(conv('- [X] done'), '* (/) done')


class TestTable(unittest.TestCase):
    def test_simple_table(self):
        md = '| A | B |\n|---|---|\n| 1 | 2 |'
        result = conv(md)
        self.assertIn('||A||B||', result)
        self.assertIn('|1|2|', result)

    def test_header_only(self):
        md = '| Col1 | Col2 |\n|------|------|\n| val1 | val2 |'
        result = conv(md)
        lines = result.splitlines()
        self.assertTrue(lines[0].startswith('||'))
        self.assertTrue(lines[1].startswith('|') and not lines[1].startswith('||'))


class TestFixture(unittest.TestCase):
    """End-to-end test using fixture files."""

    def test_sample_md(self):
        input_text = (FIXTURES / 'sample.md').read_text(encoding='utf-8')
        expected = (FIXTURES / 'sample_expected.txt').read_text(encoding='utf-8')
        result = ConfluenceConverter().convert(input_text)
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
