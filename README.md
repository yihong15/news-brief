# 每日简报（个人版）

## 部署（约20分钟）
1. 到 console.anthropic.com 创建 API Key（与 Claude 订阅分开计费，每月通常几美元）。
2. 在 GitHub 新建仓库，把本文件夹全部内容上传（仓库内没有任何密钥；私有仓库使用 Pages 需要付费计划，建议公开）。
3. 仓库 Settings → Pages → Source 选 **GitHub Actions**。
4. Settings → Secrets and variables → Actions：
   - Secrets：`ANTHROPIC_API_KEY`、`NTFY_TOPIC`（自己编一个**很长的随机字符串**，ntfy 的主题名等于密码）
   - 可选 Secrets：`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`
   - Variables：`SITE_URL` = `https://<你的用户名>.github.io/<仓库名>/`
5. iPhone：App Store 安装 **ntfy**，订阅同一个主题名；系统设置里允许通知。
6. Actions → brief → Run workflow：先选 `check` 看各媒体抓到多少条，再选 `noon` 试跑整套流程。
7. 用 Safari 打开 SITE_URL → 分享 → 添加到主屏幕。

## 说明
- 定时：马来西亚时间 11:30 和 17:30 开始运行，完成后推送；GitHub 的定时任务偶尔会延迟几分钟。
- 周三傍晚会额外生成国会周报；休会期间会提示。
- 来源与集团归属在 `config/sources.yml`，可随时增减。
- “至少N家独立来源”在 `src/run.py` 的 `MIN_OWNERS` 调整。
