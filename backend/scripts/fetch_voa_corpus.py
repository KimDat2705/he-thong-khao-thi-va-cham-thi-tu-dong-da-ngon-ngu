import requests
from bs4 import BeautifulSoup
import json
import os
import re

# Các chuyên mục của VOA Learning English
CATEGORIES = [
    "https://learningenglish.voanews.com/z/3521", # As It Is
    "https://learningenglish.voanews.com/z/955",  # Education
    "https://learningenglish.voanews.com/z/986",  # Health & Lifestyle
]

def fetch_category_links(cat_url):
    print(f"Fetching category: {cat_url}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(cat_url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")
    
    links = []
    # Tìm các link bài viết có dạng /a/...html
    for a in soup.find_all("a", href=re.compile(r"^/a/.*?\.html$")):
        href = a.get("href")
        full_url = f"https://learningenglish.voanews.com{href}"
        if full_url not in links:
            links.append(full_url)
    return list(set(links))

def scrape_article(url):
    print(f"Scraping: {url}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None
        
    soup = BeautifulSoup(resp.content, "html.parser")
    
    # Title
    title_tag = soup.find("h1", class_="title")
    title = title_tag.text.strip() if title_tag else ""
    
    # Date
    date_tag = soup.find("time")
    pub_date = date_tag.get("datetime") if date_tag else ""
    
    # Text content (paragraphs)
    content_div = soup.find("div", id="article-content")
    paragraphs = []
    if content_div:
        for p in content_div.find_all("p"):
            text = p.text.strip()
            if text and not text.startswith("Words in This Story"):
                paragraphs.append(text)
    
    # Audio link
    audio_url = ""
    # Look for links that end with mp3 or contain audio
    audio_tag = soup.find("a", href=re.compile(r'\.mp3(\?.*)?$'))
    if audio_tag:
        audio_url = audio_tag["href"]
    else:
        # Check source tags inside audio element
        audio_src = soup.find("source", type="audio/mpeg")
        if audio_src and audio_src.has_attr("src"):
            audio_url = audio_src["src"]
        
    # Join text
    full_text = "\n\n".join(paragraphs)
    word_count = len(full_text.split())
    
    return {
        "url": url,
        "title": title,
        "published_date": pub_date,
        "audio_url": audio_url,
        "content": full_text,
        "word_count": word_count
    }

def main():
    all_articles = []
    
    for cat in CATEGORIES:
        try:
            links = fetch_category_links(cat)
            print(f"Found {len(links)} links in {cat}")
            # Take top 5 cho mỗi category
            for link in links[:5]:
                article = scrape_article(link)
                if article and article["word_count"] > 100:
                    all_articles.append(article)
        except Exception as e:
            print(f"Error processing category {cat}: {e}")
                
    output_path = os.path.join(os.path.dirname(__file__), "..", "app", "data", "factory_seeds", "voa_raw.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(all_articles)} articles to {output_path}")

if __name__ == "__main__":
    main()
