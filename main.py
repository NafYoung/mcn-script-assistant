#!/usr/bin/env python3
"""MCN 商单脚本生成助手 — 5 步 Agent Pipeline 编排脚本。

使用方式：
    python main.py --brief brief.md --blogger references/blogger-profiles.md
    python main.py --brief brief.md --blogger references/blogger-profiles.md --api-key sk-xxx

依赖：
    pip install requests
"""

import argparse
import json
import os
import re
import sys
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── LLM 调用 ──────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_message: str, api_key: str, base_url: str, model: str) -> str:
    """调用 OpenAI 兼容 API（DeepSeek / 其他）"""
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ── Prompt 加载 ────────────────────────────────────────────────────────

def extract_system_prompt(file_path: str) -> str:
    """从 prompt markdown 文件中提取 System Prompt 内容。

    文件格式示例：
        # Step 1: Brief 拆解 Agent
        ## 功能
        ...
        ## System Prompt
        ```
        你是一位资深的...
        ```
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 定位 System Prompt section 中的代码块
    match = re.search(
        r"##\s*System\s*Prompt\s*\n+```(?:\w*\n)?(.*?)```",
        content,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    # fallback: 使用整个文件内容
    return content.strip()


# ── Pipeline 步骤 ─────────────────────────────────────────────────────

def run_pipeline(brief_path: str, blogger_path: str, api_key: str,
                 base_url: str, model: str) -> dict:
    """执行 5 步 pipeline，返回各步骤输出。"""

    output_dir = os.path.join(SCRIPT_DIR, "output")
    prompts_dir = os.path.join(SCRIPT_DIR, "prompts")
    os.makedirs(output_dir, exist_ok=True)

    # 读取输入文件
    with open(brief_path, "r", encoding="utf-8") as f:
        brief_text = f.read()
    with open(blogger_path, "r", encoding="utf-8") as f:
        blogger_text = f.read()

    results = {}

    # ── Step 1: Brief 拆解 ─────────────────────────────────────────
    print("\n[Step 1/5] Brief 拆解...")
    sys1 = extract_system_prompt(os.path.join(prompts_dir, "01-brief-deconstruct.md"))
    results["brief_analysis"] = call_llm(sys1, brief_text, api_key, base_url, model)
    with open(os.path.join(output_dir, "01-brief-analysis.md"), "w", encoding="utf-8") as f:
        f.write(results["brief_analysis"])
    print(f"  ✓ 输出 {len(results['brief_analysis'])} 字 → output/01-brief-analysis.md")

    # ── Step 2: 风格分析 ───────────────────────────────────────────
    print("\n[Step 2/5] 内容风格分析...")
    sys2 = extract_system_prompt(os.path.join(prompts_dir, "02-style-analysis.md"))
    user2 = (
        f"以下是博主调研资料：\n\n{blogger_text}\n\n"
        f"以下是创作简报（供参考，帮助你判断博主与品牌的匹配度）：\n\n{results['brief_analysis']}"
    )
    results["style_fingerprint"] = call_llm(sys2, user2, api_key, base_url, model)
    with open(os.path.join(output_dir, "02-style-fingerprint.md"), "w", encoding="utf-8") as f:
        f.write(results["style_fingerprint"])
    print(f"  ✓ 输出 {len(results['style_fingerprint'])} 字 → output/02-style-fingerprint.md")

    # ── Step 3: 脚本生成 ───────────────────────────────────────────
    print("\n[Step 3/5] 脚本 + 分镜生成...")
    sys3 = extract_system_prompt(os.path.join(prompts_dir, "03-script-generate.md"))
    user3 = (
        f"## 创作简报\n\n{results['brief_analysis']}\n\n"
        f"## 博主风格指纹\n\n{results['style_fingerprint']}\n\n"
        f"## 目标时长\n90-120 秒"
    )
    results["script"] = call_llm(sys3, user3, api_key, base_url, model)
    with open(os.path.join(output_dir, "final-script.md"), "w", encoding="utf-8") as f:
        f.write(results["script"])
    print(f"  ✓ 输出 {len(results['script'])} 字 → output/final-script.md")

    # ── Step 4: 合规质检 ───────────────────────────────────────────
    print("\n[Step 4/5] 风险质检...")
    sys4 = extract_system_prompt(os.path.join(prompts_dir, "04-compliance-check.md"))
    user4 = (
        f"## 待检脚本\n\n{results['script']}\n\n"
        f"## 合规红线清单\n\n{results['brief_analysis']}"
    )
    results["compliance"] = call_llm(sys4, user4, api_key, base_url, model)
    with open(os.path.join(output_dir, "compliance-report.md"), "w", encoding="utf-8") as f:
        f.write(results["compliance"])
    print(f"  ✓ 输出 {len(results['compliance'])} 字 → output/compliance-report.md")

    # ── Step 5: 飞书文档写入 ───────────────────────────────────────
    print("\n[Step 5/5] 写入飞书文档...")
    feishu_config = os.path.join(SCRIPT_DIR, "feishu", "config.json")
    if not os.path.exists(feishu_config):
        print("  ⚠ 飞书配置文件不存在，跳过自动写入。")
        print(f"  请复制 feishu/config.example.json → feishu/config.json 并填入凭证后手动运行：")
        print(f"    python feishu/writer.py")
    else:
        # 直接调用 writer.py 的 main 函数
        sys.path.insert(0, os.path.join(SCRIPT_DIR, "feishu"))
        from writer import main as feishu_main
        feishu_main()

    return results


# ── CLI 入口 ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MCN 商单脚本生成助手 — 5 步 Agent Pipeline"
    )
    parser.add_argument("--brief", required=True, help="客户 Brief 文件路径")
    parser.add_argument("--blogger", required=True, help="博主调研资料文件路径")
    parser.add_argument("--api-key", default=None, help="LLM API Key（或设置 DEEPSEEK_API_KEY 环境变量）")
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1", help="API Base URL")
    parser.add_argument("--model", default="deepseek-chat", help="模型名称")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误：请通过 --api-key 或 DEEPSEEK_API_KEY 环境变量提供 API Key")
        sys.exit(1)

    if not os.path.exists(args.brief):
        print(f"错误：Brief 文件不存在: {args.brief}")
        sys.exit(1)

    print("=" * 60)
    print("MCN 商单脚本生成助手 — 5 步 Agent Pipeline")
    print(f"  Brief:  {args.brief}")
    print(f"  博主:   {args.blogger}")
    print(f"  模型:   {args.model}")
    print(f"  API:    {args.base_url}")
    print("=" * 60)

    results = run_pipeline(args.brief, args.blogger, api_key, args.base_url, args.model)

    print("\n" + "=" * 60)
    print("Pipeline 完成！输出文件：")
    print("  output/01-brief-analysis.md   — Brief 拆解")
    print("  output/02-style-fingerprint.md — 风格指纹")
    print("  output/final-script.md        — 最终脚本 + 分镜")
    print("  output/compliance-report.md   — 合规质检报告")
    print("=" * 60)


if __name__ == "__main__":
    main()
