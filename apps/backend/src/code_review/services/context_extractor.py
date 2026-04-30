"""上下文提取器 — 从 diff 中提取跨文件引用并加载相关文件内容。"""

import logging
import re

from code_review.core.platform import PlatformAdapter, FileChange

logger = logging.getLogger(__name__)

_IMPORT_PATTERNS: dict[str, list[str]] = {
    "python": [
        r"(?:from|import)\s+([a-zA-Z_][\w.]*)",
    ],
    "java": [
        r"import\s+(?:static\s+)?([\w.]+)",
    ],
    "go": [
        r'"([^"]+)"',
    ],
    "javascript": [
        r"(?:import\s+.*?from\s+|require\s*\(\s*)['\"]([^'\"]+)['\"]",
    ],
    "typescript": [
        r"(?:import\s+.*?from\s+|require\s*\(\s*)['\"]([^'\"]+)['\"]",
    ],
}


def _detect_language(file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    ext_map = {
        "py": "python", "java": "java", "go": "go",
        "js": "javascript", "jsx": "javascript",
        "ts": "typescript", "tsx": "typescript",
    }
    return ext_map.get(ext, "")


def _resolve_import_path(import_path: str, language: str) -> str:
    """将 import 路径转为文件系统路径。"""
    if language == "python":
        return import_path.replace(".", "/") + ".py"
    elif language == "java":
        return import_path.replace(".", "/") + ".java"
    elif language == "go":
        return import_path
    elif language in ("javascript", "typescript"):
        path = import_path.lstrip("@/").lstrip("./").lstrip("../")
        if not path.endswith((".js", ".jsx", ".ts", ".tsx")):
            path = path + "/index.ts" if language == "typescript" else path + "/index.js"
        return path
    return import_path


class ContextExtractor:
    """从 diff 中提取跨文件引用并加载相关文件内容。"""

    async def extract_context(
        self,
        adapter: PlatformAdapter,
        project_id: str,
        changes: list[FileChange],
        source_branch: str,
        max_files: int = 5,
        max_file_size: int = 10000,
    ) -> dict[str, str]:
        """提取并加载相关文件上下文。返回 {file_path: content} 映射。"""
        changed_paths = {c.path for c in changes}
        import_paths: dict[str, None] = {}

        for change in changes:
            language = _detect_language(change.path)
            if not language or language not in _IMPORT_PATTERNS:
                continue
            patterns = _IMPORT_PATTERNS[language]
            diff_text = change.diff or ""
            for pattern in patterns:
                for match in re.finditer(pattern, diff_text):
                    raw_import = match.group(1)
                    resolved = _resolve_import_path(raw_import, language)
                    if resolved and resolved not in changed_paths:
                        import_paths[resolved] = None

        if not import_paths:
            return {}

        result: dict[str, str] = {}
        for path in list(import_paths.keys())[:max_files]:
            try:
                content = await adapter.get_file_content(project_id, path, source_branch)
                if content:
                    if len(content) > max_file_size:
                        content = content[:max_file_size] + "\n... (已截断)"
                    result[path] = content
                    logger.debug("加载上下文文件: %s (%d 字符)", path, len(content))
            except Exception as e:
                logger.debug("跳过无法加载的文件 %s: %s", path, e)

        if result:
            logger.info("上下文增强: 加载了 %d 个相关文件", len(result))
        return result
