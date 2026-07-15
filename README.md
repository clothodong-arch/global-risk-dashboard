# 全球风险仪表盘

一个无需后端服务器的每日宏观风险网页。GitHub Actions 在每个美股交易日收盘后抓取市场与 FRED 数据，计算综合风险分数，生成中文规则化分析，并把结果写入 `data/dashboard.json`。

## 覆盖指标

- 利率：美国 10Y、30Y
- 波动率：VIX、MOVE
- 信用：美国高收益债利差、HYG
- 美元与套息：DXY、USD/JPY
- 流动性：银行准备金、逆回购、TGA、NFCI
- 全球股票：标普、纳指、日经、KOSPI、台湾加权、恒生

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/update_data.py
python -m http.server 8000
```

打开 `http://localhost:8000`。

## 部署到 GitHub Pages

1. 新建 GitHub 仓库并上传全部文件。
2. Repository Settings → Pages。
3. Source 选择 `Deploy from a branch`。
4. Branch 选择 `main`，目录选择 `/ (root)`。
5. 在 Actions 页面手动运行一次 `Update dashboard data`。

定时任务使用 UTC：`23:15 UTC` 对应珀斯次日 `07:15`。GitHub 的 scheduled workflow 可能延迟几分钟，因此不适合分钟级交易信号。

## 数据说明

- Yahoo Finance 由 `yfinance` 抓取，个别代码可能因上游调整而暂时缺失。
- FRED 使用公开 CSV 下载接口。
- 页面会自动忽略缺失指标，不会因单一数据源失败而完全中断。
- 风险分数是监控工具，不是回测后的交易模型，也不构成投资建议。
