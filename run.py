from __future__ import annotations

import argparse
import asyncio

import config
from agent.graph import build_graph


def _initial_state(url: str) -> dict:
    return {
        "url": url,
        "authorized": True,
        "status": "running",
        "errors": [],
        "image_failures": [],
        "needs_manual_image_review": False,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="处理经授权的微信公众号文章")
    parser.add_argument("url", nargs="?", help="公众号文章 URL；不传则交互式输入")
    args = parser.parse_args()
    url = (args.url or input("请输入公众号文章链接：")).strip()
    if not url:
        raise SystemExit("URL 不能为空")

    confirmation = input("请确认你拥有该内容版权或已获明确授权（输入 yes 继续）：").strip().lower()
    if confirmation != "yes":
        raise SystemExit("未确认授权，已取消处理。")

    config.ensure_directories()
    graph = build_graph()
    state = _initial_state(url)
    print("开始处理……")
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
