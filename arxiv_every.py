## arXiv 每日同步版日报生成器 --- 作者：朱柏铖 (author:Bocheng Zhu bochengzhu@outlook.com)
import arxiv
from openai import OpenAI
import pytz
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import time
import datetime
import random
# ==========================================
MY_API_KEY = "你的api密钥" 
MY_BASE_URL = "你的baseURL"
MY_MODEL = "你的模型@@"
client = OpenAI(api_key=MY_API_KEY, base_url=MY_BASE_URL)

def fetch_arxiv_papers():
    url = 'https://arxiv.org/list/astro-ph.GA/recent'
    headers = {
        # 伪装成浏览器
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=15)

    # 如果不是 200，说明被墙或者被反爬拦截了
    response.raise_for_status() 

    # 解析 HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    papers_ids = []
    h3_count = 0  # 记录遇到了几个 h3
    for element in soup.find_all(['h3', 'dt']):
        if element.name == 'h3':
            h3_count += 1
            if h3_count == 2:
                # 遇到第二个 h3，说明中间的文章已经抓完了，直接跳出循环
                break 
                
        # 当 h3_count 为 1 时，说明我们正处于两个 h3 之间
        elif element.name == 'dt' and h3_count == 1:
            a_tag = element.find('a', title='Abstract')
            if a_tag:
                # 提取并清理出纯净的 ID
                arxiv_id = a_tag.text.replace('arXiv:', '').strip()
                papers_ids.append(arxiv_id)
    
    search = arxiv.Search(id_list=papers_ids)
    client = arxiv.Client()
    results = list(client.results(search))
    details_dict = {}
    for paper in results:
        base_id = paper.entry_id.split('/abs/')[-1].split('v')[0]
        details_dict[base_id] = {
            "id": paper.entry_id,  
            "title": paper.title.replace('\n', ' '), # 去掉标题里烦人的换行
            "authors": ", ".join([author.name for author in paper.authors]), # 把作者列表拼成字符串
            "summary": paper.summary.replace('\n', ' '), # 去掉摘要里的换行
        }
    final_papers = []
    for pid in papers_ids:
        if pid in details_dict:
            final_papers.append(details_dict[pid])
    return final_papers

