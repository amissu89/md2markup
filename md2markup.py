#!/usr/bin/env python3
"""
md2markup — Markdown to Confluence Wiki Markup converter.

Usage:
    python md2markup.py input.md
    python md2markup.py input.md -o output.txt
    python md2markup.py input.md --stdout
"""
import re
import sys
import argparse
from pathlib import Path

# Placeholder tag characters — NUL-delimited, no * _ ~ ` chars so they
# don't interact with the inline-formatting regexes.
_PH_CB = '\x00CB'   # fenced code block
_PH_IC = '\x00IC'   # inline code
_PH_LK = '\x00LK'   # link / image
_PH_BD = '\x00BD'   # bold (internal, within _process_inline_formatting)
_PH_END = '\x00'


def _ph(tag: str, n: int) -> str:
    """Return a unique placeholder string for tag+counter."""
    return f'{tag}\x01{n}{_PH_END}'


class ConfluenceConverter:
    """Convert Markdown text to Confluence Wiki Markup."""

    # Regex for fenced code blocks: ```lang or ``` (no lang)
    _FENCE_START = re.compile(r'^(`{3,}|~{3,})([\w+-]*)$')
    # Inline code
    _INLINE_CODE = re.compile(r'`([^`]+)`')
    # Images: ![alt](url)  — must be before link regex
    _IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    # Links: [text](url)
    _LINK = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
    # Bold-italic: ***text*** or ___text___
    _BOLD_ITALIC = re.compile(r'(\*{3}|_{3})(.+?)\1')
    # Bold: **text** or __text__
    _BOLD = re.compile(r'(\*{2}|_{2})(.+?)\1')
    # Italic: *text* or _text_  (single, not preceded/followed by same char)
    _ITALIC = re.compile(
        r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)'
        r'|'
        r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)'
    )
    # Strikethrough: ~~text~~
    _STRIKE = re.compile(r'~~(.+?)~~')
    # Heading
    _HEADING = re.compile(r'^(#{1,6})\s+(.*)')
    # HR: --- or *** or ___ on its own line (3+ chars)
    _HR = re.compile(r'^(\*{3,}|-{3,}|_{3,})\s*$')
    # Blockquote
    _BLOCKQUOTE = re.compile(r'^>\s?(.*)')
    # Unordered list item: -, *, + with optional leading spaces
    _UL_ITEM = re.compile(r'^(\s*)([-*+])\s+(.*)')
    # Ordered list item
    _OL_ITEM = re.compile(r'^(\s*)(\d+)\.\s+(.*)')
    # Task list checked/unchecked
    _TASK_CHECKED = re.compile(r'^\[x\]\s+', re.IGNORECASE)
    _TASK_UNCHECKED = re.compile(r'^\[ \]\s+')
    # Table row: starts and ends with |
    _TABLE_ROW = re.compile(r'^\|(.+)\|$')
    # Table separator row: |---|---|
    _TABLE_SEP = re.compile(r'^\|[-| :]+\|$')

    def convert(self, text: str) -> str:
        trailing_newline = text.endswith('\n')
        lines = text.splitlines()

        # Pass 1: Extract fenced code blocks → placeholders
        lines, code_map = self._extract_code_blocks(lines)

        # Pass 2: Block structure (headings, HR, blockquotes, lists, tables)
        lines = self._process_block_structure(lines)

        # Pass 3–6: Per-line inline processing
        result_lines = []
        inline_map: dict = {}
        link_map: dict = {}

        for line in lines:
            # Code block placeholders pass through unchanged
            if _PH_CB in line:
                result_lines.append(line)
                continue

            # Pass 3: Extract inline code → placeholders
            line, inline_map = self._extract_inline_code(line, inline_map)

            # Pass 4: Extract links/images → placeholders (protect _ in URLs)
            line, link_map = self._extract_links(line, link_map)

            # Pass 5: Inline formatting
            line = self._process_inline_formatting(line)

            # Pass 6: Restore link/image placeholders, then inline code
            line = self._restore_placeholders(line, link_map)
            line = self._restore_placeholders(line, inline_map)

            result_lines.append(line)

        # Restore code block placeholders in final text
        output = '\n'.join(result_lines)
        output = self._restore_placeholders(output, code_map)
        if trailing_newline:
            output += '\n'

        return output

    # ------------------------------------------------------------------
    # Pass 1: Fenced code blocks
    # ------------------------------------------------------------------

    def _extract_code_blocks(self, lines: list) -> tuple:
        result = []
        code_map: dict = {}
        idx = 0
        counter = 0

        while idx < len(lines):
            m = self._FENCE_START.match(lines[idx])
            if m:
                fence_char = m.group(1)[0]  # ` or ~
                lang = m.group(2).strip()
                idx += 1
                body_lines = []
                # Collect until matching closing fence
                while idx < len(lines):
                    close_m = re.match(
                        r'^' + re.escape(fence_char) + r'{3,}\s*$', lines[idx]
                    )
                    if close_m:
                        idx += 1
                        break
                    body_lines.append(lines[idx])
                    idx += 1
                # Build Confluence {code} block
                if lang:
                    header = '{code:language=' + lang + '}'
                else:
                    header = '{code}'
                body = '\n'.join(body_lines)
                confluence_block = header + '\n' + body + '\n{code}'
                key = _ph(_PH_CB, counter)
                code_map[key] = confluence_block
                result.append(key)
                counter += 1
            else:
                result.append(lines[idx])
                idx += 1

        return result, code_map

    # ------------------------------------------------------------------
    # Pass 2: Block structure
    # ------------------------------------------------------------------

    def _process_block_structure(self, lines: list) -> list:
        result = []
        i = 0
        list_stack = []  # stack of 'ul' or 'ol'

        table_buffer = []

        def flush_table():
            nonlocal table_buffer
            if table_buffer:
                result.extend(self._process_table(table_buffer))
                table_buffer = []

        while i < len(lines):
            line = lines[i]

            # Skip code block placeholders unchanged
            if _PH_CB in line:
                flush_table()
                list_stack = []
                result.append(line)
                i += 1
                continue

            # --- Table detection ---
            if self._TABLE_ROW.match(line):
                table_buffer.append(line)
                i += 1
                continue
            else:
                flush_table()

            # --- Heading ---
            m = self._HEADING.match(line)
            if m:
                list_stack = []
                level = len(m.group(1))
                content = m.group(2).rstrip()
                result.append(f'h{level}. {content}')
                i += 1
                continue

            # --- HR ---
            if (
                self._HR.match(line)
                and not self._UL_ITEM.match(line)
                and not self._OL_ITEM.match(line)
            ):
                list_stack = []
                result.append('----')
                i += 1
                continue

            # --- Blockquote ---
            m = self._BLOCKQUOTE.match(line)
            if m:
                list_stack = []
                content = m.group(1)
                # Flatten nested blockquotes
                while self._BLOCKQUOTE.match(content):
                    content = self._BLOCKQUOTE.match(content).group(1)
                result.append(f'bq. {content}')
                i += 1
                continue

            # --- Unordered list ---
            m = self._UL_ITEM.match(line)
            if m:
                indent = len(m.group(1))
                content = m.group(3)
                depth = indent // 2 + 1
                while len(list_stack) > depth:
                    list_stack.pop()
                while len(list_stack) < depth:
                    list_stack.append('ul')
                list_stack[depth - 1] = 'ul'
                prefix = self._list_prefix(list_stack[:depth])
                if self._TASK_CHECKED.match(content):
                    content = self._TASK_CHECKED.sub('', content)
                    result.append(f'{prefix} (/) {content}')
                elif self._TASK_UNCHECKED.match(content):
                    content = self._TASK_UNCHECKED.sub('', content)
                    result.append(f'{prefix} ( ) {content}')
                else:
                    result.append(f'{prefix} {content}')
                i += 1
                continue

            # --- Ordered list ---
            m = self._OL_ITEM.match(line)
            if m:
                indent = len(m.group(1))
                content = m.group(3)
                depth = indent // 2 + 1
                while len(list_stack) > depth:
                    list_stack.pop()
                while len(list_stack) < depth:
                    list_stack.append('ol')
                list_stack[depth - 1] = 'ol'
                prefix = self._list_prefix(list_stack[:depth])
                result.append(f'{prefix} {content}')
                i += 1
                continue

            # Any non-list line resets the list stack
            list_stack = []
            result.append(line)
            i += 1

        flush_table()
        return result

    def _list_prefix(self, stack: list) -> str:
        return ''.join('*' if t == 'ul' else '#' for t in stack)

    def _process_table(self, rows: list) -> list:
        """Convert markdown table rows to Confluence markup."""
        result = []
        sep_indices = [i for i, r in enumerate(rows) if self._TABLE_SEP.match(r)]

        if not sep_indices:
            for row in rows:
                result.append(self._format_table_row(row, header=False))
            return result

        sep_idx = sep_indices[0]
        for row in rows[:sep_idx]:
            result.append(self._format_table_row(row, header=True))
        for row in rows[sep_idx + 1:]:
            if not self._TABLE_SEP.match(row):
                result.append(self._format_table_row(row, header=False))
        return result

    def _format_table_row(self, row: str, header: bool) -> str:
        inner = row.strip()
        if inner.startswith('|'):
            inner = inner[1:]
        if inner.endswith('|'):
            inner = inner[:-1]
        cells = [c.strip() for c in inner.split('|')]
        sep = '||' if header else '|'
        return sep + sep.join(cells) + sep

    # ------------------------------------------------------------------
    # Pass 3: Inline code extraction
    # ------------------------------------------------------------------

    def _extract_inline_code(self, line: str, inline_map: dict) -> tuple:
        counter = len(inline_map)

        def replacer(m: re.Match) -> str:
            nonlocal counter
            key = _ph(_PH_IC, counter)
            content = m.group(1)
            # Confluence parses {{ as a macro start, so braces inside {{...}}
            # must be escaped as HTML entities to avoid "Unknown macro" errors.
            # This also works safely inside table cells, unlike {code}...{code}
            # which is a block-level macro and breaks table layout.
            if '{' in content or '}' in content:
                content = content.replace('{', '&#123;').replace('}', '&#125;')
            inline_map[key] = '{{' + content + '}}'
            counter += 1
            return key

        line = self._INLINE_CODE.sub(replacer, line)
        return line, inline_map

    # ------------------------------------------------------------------
    # Pass 4: Link / image extraction
    # ------------------------------------------------------------------

    def _extract_links(self, line: str, link_map: dict) -> tuple:
        counter = len(link_map)

        def img_replacer(m: re.Match) -> str:
            nonlocal counter
            key = _ph(_PH_LK, counter)
            link_map[key] = f'!{m.group(2)}!'
            counter += 1
            return key

        def link_replacer(m: re.Match) -> str:
            nonlocal counter
            key = _ph(_PH_LK, counter)
            link_map[key] = f'[{m.group(1)}|{m.group(2)}]'
            counter += 1
            return key

        # Images first (subset of link syntax)
        line = self._IMAGE.sub(img_replacer, line)
        line = self._LINK.sub(link_replacer, line)
        return line, link_map

    # ------------------------------------------------------------------
    # Pass 5: Inline formatting
    # ------------------------------------------------------------------

    def _process_inline_formatting(self, line: str) -> str:
        # Temporarily store converted bold/bold-italic as placeholders so
        # the italic pass does not re-process the surrounding `*` chars.
        bold_map: dict = {}
        bd_counter = [0]

        def store_bold(wiki: str) -> str:
            key = _ph(_PH_BD, bd_counter[0])
            bold_map[key] = wiki
            bd_counter[0] += 1
            return key

        # Bold-italic first (***text*** or ___text___)
        line = self._BOLD_ITALIC.sub(
            lambda m: store_bold(f'*_{m.group(2)}_*'), line
        )
        # Bold (**text** or __text__)
        line = self._BOLD.sub(
            lambda m: store_bold(f'*{m.group(2)}*'), line
        )
        # Italic (*text* or _text_)
        def italic_repl(m: re.Match) -> str:
            content = m.group(1) if m.group(1) is not None else m.group(2)
            return f'_{content}_'

        line = self._ITALIC.sub(italic_repl, line)
        # Strikethrough
        line = self._STRIKE.sub(lambda m: f'-{m.group(1)}-', line)
        # Restore bold placeholders
        line = self._restore_placeholders(line, bold_map)
        return line

    # ------------------------------------------------------------------
    # Pass 6: Restore placeholders
    # ------------------------------------------------------------------

    def _restore_placeholders(self, text: str, placeholder_map: dict) -> str:
        for key, value in placeholder_map.items():
            text = text.replace(key, value)
        return text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='md2markup',
        description='Convert Markdown to Confluence Wiki Markup.',
    )
    parser.add_argument('input', help='Input Markdown file')
    parser.add_argument(
        '-o', '--output', default=None,
        help='Output file (default: input with .txt extension)',
    )
    parser.add_argument(
        '--stdout', action='store_true',
        help='Print to stdout instead of writing a file',
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f'Error: file not found: {input_path}', file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding='utf-8')
    converter = ConfluenceConverter()
    output = converter.convert(text)

    if args.stdout:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        print(output)
    else:
        out_path = Path(args.output) if args.output else input_path.with_suffix('.txt')
        out_path.write_text(output, encoding='utf-8')
        print(f'Written to {out_path}')


if __name__ == '__main__':
    main()
