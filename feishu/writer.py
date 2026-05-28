#!/usr/bin/env python3
"""飞书文档写入模块 — 将 MCN 商单脚本自动化写入飞书文档。

使用方式：
    python feishu/writer.py                          # 从 output/ 目录读取最新脚本
    python feishu/writer.py --script output/final-script.md --storyboard output/storyboard.md --compliance output/compliance-report.md

前置条件：
    1. pip install requests
    2. 复制 feishu/config.example.json 为 feishu/config.json 并填入真实凭证
    3. 飞书应用已开通权限：docx:document, drive:drive
    4. 飞书应用已发布上线
"""

import argparse
import json
import os
import re
import sys
import requests

# === 配置加载 ===

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
BASE_URL = "https://open.feishu.cn/open-apis"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"[ERROR] 配置文件不存在: {CONFIG_PATH}")
        print("请复制 config.example.json 为 config.json 并填入真实凭证")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


# === 飞书 API 工具函数 ===

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        headers={"Content-Type": "application/json"},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def create_document(token: str, title: str = "MCN商单脚本") -> tuple:
    resp = requests.post(
        f"{BASE_URL}/docx/v1/documents",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"title": title},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"创建文档失败: {data}")
    doc = data["data"]["document"]
    doc_url = doc.get("url", f"https://xcnfvm8aee87.feishu.cn/docx/{doc['document_id']}")
    return doc["document_id"], doc_url


def get_document_root_block(token: str, doc_token: str) -> str:
    resp = requests.get(
        f"{BASE_URL}/docx/v1/documents/{doc_token}/blocks",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取文档结构失败: {data}")
    for item in data.get("data", {}).get("items", []):
        bt = item.get("block_type")
        if bt in (1, 2):
            return item["block_id"]
    items = data.get("data", {}).get("items", [])
    if items:
        return items[0]["block_id"]
    raise Exception(f"未找到文档根节点，返回数据: {data}")


def add_blocks(token: str, doc_token: str, parent_id: str, blocks: list) -> bool:
    """批量添加 blocks（自动分批，每批最多 50 个）"""
    batch_size = 50
    total = len(blocks)
    for i in range(0, total, batch_size):
        batch = blocks[i:i + batch_size]
        resp = requests.post(
            f"{BASE_URL}/docx/v1/documents/{doc_token}/blocks/{parent_id}/children",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"children": batch, "index": -1},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"写入第{i // batch_size + 1}批失败: {data}")
        print(f"  [{i + len(batch)}/{total}] blocks 已写入")
    return True


# === 飞书 Block 构造器 ===

def text_element(content: str, bold: bool = False) -> dict:
    el = {"text_run": {"content": content, "text_element_style": {}}}
    if bold:
        el["text_run"]["text_element_style"]["bold"] = True
    return el


def paragraph_block(elements: list) -> dict:
    return {"block_type": 2, "text": {"elements": elements, "style": {}}}


def heading_block(text: str, level: int = 1) -> dict:
    key = {1: "heading1", 2: "heading2", 3: "heading3"}[level]
    return {"block_type": 2 + level, key: {"elements": [text_element(text, True)], "style": {}}}


def separator_block() -> dict:
    return paragraph_block([text_element("─" * 50)])


# === Markdown → 飞书 Blocks 解析器 ===

