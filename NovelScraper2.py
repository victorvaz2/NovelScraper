import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from ebooklib import epub
import time
import logging
import os

logging.basicConfig(level=logging.INFO)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

def clean_content(text):
    """Fix words with intentional dot-separated 'ass' sequences"""
    return re.sub(r'a\.s\.s', 'ass', text, flags=re.IGNORECASE)

def get_novel_info(first_chapter_url):
    response = requests.get(first_chapter_url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Get novel main URL from h1.tit link
    title_link = soup.find('h1', class_='tit').find('a')
    if not title_link:
        raise ValueError("Could not find novel title link")
    
    novel_title = title_link.get('title', 'Unknown Novel')
    novel_main_path = title_link['href']
    novel_main_url = urljoin(first_chapter_url, novel_main_path)
    
    # Get author and cover from novel's main page
    response_main = requests.get(novel_main_url, headers=headers)
    response_main.raise_for_status()
    soup_main = BeautifulSoup(response_main.content, 'html.parser')
    
    # Extract author
    author_link = soup_main.find('a', href=lambda href: href and '/author/' in href)
    author = author_link.text.strip() if author_link else "Unknown"
    
    # Extract cover image
    cover_div = soup_main.find('div', class_='pic')
    cover_url = None
    if cover_div:
        img = cover_div.find('img')
        if img and img.has_attr('src'):
            cover_path = img['src']
            cover_url = urljoin(novel_main_url, cover_path)
    
    return novel_title, author, cover_url

def scrape_chapters(start_url, max_chapters=None):
    chapters = []
    current_url = start_url
    
    while current_url and (max_chapters is None or len(chapters) < max_chapters):
        logging.info(f"Scraping {current_url}")
        try:
            response = requests.get(current_url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch {current_url}: {e}")
            break
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract chapter title
        chapter_title_tag = soup.find('span', class_='chapter')
        chapter_title = chapter_title_tag.text.strip() if chapter_title_tag else "Untitled"
        
        # Extract and clean content
        content_div = soup.find('div', id='article')
        paragraphs = content_div.find_all('p') if content_div else []
        cleaned_paragraphs = [clean_content(p.text.strip()) for p in paragraphs]
        content = '\n'.join(cleaned_paragraphs)
        
        chapters.append({'title': chapter_title, 'content': content})
        
        if max_chapters is not None and len(chapters) >= max_chapters:
            break
            
        # Find next chapter link
        next_link = soup.find('a', title="Read Next chapter")
        if next_link and next_link.has_attr('href'):
            current_url = urljoin(current_url, next_link['href'])
            time.sleep(1)
        else:
            current_url = None
    
    return chapters

def create_epub(novel_title, author, chapters, cover_url=None):
    book = epub.EpubBook()
    book.set_title(novel_title)
    book.add_author(author)
    
    # Add cover image
    if cover_url:
        try:
            logging.info(f"Downloading cover image from {cover_url}")
            response = requests.get(cover_url, headers=headers)
            response.raise_for_status()
            
            # Determine image type
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            if 'image/jpeg' in content_type:
                ext = 'jpg'
            elif 'image/png' in content_type:
                ext = 'png'
            else:
                ext = 'jpg'
            
            cover_filename = f'cover.{ext}'
            book.set_cover(cover_filename, response.content)
            
            # Create cover page
            cover_page = epub.EpubHtml(title='Cover', file_name='cover.xhtml')
            cover_page.content = f'<img src="{cover_filename}" alt="{novel_title} Cover"/>'
            book.add_item(cover_page)
        except Exception as e:
            logging.error(f"Failed to add cover image: {e}")

    # Create chapters
    epub_chapters = []
    for i, chapter in enumerate(chapters):
        chapter_content = f'<h1>{chapter["title"]}</h1><p>{chapter["content"].replace("\n", "</p><p>")}</p>'
        epub_chapter = epub.EpubHtml(
            title=chapter['title'],
            file_name=f'chapter_{i+1}.xhtml',
            lang='en'
        )
        epub_chapter.content = chapter_content
        book.add_item(epub_chapter)
        epub_chapters.append(epub_chapter)
    
    # Add navigation
    book.toc = tuple(epub_chapters)
    book.spine = ['nav'] + (['cover.xhtml'] if cover_url else []) + epub_chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Save EPUB
    filename = f'{novel_title.replace(" ", "_")}.epub'
    epub.write_epub(filename, book, {})
    return os.path.abspath(filename)

def main():
    first_chapter_url = input("Enter the first chapter URL: ").strip()
    num_input = input("Enter number of chapters to download (or 'all'): ").strip()
    
    max_chapters = None
    if num_input.lower() != 'all':
        try:
            max_chapters = max(1, int(num_input))
        except ValueError:
            logging.warning("Invalid input, downloading all available chapters")
            max_chapters = None
    
    try:
        novel_title, author, cover_url = get_novel_info(first_chapter_url)
        logging.info(f"Downloading: {novel_title} by {author}")
        if cover_url:
            logging.info(f"Found cover image at: {cover_url}")
        
        chapters = scrape_chapters(first_chapter_url, max_chapters)
        logging.info(f"Processed {len(chapters)} chapters")
        
        if chapters:
            filename = create_epub(novel_title, author, chapters, cover_url)
            logging.info(f"Successfully created EPUB: {filename}")
        else:
            logging.warning("No chapters found to convert")
            
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()