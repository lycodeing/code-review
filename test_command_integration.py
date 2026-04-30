#!/usr/bin/env python3
"""命令系统集成测试脚本（直接导入模块，避免 __init__.py）。"""

import sys
from pathlib import Path

# 添加 src 目录到路径
src_path = Path(__file__).parent / "apps" / "backend" / "src"
sys.path.insert(0, str(src_path))


def test_command_router():
    """测试命令路由器。"""
    # 直接导入模块，避免通过 __init__.py
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "command_router",
        src_path / "code_review" / "services" / "command_router.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    router = module.CommandRouter()

    test_cases = [
        ("/review", ("review", "")),
        ("/review please", ("review", "please")),
        ("/Review", ("review", "")),
        ("/describe", ("describe", "")),
        ("/improve this code", ("improve", "this code")),
        ("/analyze", ("analyze", "")),
        ("just a comment", None),
        ("/unknown", None),
    ]

    print("✓ 测试命令路由器")
    for input_str, expected in test_cases:
        result = router.parse_command(input_str)
        assert result == expected, f"失败: {input_str} -> {result} (期望: {expected})"
    print("  所有测试用例通过")


def test_webhook_event_structure():
    """测试 WebhookEvent 结构支持命令模式。"""
    import importlib.util

    # 导入 platform 模块
    spec = importlib.util.spec_from_file_location(
        "platform",
        src_path / "code_review" / "core" / "platform.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    event = module.WebhookEvent(
        platform=module.PlatformType.GITHUB,
        project_id="owner/repo",
        mr_id="123",
        mr_iid="456",
        action="command",
        event_id="test-command-1",
        raw_payload={
            "command": "review",
            "args": "",
            "project_id": "owner/repo",
            "mr_iid": "456",
        },
    )

    assert event.action == "command"
    assert event.raw_payload["command"] == "review"
    print("✓ 测试 WebhookEvent 命令模式结构")
    print("  命令模式事件创建成功")


def test_command_handler():
    """测试命令处理器可以导入。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "command_handler",
        src_path / "code_review" / "services" / "command_handler.py"
    )
    module = importlib.util.module_from_spec(spec)

    # 模块依赖 command_router，需要先导入
    import sys
    command_router_spec = importlib.util.spec_from_file_location(
        "command_router",
        src_path / "code_review" / "services" / "command_router.py"
    )
    command_router_module = importlib.util.module_from_spec(command_router_spec)
    command_router_spec.loader.exec_module(command_router_module)
    sys.modules["code_review.services.command_router"] = command_router_module

    spec.loader.exec_module(module)

    assert hasattr(module, "CommandHandler")
    print("✓ 测试命令处理器导入")
    print("  CommandHandler 类导入成功")


def main():
    """运行所有测试。"""
    print("=" * 60)
    print("命令系统集成测试")
    print("=" * 60)
    print()

    try:
        test_command_router()
        print()
        test_webhook_event_structure()
        print()
        test_command_handler()
        print()
        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
