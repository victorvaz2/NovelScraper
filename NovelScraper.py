from bs4 import BeautifulSoup
from shutil import copyfile
from xml.etree import ElementTree as ET
import requests
import string
import os
from datetime import datetime
import re

class Settings:
    FileName = ''
    RootPath = './'
    EpubRootPath = ''
    MetaPath = ''
    OEBPSPath = ''
    ContentPath = ''
    StylePath = ''
    FontsPath = ''

    def setPath():
        Settings.EpubRootPath = Settings.RootPath + Settings.FileName + '/'
        Settings.MetaPath = Settings.EpubRootPath + 'META-INF/'
        Settings.OEBPSPath = Settings.EpubRootPath + 'OEBPS/'
        Settings.ContentPath = Settings.OEBPSPath + 'Content/'
        Settings.StylePath = Settings.OEBPSPath + 'Style/'
        Settings.FontsPath = Settings.OEBPSPath + 'Fonts/'

    def prepareEpub():
        containerXML = '''<?xml version="1.0"?>
        <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
            <rootfiles>
                <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
        </rootfiles>
        </container>'''
        
        try:
            os.mkdir(Settings.EpubRootPath)
        except OSError:
            pass
        try:
            os.mkdir(Settings.MetaPath)
        except OSError:
            pass
        try:
            os.mkdir(Settings.OEBPSPath)
        except OSError:
            pass
        try:
            os.mkdir(Settings.ContentPath)
        except OSError:
            pass
        try:
            os.mkdir(Settings.StylePath)
        except OSError:
            pass
        try:
            os.mkdir(Settings.FontsPath)
        except OSError:
            pass

        with open(Settings.MetaPath + 'container.xml', 'w') as file:
            file.write(containerXML)

        with open(Settings.EpubRootPath + 'mimetype', 'w') as file:
            file.write('application/epub+zip')

        copyfile(Settings.RootPath + 'content.opf', Settings.OEBPSPath + 'content.opf')

        Settings.prepareOPF()

    def prepareOPF():
        ET.register_namespace('','http://www.idpf.org/2007/opf')
        # ET.register_namespace('opf','http://www.idpf.org/2007/opf')
        ET.register_namespace('dc','http://purl.org/dc/elements/1.1/')
        tree = ET.parse(Settings.OEBPSPath+'content.opf')
        root = tree.getroot()
        root[0][1].text = Settings.FileName # Title
        root[0][5].text = datetime.now().strftime('%Y-%m-%d') # Modified datetime
        tree.write(Settings.OEBPSPath + 'content.opf', encoding='UTF-8',xml_declaration=True)

    # returns an array with all numbers contained on the title
    # Bla bla Book 1 chapter 73 ===> [1,73]
    # Bla bla chapter 80        ===> [80]
    def getVolumeAndChapter(title):
        return list(re.findall(r'\d+',title))

    def addToOPF(titleText, path):
        # Adds chapters to .opf
        tree = ET.parse(Settings.OEBPSPath+'content.opf')
        root = tree.getroot()
        
        newChapter = ET.Element('item')
        newSpine = ET.Element('itemref')
        volume = (Settings.getVolumeAndChapter(titleText))[0]
        # Pos 0 should have a number, however, pos 1 might not
        # 'Bla bla chapter 583' would only have pos 0
        try:
            chapterNumber = (Settings.getVolumeAndChapter(titleText))[1]
        except:
            chapterNumber = volume

        newChapter.set('id',volume +'-'+ chapterNumber)
        newChapter.set('href',path)
        newChapter.set('media-type','application/html+xml')
        newSpine.set('idref',volume +'-'+ chapterNumber)
        
        root[1].insert(-1,newChapter)
        root[2].insert(-1,newSpine)
        tree.write(Settings.OEBPSPath + 'content.opf', encoding='UTF-8',xml_declaration=True)


class Novelfull:
    
    def toText(request):
        soup = BeautifulSoup(request.text,'lxml')
        chapter = soup.find('div', class_='col-xs-12')
        title = chapter.h2.a.text

        # Get next chapter url
        try:
            url = 'https://novelfull.com' + chapter.find('a', id='next_chap')['href']
        except:
            url = ''

        chapterText = chapter.find('div', id='chapter-content')
        chapterText = chapterText.find_all('p')
        cleanChapterText = ''
        
        # Adds a new paragraph if the p tag is not empty (tons of empty p tags on this website)
        # As a bonus, excludes ads since they are on div tags
        for p in chapterText:
            if(p.text):
                cleanChapterText += p.text + '\n'

        printable = set(string.printable)
        cleanChapterText = ''.join(filter(lambda x: x in printable, cleanChapterText))
        file = open(Settings.RootPath + 'novel.txt','a')
        file.write(title + '\n\n' + cleanChapterText + '\n\n\n\n')
        file.close()
        print(title)
        # print(cleanChapterText)
        # print(url)
        return (url)
        
    def toEpub(request):

        # Prepare head tag
        epubFile = BeautifulSoup('<html></html>','lxml')
        newTag = BeautifulSoup().new_tag('head')
        epubFile.html.append(newTag)

        # Get the page content
        pageContent = BeautifulSoup(request.text,'lxml')
        chapter = pageContent.find('div', class_='col-xs-12')

        # Add the title
        titleText = chapter.h2.a.text
        titleTag = BeautifulSoup().new_tag('title')
        titleTag.string = titleText
        epubFile.head.append(titleTag)

        # Prepare the body tag
        newTag = BeautifulSoup().new_tag('body')
        epubFile.html.append(newTag)

        # Get next chapter url
        try:
            url = 'https://novelfull.com' + chapter.find('a', id='next_chap')['href']
        except:
            url = ''

        chapterText = chapter.find('div', id='chapter-content')
        chapterText = chapterText.find_all('p')
        
        # Adds a new paragraph if the p tag is not empty (tons of empty p tags on this website)
        # As a bonus, excludes ads since they are on div tags
        for p in chapterText:
            if(p.text):
                epubFile.body.append(p)
        
        printable = set(string.printable)
        epubFileText = ''.join(filter(lambda x: x in printable, str(epubFile)))
        
        print(titleText)

        titleText = ''.join(e for e in titleText if e.isalnum())
        path = Settings.ContentPath + titleText + '.html'
        with open(path,'w') as file:
            file.write(epubFileText)

        # Adds chapters to .opf
        Settings.addToOPF(titleText,path)

        return (url)


def main():
    
    # print(os.getcwd())
    '''Settings.FileName = input('Title: ')
    url = input('Initial chapter URL: ')
    print('1 - Epub')
    print('2 - txt')
    option = int(input('Option: '))'''

    Settings.FileName = 'divine throne of primordial blood'
    url = 'https://novelfull.com/divine-throne-of-primordial-blood/book-5-chapter-91-study.html'
    option = 1
    Settings.setPath()
    if option == 1:
       Settings.prepareEpub()
   
    while(url):
        request = requests.get(url)
        #print('Connecting...')
        if(request.status_code == 200):
            #print('Connected...')
            if(option == 1):
                print('Downloading to .epub')
                url = Novelfull.toEpub(request)

            elif(option == 2):
                print('Downloading to .txt')
                url = Novelfull.toText(request)
            
            if(not url):
                quit()
        else:
            print('Connection failed'),


if(__name__ == '__main__'):
    main()