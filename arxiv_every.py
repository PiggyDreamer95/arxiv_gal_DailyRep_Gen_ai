## arXiv 每日同步版日报生成器 --- 作者：朱柏铖 (author:Bocheng Zhu bochengzhu@outlook.com)
import arxiv
import datetime
from openai import OpenAI
from datetime import timedelta
import pytz
# ==========================================
MY_API_KEY = "API~"
MY_BASE_URL = "URL BASE～"
MY_MODEL = "模型～"
client = OpenAI(api_key=MY_API_KEY, base_url=MY_BASE_URL)
# ==========================================
def get_arxiv_sync_window():
    """精确计算 arXiv 今日公布批次的提交时间窗口"""
    tz_et = pytz.timezone('US/Eastern')
    now_et = datetime.datetime.now(tz_et)
    
    # arXiv 更新规则：周四的 New 列表来自周三 14:00 前的 24 小时提交
    # 周一的 New 列表来自上周五 14:00 前的提交
    weekday = now_et.weekday() 
    if weekday == 0: # Monday
        days_back = 3
    elif weekday in [5, 6]: # Weekend
        days_back = 0
    else:
        days_back = 1
        
    # 窗口结束点：昨天 14:00 ET
    end_time = now_et.replace(hour=14, minute=0, second=0, microsecond=0) - timedelta(days=1)
    # 窗口起始点：再往前推 24h (或周一对应的 72h)
    start_time = end_time - timedelta(days=days_back)
    
    return start_time, end_time

def fetch_arxiv_papers():
    start_t, end_t = get_arxiv_sync_window()
    print(f"🔍 正在同步 arXiv 公告批次 (提交时间窗口: {start_t.strftime('%m-%d %H:%M')} -> {end_t.strftime('%m-%d %H:%M')} ET)")

    arxiv_client = arxiv.Client()
    search = arxiv.Search(query="cat:astro-ph.ga", max_results=60, sort_by=arxiv.SortCriterion.SubmittedDate)
    
    papers = []
    for r in arxiv_client.results(search):
        pub_et = r.published.astimezone(pytz.timezone('US/Eastern'))
        if start_t <= pub_et < end_t:
            papers.append({
                "title": r.title,
                "authors": ", ".join([a.name for a in r.authors]),
                "summary": r.summary,
                "url": r.entry_id
            })
    
    print(f"✅ 同步成功！抓取到 {len(papers)} 篇论文（应与官网 New 列表数量一致）。")
    return papers

def generate_report(papers):
    if not papers: return "<p>今日暂无更新。</p>"
    
    input_text = ""
    for i, p in enumerate(papers):
        input_text += f"[{i+1}] Title: {p['title']}\nAuthors: {p['authors']}\nAbstract: {p['summary']}\n\n"

    prompt = f"""
    你是一名专业的天文学公众号主编且资深天文学家。请处理以下 {len(papers)} 篇论文，严格按以下格式输出 HTML：

    一、领域归类 (Index Section)
    按领域（如：引力与动力学、星团、星系演化、AGN等）分类，在每个类别后列出对应的论文编号。
    格式示例：领域名称：[1], [5], [12]

    二、论文条目 (Details Section)
    按编号顺序排列所有 {len(papers)} 篇论文。
    每篇格式：
    [编号] 中文标题
    作者：姓名全称（若有天文模拟、观测、理论、方法等领域的著名学者，请用 <strong style="color:#d35400;">姓名 ★(Famous Scholar)</strong>）
    研究方法：[需判定为 Observation / Simulation / Theory / Methods 之一]。判定标准：若文章核心是发布新数据或巡天样本，请标为 [Observation]；若核心是算法改进或软件评测，请标为 [Methods]。
    核心物理结果：严禁使用‘本文研究了...’这种废话。请直接描述物理发现，例如：‘发现星系旋转曲线在 R > 20kpc 处依然平坦，暗示暗物质晕比例高于预期。’，使用 2-3 句地道的中文学术表达。保留希腊字母(α, β, σ)和太阳符号(M☉)。

    要求：
    - 严禁 Markdown 符号（如 ##, **），必须使用纯 HTML 标签 (<h3>, <ul>, <li>, <p>, <strong>)。
    - 只返回 <body> 内部内容。

    待处理论文：
    {input_text}
    """

    print("🧠 Claude 正在按照“索引+详情”模式进行排版...")
    try:
        response = client.chat.completions.create(
            model=MY_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {e}"

def save_html(content, lenpapers):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    html_layout = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: auto; padding: 20px; }}
        .header {{ background: #004085; color: white; padding: 20px; border-radius: 10px; text-align: center; }}
        .index-box {{ background: #f8f9fa; border: 1px solid #dee2e6; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .paper-item {{ border-bottom: 1px solid #eee; padding: 15px 0; }}
        .method-tag {{ color: #28a745; font-weight: bold; font-size: 0.9em; }}
        h3 {{ color: #004085; border-left: 5px solid #004085; padding-left: 10px; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0;">🌌 星系物理与动力学日报</h2>
        <p>{date_str} | 今日同步更新 {lenpapers} 篇</p>
    </div>
    {content.replace('```html', '').replace('```', '')}
</body>
</html>"""
    
    filename = f"GA_Sync_Report_{date_str}.html"
    with open(filename, "w", encoding="utf-8-sig") as f:
        f.write(html_layout)
    print(f"✨ 同步版日报（索引+详情）已生成：{filename}")

if __name__ == "__main__":
    # 确保安装了 pytz: !pip install pytz
    data = fetch_arxiv_papers()
    report = generate_report(data)
    save_html(report,len(data))