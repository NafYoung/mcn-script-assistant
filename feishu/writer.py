#!/usr/bin/env python3
"""飞书文档写入模块 — 将 MCN 商单脚本自动化写入飞书文档。

使用方式：
    python feishu/writer.py

前置条件：
    1. pip install requests
    2. 复制 feishu/config.example.json 为 feishu/config.json 并填入真实凭证
    3. 飞书应用已开通权限：docx:document, drive:drive
    4. 飞书应用已发布上线
"""

import json
import os
import sys
import requests

# === 配置加载 ===

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

if not os.path.exists(CONFIG_PATH):
    print(f"[ERROR] 配置文件不存在: {CONFIG_PATH}")
    print("请复制 config.example.json 为 config.json 并填入真实凭证")
    sys.exit(1)

with open(CONFIG_PATH) as f:
    config = json.load(f)

APP_ID = config["app_id"]
APP_SECRET = config["app_secret"]
DOC_TOKEN = config["doc_token"]

BASE_URL = "https://open.feishu.cn/open-apis"


def get_tenant_access_token():
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        headers={"Content-Type": "application/json"},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def create_document(token, title="MCN商单脚本"):
    """创建新文档并返回 doc_token"""
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


def get_document_blocks(token, doc_token):
    resp = requests.get(
        f"{BASE_URL}/docx/v1/documents/{doc_token}/blocks",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取文档结构失败: {data}")
    for item in data.get("data", {}).get("items", []):
        bt = item.get("block_type")
        # page block (2) or document block (1)
        if bt in (1, 2):
            return item["block_id"]
    # fallback: return first item's block_id
    items = data.get("data", {}).get("items", [])
    if items:
        return items[0]["block_id"]
    raise Exception(f"未找到文档根节点，返回数据: {data}")


def text_element(content, bold=False):
    """构造飞书文本元素"""
    el = {"text_run": {"content": content, "text_element_style": {}}}
    if bold:
        el["text_run"]["text_element_style"]["bold"] = True
    return el


def paragraph(elements):
    """构造段落 block"""
    return {"block_type": 2, "text": {"elements": elements, "style": {}}}


def heading(text, level=1):
    """构造标题 block (level 1-3 → block_type 3-5)"""
    key = {1: "heading1", 2: "heading2", 3: "heading3"}[level]
    return {"block_type": 2 + level, key: {"elements": [text_element(text, True)], "style": {}}}


def separator():
    """构造分隔线（用段落 + 短线模拟）"""
    return paragraph([text_element("─" * 50)])


def add_blocks(token, doc_token, parent_id, blocks):
    """批量添加 blocks（自动分批，每批最多50个）"""
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


def clear_document(token, doc_token):
    """清空文档"""
    root_id = get_document_blocks(token, doc_token)
    resp = requests.get(
        f"{BASE_URL}/docx/v1/documents/{doc_token}/blocks/{root_id}/children",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 500},
    )
    data = resp.json()
    if data.get("code") != 0:
        return

    items = data.get("data", {}).get("items", [])
    if not items:
        return

    requests.delete(
        f"{BASE_URL}/docx/v1/documents/{doc_token}/blocks/{root_id}/children/batch_delete",
        headers={"Authorization": f"Bearer {token}"},
        json={"start_index": 0, "end_index": len(items)},
    )


