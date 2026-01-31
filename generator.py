import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import os
import sys
from jinja2 import Environment, FileSystemLoader

# --- Data Fetching Logic ---

def get_tdnet_url(date_str=None, page=1):
    if date_str is None:
        date_str = datetime.datetime.now().strftime('%Y%m%d')
    page_str = f"{page:03d}"
    url = f"https://www.release.tdnet.info/inbs/I_list_{page_str}_{date_str}.html"
    return url, date_str

def fetch_tdnet_data(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except Exception as e:
        return None

def parse_tdnet_html(html, base_url="https://www.release.tdnet.info/inbs/"):
    soup = BeautifulSoup(html, 'html.parser')
    data = []
    rows = soup.find_all('tr')
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 4:
            try:
                time_str = cells[0].get_text(strip=True)
                code_str = cells[1].get_text(strip=True)
                name_str = cells[2].get_text(strip=True)
                title_cell = cells[3]
                title_str = title_cell.get_text(strip=True)
                pdf_link = ""
                a_tag = title_cell.find('a')
                if a_tag and 'href' in a_tag.attrs:
                    link_href = a_tag['href']
                    pdf_link = (base_url + link_href) if not link_href.startswith('http') else link_href
                
                if ':' in time_str and len(time_str) <= 5:
                    data.append({
                        'time': time_str,
                        'code': code_str[:4],
                        'name': name_str,
                        'title': title_str,
                        'url': pdf_link
                    })
            except:
                continue
    return pd.DataFrame(data)

def get_all_tdnet_data(date_str=None):
    all_dfs = []
    for page in range(1, 11): # Check up to 10 pages
        url, _ = get_tdnet_url(date_str, page)
        html = fetch_tdnet_data(url)
        if not html: break
        df = parse_tdnet_html(html)
        if df.empty: break
        all_dfs.append(df)
    
    if not all_dfs: return pd.DataFrame()
    final_df = pd.concat(all_dfs, ignore_index=True)
    return final_df.drop_duplicates(subset=['time', 'code', 'title'])

def filter_data(df):
    if df.empty: return df
    # Filter out ETFs
    mask = df['name'].str.contains("ETF|ＥＴＦ|上場投信", na=False) | df['title'].str.contains("ETF|ＥＴＦ|上場投信", na=False)
    return df[~mask]

# --- HTML Generation ---

def generate_html(df, date_str):
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('template.html')
    
    items = df.to_dict('records')
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    html_content = template.render(
        items=items,
        date=date_str,
        update_time=now,
        count=len(items)
    )
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Successfully generated index.html for {date_str}")

def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    
    if target_date:
        print(f"Fetching IR data for {target_date}...")
        df = get_all_tdnet_data(target_date)
        df = filter_data(df)
        date_display = target_date
    else:
        # If no date specified, try today and look back up to 5 days if empty (for weekends/holidays)
        today = datetime.datetime.now()
        df = pd.DataFrame()
        date_display = ""
        
        for i in range(5):
            current_date = (today - datetime.timedelta(days=i)).strftime('%Y%m%d')
            print(f"Checking data for {current_date}...")
            df = get_all_tdnet_data(current_date)
            df = filter_data(df)
            if not df.empty:
                date_display = current_date
                break
    
    if not df.empty:
        generate_html(df, date_display)
    else:
        print("No data found in the last 5 days. Please specify a date: python generator.py YYYYMMDD")

if __name__ == "__main__":
    main()
