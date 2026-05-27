# MCN Script Assistant

MCN 商单脚本生成助手 — 从品牌 brief 到飞书文档的 AI 全流程自动化。

**适用场景**：品牌方/ MCN 机构为小红书达人制作商单脚本，确保内容自然种草、合规安全、高效交付。

---

## 项目结构

```
/
├── README.md                               # 本文件
├── report.md                               # 调研与方案报告
├── prompts/                                # AI Agent Prompt
│   ├── 01-brief-deconstruct.md             # Step 1: Brief 拆解
│   ├── 02-style-analysis.md                # Step 2: 内容风格分析
│   ├── 03-script-generate.md               # Step 3: 脚本生成
│   ├── 04-compliance-check.md              # Step 4: 风险质检
│   └── 05-feishu-write.md                  # Step 5: 飞书文档写入
├── references/                             # 小红书调研资料
│   ├── blogger-profiles.md                 # 博主调研档案
│   └── content-breakdown.md                # 内容风格拆解
├── skills/mcn-script-assistant/
│   └── SKILL.md                            # 可复用 Skill
├── feishu/                                 # 飞书接入
│   ├── writer.py                           # 自动化写入脚本
│   ├── config.json                         # API 凭证（不提交）
│   └── config.example.json                 # 配置模板
└── output/                                 # 最终交付物
    ├── final-script.md                     # 完整脚本
    ├── storyboard.md                       # 分镜表
    └── compliance-report.md                # 合规质检报告
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 配置飞书凭证

1. 前往 [飞书开放平台](https://open.feishu.cn) 创建企业自建应用
2. 开通权限：`docx:document`、`drive:drive`
3. 发布应用上线
4. 复制 `feishu/config.example.json` 为 `feishu/config.json`，填入真实凭证：

```json
{
  "app_id": "cli_xxxxxxxxxxxxxxx",
  "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "doc_token": "文档Token（可选，writer.py 会自动创建新文档）"
}
```

### 3. 运行飞书文档写入

```bash
python feishu/writer.py
```

控制台会输出创建的飞书文档链接。

### 4. 运行完整 AI 工作流（待实现）

5 步 Agent Pipeline 的 Prompt 设计已全部完成（见 `prompts/` 目录），可直接将对应 System Prompt 粘贴至任意 LLM 工具（Claude、DeepSeek、ChatGPT 等）中执行。完整自动化编排脚本（main.py + DeepSeek API 链式调用）见后续迭代计划。

---

## 工作流说明

本项目设计了一个 5 步 AI Agent Pipeline：

| 步骤 | 功能 | 输入 | 输出 |
|------|------|------|------|
| Step 1 | Brief 拆解 | 客户原始 brief | 结构化创作简报 + 合规红线清单 |
| Step 2 | 风格分析 | 博主内容样本 | 风格指纹（钩子/节奏/镜头/口播） |
| Step 3 | 脚本生成 | 创作简报 + 风格指纹 | 完整脚本 + 分镜表 |
| Step 4 | 风险质检 | 脚本 + 合规清单 | 质检报告（通过/不通过） |
| Step 5 | 飞书写入 | 脚本 + 分镜 + 质检报告 | 飞书文档链接 |

每个步骤的详细 Prompt 见 `prompts/` 目录。

---

## 飞书文档接入

### 自动化方式

`feishu/writer.py` 通过飞书开放平台 API 实现：
1. 使用 App ID + App Secret 获取 tenant_access_token
2. 调用 `POST /open-apis/docx/v1/documents` 创建文档
3. 分批写入内容 blocks（heading / paragraph / 分隔线）
4. 输出文档链接

### 最终飞书文档

**链接**：https://xcnfvm8aee87.feishu.cn/docx/IfHKdZHOWo1jOKxwQh3cv1ZbnZf

该文档由 `writer.py` 自动化创建并写入，非手动复制粘贴。

---

## 测试案例：轻醒 × 凌二七

本项目以虚拟品牌「轻醒」0蔗糖高蛋白希腊酸奶为例，完成了完整的博主调研与脚本生成：

- **品牌**：轻醒（轻食酸奶）
- **产品**：0蔗糖高蛋白希腊酸奶（原味/蓝莓/黄桃）
- **博主**：凌二七（干净饮食食谱博主，2.1万粉丝）
- **平台**：小红书短视频
- **脚本时长**：~95s / 16镜
- **版本**：v2.0（基于博主真实逐字稿校准）
- **合规结果**：18/18 项检查全部通过

---

## 使用工具

- **AI 模型**：Claude Code（调研/脚本生成/飞书集成）+ Prompt 设计兼容 DeepSeek/其他 LLM
- **飞书 API**：文档自动创建与写入
- **调研工具**：小红书 App + 录屏 ASR 转写（一手信源）+ 新榜交叉验证
- **脚本语言**：Python 3

---

## License

本项目为求职面试测试题交付物，仅供评估使用。