def generate_summary(papers):
    if not papers: return ""
    
    papers_content = "\n\n".join([
    f"[{i+1}] 标题：{p.get('title', '')}\n摘要：{p.get('summary', '')}" 
    for i, p in enumerate(papers)
    ])
    
    prompt = f"""
    你是一名资深天文学家。请阅读以下 {len(papers)} 篇论文的【标题与完整摘要】，撰写一段约 400-500字的“今日 arXiv 综述”。
    核心要求：
    1. 使用更加易懂的语言，因为阅读的都是大同行，太专业大家看不懂。
    2. 归纳热点聚类：不要按流水账列举。请将今日的干货提炼为2-4个核心研究热点，每个热点名称使用 <b> 加粗 </b>。
    3. 独立描述：不同工作内容请并列描述，**严禁为几篇不同的文章生硬捏造因果或递进逻辑链条**。
    4. 精准引证：在描述具体物理发现时，必须紧跟对应的论文编号，如“模拟结果显示黑洞动能反馈显著压制了冷气体吸积 [3, 15]”。
    5. 专业排版：纯 HTML 格式输出，最外层使用 <div style="background:#f0f7ff; padding:15px; border-radius:8px; line-height: 1.6; font-size: 15px; color: #333; margin-bottom: 20px;"> 包装。
    6. 符号规范：绝对不要使用 LaTeX 公式。请使用纯文本或 HTML 支持的常见天文写法（如 M_sun, z~10, Lambda-CDM）。语言必须地道，保留专业名词的英文原词（如 Outflow, Quenching, IMF等）。
    论文列表：
    {papers_content}
    """
    
    print("🧠 正在生成今日综述（导读）...")
    response = client.chat.completions.create(
        model=MY_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ================= 修改后的 generate_report 函数 =================
def generate_report(papers):
    if not papers: return "<p>今日暂无更新。</p>"
    
    # 第一步：生成导读摘要
    summary_html = generate_summary(papers)
    
    # 第二步：生成分类索引
    index_prompt = "请对以下论文进行【领域归类】，领域不用分的太细，分几个大类即可。只需返回 <h3>一、领域归类</h3> 和分类列表（HTML格式）。\n\n"
    index_prompt += "\n".join([f"[{i+1}] {p['title']}" for i, p in enumerate(papers)])
    
    print("🧠 正在生成索引部分...")
    index_html = client.chat.completions.create(
        model=MY_MODEL,
        messages=[{"role": "user", "content": index_prompt}]
    ).choices[0].message.content

    # 第三步：分批生成详情（降低步长至 5，确保不被截断）
    print(f"🧠 正在分段生成 {len(papers)} 篇论文详情...")
    details_html = "<h3>二、论文条目 (Details Section)</h3>"
    
    batch_size = 5 # ⬅️ 缩小步长，每组 5 篇最安全
    for i in range(0, len(papers), batch_size):
        batch = papers[i : i + batch_size]
        current_range = f"{i+1} 到 {min(i + batch_size, len(papers))}"
        print(f"   👉 正在处理第 {current_range} 篇...")
        
        batch_text = ""
        for j, p in enumerate(batch):
            batch_text += f"[{i+j+1}] Title: {p['title']}\nLink: {p['id']}\nAuthors: {p['authors']}\nAbstract: {p['summary']}\n\n"

        # 注意：这里的 prompt 修正了数量描述
        details_prompt = f"""
        你是一名专业的天文学家。请处理以下编号为 [{current_range}] 的 {len(batch)} 篇论文，按 HTML 格式输出：
        
        每篇格式：
        [编号] 中文标题
        链接：论文链接
        作者：[仅提取前十个作者，多余的使用(et al.)"]
        研究方法：[严格从 Observation / Simulation / Theory / Methods / Review 中选择 1-2 个]。
        核心问题：严格限制 1 句话，20 字以内，一针见血说明在问什么
        核心物理结果：使用易懂通俗的语言，表达短小精悍。严禁使用‘本文研究了...’这种废话。请直接描述物理发现，例如：‘发现星系旋转曲线在 R > 20kpc 处依然平坦，暗示暗物质晕比例高于预期。’，使用 2-3 句地道的中文学术表达。保留希腊字母(α, β, σ)和太阳符号(M☉)。语言必须地道，保留专业名词的英文原词（如 Outflow, Quenching, IMF等）。

        要求：
        - 只返回这 {len(batch)} 篇论文的内容。
        - 严禁 Markdown 符号（如 ##, **），必须使用纯 HTML 标签 (<h3>, <ul>, <li>, <p>, <strong>)。
        - 只返回 <body> 内部内容。

        待处理论文：
        {batch_text}
        """
        
        try:
            response = client.chat.completions.create(
                model=MY_MODEL,
                messages=[{"role": "user", "content": details_prompt}]
            )
            # 清理 AI 可能带出来的 markdown 代码块标识
            chunk = response.choices[0].message.content.replace('```html', '').replace('```', '')
            details_html += chunk
        except Exception as e:
            print(f"❌ 处理批次 {current_range} 时出错: {e}")

    return summary_html + index_html + details_html

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
        <h2 style="margin:0;">🌌 星系天文arxiv日报</h2>
        <p>{date_str} | 今日同步更新 {lenpapers} 篇</p>
    </div>
    {content.replace('```html', '').replace('```', '')}
</body>
</html>"""
    
    filename = f"GA_opus_Report_{date_str}.html"
    with open(filename, "w", encoding="utf-8-sig") as f:
        f.write(html_layout)
    print(f"✨ 同步版日报（索引+详情）已生成：{filename}")

if __name__ == "__main__":
    # 确保安装了 pytz: !pip install pytz
    data = fetch_arxiv_papers()
    report = generate_report(data)
    save_html(report,len(data))
