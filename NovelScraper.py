from bs4 import BeautifulSoup
from shutil import copyfile
from xml.etree import ElementTree as ET
import requests
import os
from datetime import datetime
import re
from zipfile import ZipFile, ZIP_STORED
from pathlib import Path

class Settings:
    FileName = ''
    RootPath = Path('./')
    EpubRootPath = Path()
    MetaPath = Path()
    OEBPSPath = Path()
    ContentPath = Path()
    StylePath = Path()
    FontsPath = Path()

    @classmethod
    def set_paths(cls):
        cls.EpubRootPath = cls.RootPath / cls.FileName
        cls.MetaPath = cls.EpubRootPath / 'META-INF'
        cls.OEBPSPath = cls.EpubRootPath / 'OEBPS'
        cls.ContentPath = cls.OEBPSPath / 'Content'
        cls.StylePath = cls.OEBPSPath / 'Style'
        cls.FontsPath = cls.OEBPSPath / 'Fonts'

    @classmethod
    def prepare_epub(cls):
        container_xml = '''<?xml version="1.0"?>
        <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
            <rootfiles>
                <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
            </rootfiles>
        </container>'''
        
        directories = [cls.EpubRootPath, cls.MetaPath, cls.OEBPSPath,
                       cls.ContentPath, cls.StylePath, cls.FontsPath]
        for dir_path in directories:
            dir_path.mkdir(parents=True, exist_ok=True)

        (cls.MetaPath / 'container.xml').write_text(container_xml)
        (cls.EpubRootPath / 'mimetype').write_text('application/epub+zip')

        copyfile(cls.RootPath / 'content.opf', cls.OEBPSPath / 'content.opf')
        copyfile(cls.RootPath / 'toc.xhtml', cls.OEBPSPath / 'toc.xhtml')

        cls.prepare_opf()

    @classmethod
    def prepare_opf(cls):
        ET.register_namespace('', 'http://www.idpf.org/2007/opf')
        ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')
        tree = ET.parse(cls.OEBPSPath / 'content.opf')
        root = tree.getroot()
        ns = {'opf': 'http://www.idpf.org/2007/opf', 'dc': 'http://purl.org/dc/elements/1.1/'}
        
        title_elem = root.find('.//dc:title', ns)
        if title_elem is not None:
            title_elem.text = cls.FileName
        
        modified_elem = root.find('.//opf:meta[@property="dcterms:modified"]', ns)
        if modified_elem is not None:
            modified_elem.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        tree.write(cls.OEBPSPath / 'content.opf', encoding='UTF-8', xml_declaration=True)

    @staticmethod
    def get_volume_chapter(title):
        numbers = re.findall(r'\d+', title)
        return [int(num) for num in numbers] if numbers else [0]

    @classmethod
    def add_to_opf(cls, title_text, path):
        ET.register_namespace('', 'http://www.idpf.org/2007/opf')
        tree = ET.parse(cls.OEBPSPath / 'content.opf')
        root = tree.getroot()
        ns = {'opf': 'http://www.idpf.org/2007/opf'}
        
        numbers = cls.get_volume_chapter(title_text)
        vol = numbers[0] if numbers else 0
        ch = numbers[1] if len(numbers) > 1 else vol

        item_id = f"{vol}-{ch}"
        manifest = root.find('opf:manifest', ns)
        spine = root.find('opf:spine', ns)

        item = ET.SubElement(manifest, 'item', {'id': item_id, 'href': path, 'media-type': 'application/xhtml+xml'})
        itemref = ET.SubElement(spine, 'itemref', {'idref': item_id})
        
        tree.write(cls.OEBPSPath / 'content.opf', encoding='UTF-8', xml_declaration=True)

    @classmethod
    def add_to_toc(cls, title_text, path):
        tree = ET.parse(cls.OEBPSPath / 'toc.xhtml')
        root = tree.getroot()
        ns = {'xhtml': 'http://www.w3.org/1999/xhtml'}
        
        li = ET.Element('li')
        a = ET.SubElement(li, 'a', {'href': path})
        a.text = title_text
        
        nav = root.find('.//xhtml:nav', ns)
        if nav is not None:
            ol = nav.find('xhtml:ol', ns)
            if ol is not None:
                ol.append(li)
                tree.write(cls.OEBPSPath / 'toc.xhtml', encoding='UTF-8', xml_declaration=True)

    @classmethod
    def to_zip(cls, dir_name, output_name):
        epub_path = Path(output_name).with_suffix('.epub')
        with ZipFile(epub_path, 'w') as zipf:
            zipf.write(cls.EpubRootPath / 'mimetype', 'mimetype', compress_type=ZIP_STORED)
            for file_path in cls.EpubRootPath.glob('**/*'):
                if file_path.is_file() and file_path.name != 'mimetype':
                    arcname = file_path.relative_to(cls.EpubRootPath)
                    zipf.write(file_path, arcname)