def _parse_inline_elements(text: str) -> list:
    """解析行内 **bold** 标记，返回飞书 text_element 列表。"""
    elements = []
    parts = re.split(r"(\*\*.*?\*\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            elements.append(text_element(part[2:-2], bold=True))
        else:
            elements.append(text_element(part))
    return elements


def markdown_to_blocks(md_content: str) -> list:
    """将 Markdown 内容转换为飞书 document blocks。

    支持：
    - # / ## / ### 标题
    - **bold** 行内加粗
    - - / * 无序列表
    - 1. 有序列表
    - | 表格（转为段落展示）
    - > 引用（转为段落 + 前缀）
    - --- / *** 分隔线
    - 普通段落
    - 空行跳过
    """
    blocks = []
    lines = md_content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 跳过空行
        if not stripped:
            i += 1
            continue

        # 分隔线
        if re.match(r"^-{3,}$|^\*{3,}$|_{3,}$", stripped):
            blocks.append(separator_block())
            i += 1
            continue

        # 标题
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append(heading_block(heading_match.group(2).strip(), level))
            i += 1
            continue

        # 表格行：收集连续的表格行，转为段落
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                # 跳过分隔行 |---|---|
                if re.match(r"^\|[\s\-:|]+\|$", row):
                    i += 1
                    continue
                cells = [c.strip() for c in row.split("|")[1:-1]]
                table_lines.append(cells)
                i += 1
            # 转为段落
            for row_cells in table_lines:
                row_text = " | ".join(row_cells)
                blocks.append(paragraph_block(_parse_inline_elements(row_text)))
            continue

        # 无序列表
        if re.match(r"^[-*+]\s+", stripped):
            content = re.sub(r"^[-*+]\s+", "", stripped)
            blocks.append(paragraph_block([text_element("• "), *_parse_inline_elements(content)]))
            i += 1
            continue

        # 有序列表
        ordered_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if ordered_match:
            num = ordered_match.group(1)
            content = ordered_match.group(2)
            blocks.append(paragraph_block(
                [text_element(f"{num}. "), *_parse_inline_elements(content)]
            ))
            i += 1
            continue

        # 引用
        if stripped.startswith(">"):
            content = stripped.lstrip("> ").strip()
            blocks.append(paragraph_block(
                [text_element("▎", bold=True), text_element(f" {content}")]
            ))
            i += 1
            continue

        # 普通段落
        blocks.append(paragraph_block(_parse_inline_elements(stripped)))
        i += 1

    return blocks


# === 脚本内容解析 → 结构化 Blocks ===

def build_blocks_from_output(script_path: str, storyboard_path: str,
                              compliance_path: str) -> list:
    """从 output/ 目录读取脚本、分镜、合规报告，构建飞书 blocks。"""
    blocks = []

    with open(script_path, "r", encoding="utf-8") as f:
        script_md = f.read()

    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard_md = f.read()

    with open(compliance_path, "r", encoding="utf-8") as f:
        compliance_md = f.read()

    # ── 标题 ──
    title_match = re.search(r"#\s+(.+?)(?:\n|$)", script_md)
    doc_title = title_match.group(1) if title_match else "MCN 商单脚本"
    blocks.append(heading_block(doc_title, 1))

    # ── 视频元信息 ──
    meta_match = re.search(r"##\s*视频元信息\s*\n([\s\S]*?)(?=\n##|\Z)", script_md)
    if meta_match:
        meta_text = meta_match.group(1).strip()
        blocks.extend(markdown_to_blocks(meta_text))
    blocks.append(separator_block())

    # ── 脚本正文 ──
    blocks.append(heading_block("脚本正文", 2))

    # 提取脚本正文部分（从 ## 脚本正文 到 ## 分镜表 之前）
    script_body_match = re.search(
        r"##\s*脚本正文\s*\n([\s\S]*?)(?=\n##\s*分镜表|\n##\s*产品植入|\Z)",
        script_md,
    )
    if script_body_match:
        body = script_body_match.group(1).strip()
        blocks.extend(markdown_to_blocks(body))
    else:
        # fallback: 将整个脚本文件转为 blocks
        blocks.extend(markdown_to_blocks(script_md))

    blocks.append(separator_block())

    # ── 分镜表 ──
    blocks.append(heading_block("分镜表", 2))
    blocks.extend(markdown_to_blocks(storyboard_md))
    blocks.append(separator_block())

    # ── 合规质检报告 ──
    blocks.append(heading_block("合规质检报告", 2))
    blocks.extend(markdown_to_blocks(compliance_md))
    blocks.append(separator_block())

    # ── 使用说明 ──
    blocks.append(heading_block("使用说明", 2))
    notes = [
        "博主可根据实际拍摄条件调整分镜细节",
        "口播文案建议在录制前练习 1-2 遍，找到自然节奏",
        "产品露出位置已在分镜中标注，实际拍摄请注意光线和角度",
        "拍摄时需按照小红书平台规则标注商业合作关系",
    ]
    for idx, note in enumerate(notes, 1):
        blocks.append(paragraph_block([text_element(f"{idx}. {note}")]))

    return blocks


# === 主流程 ===

def main():
    parser = argparse.ArgumentParser(description="飞书文档写入工具")
    parser.add_argument("--script", default=None, help="脚本文件路径")
    parser.add_argument("--storyboard", default=None, help="分镜文件路径")
    parser.add_argument("--compliance", default=None, help="合规报告路径")
    args = parser.parse_args()

    # 默认路径
    output_dir = os.path.join(PROJECT_DIR, "output")
    script_path = args.script or os.path.join(output_dir, "final-script.md")
    storyboard_path = args.storyboard or os.path.join(output_dir, "storyboard.md")
    compliance_path = args.compliance or os.path.join(output_dir, "compliance-report.md")

    # 检查文件
    for path, name in [(script_path, "脚本"), (storyboard_path, "分镜"), (compliance_path, "合规报告")]:
        if not os.path.exists(path):
            print(f"[ERROR] {name}文件不存在: {path}")
            sys.exit(1)

    config = load_config()

    print("=" * 60)
    print("MCN 商单脚本 → 飞书文档写入工具")
    print(f"  脚本:   {script_path}")
    print(f"  分镜:   {storyboard_path}")
    print(f"  合规:   {compliance_path}")
    print("=" * 60)

    print("\n[1/4] 获取飞书 API 访问令牌...")
    token = get_tenant_access_token(config["app_id"], config["app_secret"])
    print("[OK] Token 获取成功")

    print("\n[2/4] 创建飞书文档...")
    # 从脚本提取标题
    with open(script_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    doc_title = re.sub(r"^#+\s*", "", first_line) if first_line.startswith("#") else "MCN 商单脚本"
    doc_token, doc_url = create_document(token, doc_title)
    print(f"[OK] 文档已创建: {doc_url}")

    print("\n[3/4] 构建文档内容...")
    blocks = build_blocks_from_output(script_path, storyboard_path, compliance_path)
    print(f"[OK] 共 {len(blocks)} 个 blocks")

    print("\n[4/4] 写入飞书文档...")
    root_id = get_document_root_block(token, doc_token)
    add_blocks(token, doc_token, root_id, blocks)

    print("\n" + "=" * 60)
    print(f"[DONE] 飞书文档链接: {doc_url}")
    print("=" * 60)

    return doc_url


if __name__ == "__main__":
    main()
