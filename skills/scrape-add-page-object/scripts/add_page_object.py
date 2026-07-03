"""Create an empty web-poet page object in a Python source file.

Must be run inside the project env so itemadapter and the item class are importable:

    uv run --project . --with libcst add_page_object.py \\
        FILE_PATH NAME DOMAIN BASE_CLASS ITEM_CLASS

Arguments are import paths (module.Class):
    BASE_CLASS  — e.g. web_poet.WebPage, zyte_common_items.BrowserPage
    ITEM_CLASS  — e.g. books_project.items.ProductItem

Required fields (those with no default in the item class) are detected automatically
via itemadapter and get @field stubs. Pass --fields name,price to override.

Based on vscode-zyte's add_empty_page_object.py (uses libcst for correct AST manipulation).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from itemadapter import ItemAdapter
from libcst import (
    Arg,
    BaseStatement,
    Call,
    ClassDef,
    Decorator,
    Ellipsis,  # noqa: A004
    EmptyLine,
    Expr,
    FunctionDef,
    IndentedBlock,
    Index,
    Name,
    Param,
    Parameters,
    Pass,
    SimpleStatementLine,
    SimpleString,
    Subscript,
    SubscriptElement,
    parse_module,
)
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor, ImportItem


@dataclass
class POGenInfo:
    name: str
    domain: str
    base_class_module: str
    base_class: str
    to_return_module: str
    to_return: str
    fields: list[str]


def _fields(value: str) -> list[str]:
    """Argparse type: validate comma-separated Python identifiers."""
    if not value:
        return []
    fields = value.split(",")
    for f in fields:
        if not f.isidentifier():
            raise argparse.ArgumentTypeError(f"'{f}' is not a valid Python identifier")
    return fields


def _import_path(value: str) -> tuple[str, str]:
    """Argparse type: split 'web_poet.WebPage' into ('web_poet', 'WebPage').

    Builtins like 'dict' return ('', 'dict') — no import needed.
    """
    if value == "dict":
        return "", value
    parts = value.rsplit(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise argparse.ArgumentTypeError(
            f"'{value}' is not a valid import path (expected module.Class, e.g. web_poet.WebPage)"
        )
    return parts[0], parts[1]


def _get_required_fields(item_class_path: str) -> list[str]:
    if not hasattr(ItemAdapter, "get_json_schema"):
        print("itemadapter 0.12.0+ is required", file=sys.stderr)
        sys.exit(1)
    sys.path.insert(0, ".")
    module, name = item_class_path.rsplit(".", 1)
    cls = getattr(import_module(module), name)
    return ItemAdapter.get_json_schema(cls).get("required", [])


def _get_new_imports(info: POGenInfo) -> list[ImportItem]:
    imports = [
        ImportItem("web_poet", "Returns"),
        ImportItem("web_poet", "handle_urls"),
        ImportItem(info.base_class_module, info.base_class),
    ]
    if info.to_return_module:
        imports.append(ImportItem(info.to_return_module, info.to_return))
    if info.fields:
        imports.append(ImportItem("web_poet", "field"))
    return imports


def _get_new_nodes(info: POGenInfo) -> list[BaseStatement]:
    domain = SimpleString(f'"{info.domain}"')
    handle_urls_deco = Decorator(
        Call(
            Name("handle_urls"),
            args=[Arg(domain)],
        )
    )

    base_class_name = Name(info.base_class)
    returns_arg = SubscriptElement(Index(Name(info.to_return)))
    returns_subscript = Subscript(Name("Returns"), slice=[returns_arg])

    body: list[BaseStatement] = []
    if info.fields:
        first = True
        for field_name in info.fields:
            if first:
                leading_lines: list[EmptyLine] = []
                first = False
            else:
                leading_lines = [EmptyLine(indent=False)]
            field_deco = Decorator(Name("field"))
            field_body = IndentedBlock([SimpleStatementLine([Expr(Ellipsis())])])
            field_def = FunctionDef(
                Name(field_name),
                params=Parameters([Param(Name("self"))]),
                body=field_body,
                decorators=[field_deco],
                leading_lines=leading_lines,
            )
            body.append(field_def)
    else:
        body.append(SimpleStatementLine([Pass()]))
    class_body = IndentedBlock(body)

    class_def = ClassDef(
        name=Name(info.name),
        bases=[Arg(base_class_name), Arg(returns_subscript)],
        body=class_body,
        decorators=[handle_urls_deco],
        leading_lines=[EmptyLine(), EmptyLine()],
    )

    return [class_def]


def add_po_to_file(file_path: Path, info: POGenInfo) -> None:
    # work around https://github.com/Instagram/LibCST/issues/1458
    import abc
    if "__provides__" in abc.ABC.__dict__ and "__providedBy__" not in abc.ABC.__dict__:
        try:
            del abc.ABC.__provides__
        except Exception:
            pass

    codemod_context = CodemodContext()
    imports_transformer = AddImportsVisitor(codemod_context, _get_new_imports(info))

    source = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    module = parse_module(source)
    new_module = module.with_changes(body=[*module.body, *_get_new_nodes(info)]).visit(
        imports_transformer
    )
    new_source = new_module.code
    if not new_source.endswith("\n"):
        new_source += "\n"
    file_path.write_text(new_source, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an empty web-poet page object in a Python source file"
    )
    parser.add_argument("file_path", help="Path to the .py file to create/append to")
    parser.add_argument("name", help="Page object class name (e.g., ProductPage)")
    parser.add_argument(
        "domain", help="Domain for @handle_urls (e.g., books.toscrape.com)"
    )
    parser.add_argument(
        "base_class",
        type=_import_path,
        help="Base class import path (e.g., web_poet.WebPage)",
    )
    parser.add_argument(
        "item_class",
        type=_import_path,
        help="Item class import path (e.g., my_project.items.ProductItem) or builtin (e.g., dict)",
    )
    parser.add_argument(
        "--fields",
        type=_fields,
        default=None,
        help="Comma-separated field names (e.g., name,price,rating). "
        "Auto-detected from item class when omitted and itemadapter is available.",
    )
    args = parser.parse_args()

    file_path = Path(args.file_path)
    base_module, base_class = args.base_class
    item_module, item_class = args.item_class
    item_class_path = f"{item_module}.{item_class}" if item_module else item_class
    fields = (
        args.fields
        if args.fields is not None
        else _get_required_fields(item_class_path)
    )

    info = POGenInfo(
        name=args.name,
        domain=args.domain,
        base_class_module=base_module,
        base_class=base_class,
        to_return_module=item_module,
        to_return=item_class,
        fields=fields,
    )

    file_path.parent.mkdir(parents=True, exist_ok=True)
    add_po_to_file(file_path, info)

    result = {
        "path": str(file_path),
        "class_name": info.name,
        "fields": info.fields,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