class Novelfull:
    @staticmethod
    def parse_chapter(request):
        soup = BeautifulSoup(request.text, 'lxml')
        chapter = soup.find('div', class_='col-xs-12')
        title = chapter.h2.a.text if chapter and chapter.h2 else "No Title"
        
        next_url = ''
        next_link = chapter.find('a', id='next_chap') if chapter else None
        if next_link and 'href' in next_link.attrs:
            next_url = f"https://novelfull.com{next_link['href']}"
        
        return title, next_url

    @staticmethod
    def to_text(request, file_handle):
        title, next_url = Novelfull.parse_chapter(request)
        soup = BeautifulSoup(request.text, 'lxml')
        chapter_content = soup.find('div', id='chapter-content')
        paragraphs = [p.text for p in chapter_content.find_all('p') if p.text.strip()] if chapter_content else []
        
        file_handle.write(f"{title}\n\n")
        file_handle.write('\n'.join(paragraphs))
        file_handle.write('\n\n\n\n')
        print(title)
        return next_url

    @staticmethod
    def to_epub(request):
        title, next_url = Novelfull.parse_chapter(request)
        soup = BeautifulSoup(request.text, 'lxml')
        chapter_content = soup.find('div', id='chapter-content')
        
        epub_html = BeautifulSoup('<html xmlns="http://www.w3.org/1999/xhtml"></html>', 'lxml-xml')
        head = epub_html.new_tag('head')
        epub_html.html.append(head)
        body = epub_html.new_tag('body')
        epub_html.html.append(body)
        
        if title:
            h2 = epub_html.new_tag('h2')
            h2.string = title
            body.append(h2)
        
        if chapter_content:
            for p in chapter_content.find_all('p'):
                if p.text.strip():
                    new_p = epub_html.new_tag('p')
                    new_p.string = p.text
                    body.append(new_p)
        
        safe_title = re.sub(r'[\W_]+', '', title)
        content_path = Settings.ContentPath / f"{safe_title}.xhtml"
        content_path.write_text(epub_html.prettify(), encoding='utf-8')
        
        Settings.add_to_opf(title, f"Content/{safe_title}.xhtml")
        Settings.add_to_toc(title, f"Content/{safe_title}.xhtml")
        
        print(title)
        return next_url

def main():
    Settings.FileName = input('File name: ').strip()
    initial_url = input('Initial chapter URL: ').strip()
    print('1 - Epub\n2 - Txt')
    option = input('Option: ').strip()
    
    Settings.set_paths()
    if option == '1':
        Settings.prepare_epub()
    
    next_url = initial_url
    file_handle = None
    if option == '2':
        file_handle = open(Settings.RootPath / 'novel.txt', 'a', encoding='utf-8')
    
    while next_url:
        try:
            resp = requests.get(next_url)
            resp.raise_for_status()
            if option == '1':
                next_url = Novelfull.to_epub(resp)
            elif option == '2' and file_handle:
                next_url = Novelfull.to_text(resp, file_handle)
        except requests.RequestException as e:
            print(f"Error fetching {next_url}: {e}")
            break
    
    if file_handle:
        file_handle.close()
    if option == '1':
        Settings.to_zip(Settings.EpubRootPath, Settings.FileName)
        print(f"ePub created: {Settings.FileName}.epub")

if __name__ == '__main__':
    main()