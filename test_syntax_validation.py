#!/usr/bin/env python3
"""语法验证脚本（验证所有文件可以正确编译）。"""

import ast
from pathlib import Path


def validate_python_file(file_path: Path) -> bool:
    """验证 Python 文件语法是否正确。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        ast.parse(code)
        return True
    except SyntaxError as e:
        print(f"✗ 语法错误 {file_path}:{e.lineno}: {e.msg}")
        return False
    except Exception as e:
        print(f"✗ 读取错误 {file_path}: {e}")
        return False


def main():
    """验证所有新创建和修改的文件。"""
    print("=" * 60)
    print("语法验证")
    print("=" * 60)
    print()

    base_path = Path(__file__).parent / "apps" / "backend" / "src" / "code_review"

    files_to_validate = [
        base_path / "services" / "command_router.py",
        base_path / "services" / "command_handler.py",
        base_path / "api" / "webhook.py",
        base_path / "services" / "review_orchestrator.py",
    ]

    all_valid = True
    for file_path in files_to_validate:
        if file_path.exists():
            relative_path = file_path.relative_to(Path(__file__).parent)
            if validate_python_file(file_path):
                print(f"✓ {relative_path}")
            else:
                all_valid = False
        else:
            print(f"✗ 文件不存在: {file_path}")
            all_valid = False

    print()
    print("=" * 60)
    if all_valid:
        print("✓ 所有文件语法验证通过")
        print("=" * 60)
        return 0
    else:
        print("✗ 部分文件语法验证失败")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