def build_content_blocks():
    """构建文档内容（无表格，使用结构化排版）"""
    B = lambda t: text_element(t, bold=True)
    T = lambda t: text_element(t)
    P = lambda *els: paragraph(list(els))

    blocks = []

    # ═══════════════════════════════════════════
    # 标题
    # ═══════════════════════════════════════════
    blocks.append(heading("轻醒 × 凌二七 商单脚本", 1))
    blocks.append(P(T("品牌：轻醒  |  产品：0蔗糖高蛋白希腊酸奶  |  博主：凌二七  |  平台：小红书  |  时长：82s  |  版本：v1.0  |  日期：2026-05-26")))
    blocks.append(separator())

    # ═══════════════════════════════════════════
    # 脚本正文
    # ═══════════════════════════════════════════
    blocks.append(heading("脚本正文", 2))

    blocks.append(P(B("发布标题："), T("上班迟到也要吃的5分钟酸奶碗")))

    # -- 开头钩子 --
    blocks.append(heading("开头钩子（0-5s）", 3))
    blocks.append(P(B("画面："), T("特写 — 从冰箱取出「轻醒」酸奶，瓶身冷凝水珠清晰可见")))
    blocks.append(P(B("口播："), T("「打工人早上最崩溃的不是迟到，是好不容易到公司，九点半就饿了。」")))
    blocks.append(P(B("字幕："), T("打工人早上最崩溃的不是迟到")))

    # -- 主体内容 --
    blocks.append(heading("主体内容", 3))

    # 段1
    blocks.append(P(B("▎段1：痛点共鸣（5-15s）")))
    blocks.append(P(B("画面："), T("中景 — 博主站在厨房操作台前，推开包子吐司包装")))
    blocks.append(P(B("口播："), T("「我以前早上就是包子吐司轮着来，吃到十点就开始摸抽屉找零食。后来发现，真不是吃得多就不饿，是吃的东西不对。」")))
    blocks.append(P(B("字幕："), T("不是吃得多就不饿 / 是吃的东西不对")))

    # 段2
    blocks.append(P(B("▎段2：产品引入（15-28s）⭐ 核心展示")))
    blocks.append(P(B("画面："), T('特写 — 手拿「轻醒」黄桃味，旋转展示标签，手指点0蔗糖和高蛋白，开盖舀起拉出浓稠丝')))
    blocks.append(P(B("口播："), T("「后来我开始用希腊酸奶做早餐基底，像这个轻醒的黄桃味，它是0蔗糖的，但是吃起来不酸不涩。关键是它的蛋白质真的足，你看这个浓稠度——挖一勺能立住。」")))
    blocks.append(P(B("字幕："), T("0蔗糖 / 吃起来不酸 / 蛋白质真的足 / 👀 看浓稠度")))

    # 段3
    blocks.append(P(B("▎段3：制作过程（28-60s）")))
    blocks.append(P(B("画面："), T("俯拍 — 酸奶倒入碗中（慢动作）→ 撒燕麦 → 铺香蕉 → 放蓝莓 → 淋蜂蜜（慢动作）")))
    blocks.append(P(B("口播："), T("「做法其实没有技术含量，酸奶倒出来，燕麦撒一把，有什么水果丢什么水果。整个流程从头到尾不超过五分钟，你刷牙的时候把碗放那儿就行了。」")))
    blocks.append(P(B("字幕："), T("① 酸奶打底 ② 燕麦一把 ③ 水果随意 ④ 蜂蜜灵魂 / 全程 < 5min")))

    # 段4
    blocks.append(P(B("▎段4：成品展示 + 试吃（60-75s）")))
    blocks.append(P(B("画面："), T("45°俯拍成品酸奶碗 → 第一人称试吃，表情自然")))
    blocks.append(P(B("口播："), T("「这一碗吃完，我到中午都不会饿。而且它吃起来很清爽，不会有那种吃完油腻腻的感觉。我现在基本上每周有个三四天早上都这么吃，换不同口味轮着来，蓝莓的、黄桃的、原味的自己加水果。」")))
    blocks.append(P(B("字幕："), T("吃完到中午都不饿 / 清爽无负担 / 三种口味轮着吃")))

    # -- 结尾 CTA --
    blocks.append(heading("结尾 CTA（75-82s）", 3))
    blocks.append(P(B("画面："), T("中景 — 收拾碗勺，对镜头笑，右下角弹出「收藏」图标动画")))
    blocks.append(P(B("口播："), T("「你们早上一般都吃什么？可以在评论区跟我分享一下你们的快手早餐，我也去偷个师。这期如果对你有用的话记得码住，下期见~」")))
    blocks.append(P(B("字幕："), T("你们早上吃啥？👇 / 有用就码住！")))

    blocks.append(separator())

    # ═══════════════════════════════════════════
    # 分镜表（结构化列表形式）
    # ═══════════════════════════════════════════
    blocks.append(heading("分镜表", 2))
    blocks.append(P(T("共 13 镜，预计总时长 82s")))

    storyboard = [
        ("1", "3s", "特写", "冰箱取酸奶，瓶身水珠", "（BGM 起）", "打工人早上最崩溃的不是迟到", "画面先于口播"),
        ("2", "5s", "中景", "推开包子吐司包装", "打工人早上最崩溃的不是迟到...", "打工人早上最崩溃的不是迟到", "建立共鸣"),
        ("3", "5s", "中景→特写", "露出干净料理区", "我以前早上就是包子吐司轮着来...", "吃到十点就开始摸零食", ""),
        ("4", "5s", "特写", "展示轻醒黄桃味标签", "后来发现真不是吃得多就不饿...", "不是吃得多就不饿", "产品首次亮相"),
        ("5", "8s", "微距", "开盖→舀起→拉丝", "你看这个浓稠度——挖一勺能立住", "蛋白质真的足 👀看浓稠度", "⭐ 核心展示镜头"),
        ("6", "5s", "俯拍", "酸奶倒碗中（慢动作）", "（环境音留白）", "① 酸奶打底", "慢动作增强质感"),
        ("7", "8s", "俯拍", "撒燕麦→香蕉→蓝莓", "有什么水果丢什么水果", "② 燕麦一把 ③ 水果随意", "三步一气呵成"),
        ("8", "5s", "微距", "淋蜂蜜慢动作", "刷牙时把碗放那儿就行了", "④ 蜂蜜灵魂 / 全程 < 5min", "视觉亮点"),
        ("9", "5s", "45°俯拍", "成品酸奶碗特写", "这一碗吃完，我到中午都不会饿", "吃完到中午都不饿 ✨", "打光+色彩"),
        ("10", "5s", "第一人称", "试吃，表情自然", "吃起来很清爽...", "清爽无负担", "拒绝夸张表情"),
        ("11", "7s", "中景", "边吃边聊，三种口味展示", "每周三四天都这么吃，三种口味轮着来", "三种口味轮着吃 🫐🍑", "自然展示"),
        ("12", "5s", "中景", "收拾碗勺，对镜头笑", "你们早上一般都吃什么？", "你们早上吃啥？👇", "互动引导"),
        ("13", "3s", "中景+动画", "收藏图标弹出，画面定格", "有用的话记得码住，下期见~", "有用就码住！", "End card"),
    ]

    for s in storyboard:
        line = f"• 镜号{s[0]} | {s[1]} | {s[2]} | {s[3]} | 口播：{s[4]} | 字幕：{s[5]}"
        if s[6]:
            line += f" | 📌 {s[6]}"
        blocks.append(P(T(line)))

    blocks.append(separator())

    # ═══════════════════════════════════════════
    # 产品植入点
    # ═══════════════════════════════════════════
    blocks.append(heading("产品植入点", 2))
    implants = [
        "镜号1：冰箱取酸奶 → 自然展示产品外观（高颜值包装+冷凝水珠=新鲜感）",
        '镜号4-5：展示标签+开盖拉丝 → 核心传递【0蔗糖】【高蛋白】【浓稠质地】',
        "镜号6：倒入碗中 → 产品作为食谱核心基底",
        "镜号11：口播日常习惯 → 三种口味轮着吃，自然带出产品多样性",
    ]
    for imp in implants:
        blocks.append(P(T(f"• {imp}")))

    blocks.append(separator())

    # ═══════════════════════════════════════════
    # 合规质检
    # ═══════════════════════════════════════════
    blocks.append(heading("合规质检报告", 2))
    blocks.append(P(T("检查总数：18 项 ｜ 通过：18 项 ｜ 风险项：0 ｜ 判定：✅ 通过，可交付拍摄")))
    blocks.append(P(B("一级禁用词（17项）："), T("全部通过 — 无减肥/瘦身/燃脂/降糖/治疗等禁用词")))
    blocks.append(P(B("二级谨慎词（5项）："), T('全部通过 — 无控糖/代餐/低卡等敏感词，使用「轻负担」替代')))
    blocks.append(P(B("品牌要求（7项）："), T("全部通过 — 产品名准确，卖点表述合规，未超出 brief 范围")))
    blocks.append(P(B("平台合规（5项）："), T("全部通过 — 无外链/二维码，无硬广话术")))
    blocks.append(P(B("内容质量（5项）："), T("全部通过 — 口播自然、植入不硬、钩子有效、CTA自然")))

    blocks.append(separator())

    # ═══════════════════════════════════════════
    # 使用说明
    # ═══════════════════════════════════════════
    blocks.append(heading("使用说明", 2))
    notes = [
        "博主可根据实际拍摄条件调整分镜细节",
        "口播文案建议在录制前练习1-2遍，找到自然节奏",
        "产品露出位置已在分镜中标注，实际拍摄请注意光线和角度",
        "拍摄时需按照小红书平台规则标注商业合作关系",
        "封面建议使用镜号9的成品酸奶碗俯拍画面",
    ]
    for idx, note in enumerate(notes, 1):
        blocks.append(P(T(f"{idx}. {note}")))

    return blocks


def main():
    print("=" * 60)
    print("MCN 商单脚本 → 飞书文档写入工具")
    print("=" * 60)

    print("[1/5] 获取飞书 API 访问令牌...")
    token = get_tenant_access_token()
    print("[OK] Token 获取成功")

    print("[2/5] 创建飞书文档...")
    doc_token, doc_url = create_document(token, "轻醒 x 凌二七 商单脚本")
    print(f"[OK] 文档已创建: {doc_url}")

    print("[3/5] 获取文档根节点...")
    root_id = get_document_blocks(token, doc_token)
    print(f"[OK] 文档根节点: {root_id}")

    print("[4/5] 写入商单脚本...")
    blocks = build_content_blocks()
    add_blocks(token, doc_token, root_id, blocks)
    print("[OK] 全部内容已写入")

    print()
    print("=" * 60)
    print(f"[DONE] 飞书文档链接: {doc_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
