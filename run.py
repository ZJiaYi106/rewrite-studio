from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import config
from agent.graph import build_graph


def _initial_state(source: str, is_file: bool) -> dict:
    state = {
        "authorized": True,
        "status": "running",
        "errors": [],
        "image_failures": [],
        "needs_manual_image_review": False,
    }
    
    if is_file:
        state["document_path"] = source
        state["url"] = None
    else:
        state["url"] = source
        state["document_path"] = None
    
    return state


async def main() -> None:
    parser = argparse.ArgumentParser(description="处理经授权的微信公众号文章或文档")
    parser.add_argument("source", nargs="?", help="公众号文章 URL 或文档路径；不传则交互式输入")
    parser.add_argument("--file", "-f", action="store_true", help="将 source 作为文档路径处理")
    args = parser.parse_args()
    
    source = args.source
    is_file = args.file
    
    if not source:
        # 交互式输入
        mode = input("处理模式 [1=URL, 2=文档] (默认 1): ").strip() or "1"
        if mode == "2":
            is_file = True
            source = input("请输入文档路径：").strip()
        else:
            is_file = False
            source = input("请输入公众号文章链接：").strip()
    
    if not source:
        raise SystemExit("输入不能为空")
    
    # 如果是文件，验证文件存在
    if is_file:
        file_path = Path(source)
        if not file_path.exists():
            raise SystemExit(f"文件不存在: {source}")
        if file_path.suffix.lower() not in {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"}:
            raise SystemExit(f"不支持的文件格式: {file_path.suffix}")
        source = str(file_path.resolve())

    confirmation = input("请确认你拥有该内容版权或已获明确授权（输入 yes 继续）：").strip().lower()
    if confirmation != "yes":
        raise SystemExit("未确认授权，已取消处理。")

    config.ensure_directories()
    graph = build_graph()
    state = _initial_state(source, is_file)
    
    source_type = "文档" if is_file else "公众号文章"
    print(f"开始处理{source_type}……")
    
    final = dict(state)
    printed_errors: set[str] = set()
    async for event in graph.astream(state):
        for node_name, node_state in event.items():
            print(f"[{node_name}] 完成")
            final.update(node_state)
            for error in node_state.get("errors", []):
                if error not in printed_errors:
                    print(f"  警告：{error}")
                    printed_errors.add(error)

    if final.get("status") == "completed":
        print(f"\n成品已生成：{final['output_dir']}")
        print(f"文章文件：{final['final_path']}")
    else:
        print(f"\n处理失败：{final.get('parse_error') or '未知错误'}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
