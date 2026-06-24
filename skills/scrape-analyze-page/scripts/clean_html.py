# /// script
# dependencies = ["lxml"]
# ///
"""Clean HTML for LLM consumption.

Levels:
    0 — Selector-safe: strip styles, SVGs, comments, noisy attributes.
        Preserves selectors and data.
    1 — Value-safe: also strip scripts, empty elements, collapse wrapper chains.
        Preserves values and context for LLM understanding, not selectors.

Usage:
    uv run clean_html.py PAGE.html              # level 0, stdout
    uv run clean_html.py PAGE.html -l1          # level 1
    uv run clean_html.py PAGE.html -o clean.html
"""

import argparse
import sys

from lxml.html import document_fromstring, tostring, HtmlComment


KILL_TAGS_L0 = frozenset({"style", "svg"})
KILL_TAGS_L1 = frozenset({"style", "svg", "script", "noscript", "link", "meta"})
STRIP_ATTRS = frozenset({"style", "srcset", "sizes"})


def _has_text_content(el):
    """Check if element or any descendant has non-whitespace text."""
    if (el.text or "").strip():
        return True
    for child in el.iter():
        if child is el:
            continue
        if not isinstance(child.tag, str):
            continue
        if (child.text or "").strip() or (child.tail or "").strip():
            return True
    return False


def _merge_classes(parent, child):
    """Merge class attributes from parent into child."""
    pc = parent.get("class", "")
    cc = child.get("class", "")
    merged = (pc + " " + cc).strip()
    if merged:
        child.set("class", merged)


def _merge_attrs(parent, child):
    """Copy attributes from parent to child (child wins on conflict).
    class is merged; other attrs: child's value takes precedence."""
    for attr, val in parent.attrib.items():
        if attr == "class":
            continue  # handled by _merge_classes
        if attr not in child.attrib:
            child.set(attr, val)
    _merge_classes(parent, child)


def clean_html(html: str, level: int = 0) -> str:
    doc = document_fromstring(html)

    kill_tags = KILL_TAGS_L1 if level >= 1 else KILL_TAGS_L0

    # Pass 1: kill tags and comments
    for el in list(doc.iter()):
        if isinstance(el.tag, str) and el.tag in kill_tags:
            el.drop_tree()
        elif isinstance(el.tag, HtmlComment):
            el.drop_tree()

    # Pass 2: strip noisy attributes
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        for attr in list(el.attrib):
            if attr in STRIP_ATTRS or attr.startswith("on"):
                try:
                    del el.attrib[attr]
                except ValueError:
                    pass  # attr name has control chars, skip

    if level >= 1:
        # Pass 3: remove empty elements (no text, no meaningful children)
        # Repeat until stable — removing an empty child may leave parent empty
        changed = True
        while changed:
            changed = False
            for el in list(doc.iter()):
                if not isinstance(el.tag, str):
                    continue
                # Skip void elements and structural roots
                if el.tag in ("br", "hr", "img", "input", "html", "body",
                              "head", "textarea", "select", "iframe",
                              "video", "audio", "source", "canvas"):
                    continue
                if len(el) == 0 and not (el.text or "").strip():
                    # Preserve tail text
                    if (el.tail or "").strip():
                        parent = el.getparent()
                        if parent is not None:
                            prev = el.getprevious()
                            if prev is not None:
                                prev.tail = (prev.tail or "") + el.tail
                            else:
                                parent.text = (parent.text or "") + el.tail
                    el.drop_tree()
                    changed = True

        # Pass 4: collapse single-child wrapper chains
        # div.a > div.b > div.c > p  →  div.a.b.c > p
        # Merge attrs from outer into inner, unwrap outer.
        changed = True
        while changed:
            changed = False
            for el in list(doc.iter()):
                if not isinstance(el.tag, str):
                    continue
                if el.tag in ("html", "body", "head"):
                    continue
                children = list(el)
                if (len(children) == 1
                        and isinstance(children[0].tag, str)
                        and not (el.text or "").strip()
                        and not (children[0].tail or "").strip()):
                    child = children[0]
                    # Only collapse same-tag or attributeless wrapper
                    if el.tag == child.tag or not el.attrib:
                        _merge_attrs(el, child)
                        el.drop_tag()
                        changed = True

    return tostring(doc, encoding="unicode")


def read_html(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"\x1f\x8b":
        import gzip

        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html_file", help="Path to HTML file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("-l", "--level", type=int, default=0, choices=[0, 1],
                        help="Cleanup level (default: 0)")
    args = parser.parse_args()

    html = read_html(args.html_file)
    cleaned = clean_html(html, level=args.level)

    if args.output:
        with open(args.output, "w") as f:
            f.write(cleaned)
    else:
        sys.stdout.write(cleaned)


if __name__ == "__main__":
    main()
