from datetime import datetime

from elasticsearch import Elasticsearch 
#连接elasticsearch,默认是9200
import requests
import pdb
from bs4 import BeautifulSoup
import re
import sqlite3
import os

r_url = 'https://bbs.byr.cn/user/ajax_login.json'
user_agent = r'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:52.0) Gecko/20100101 Firefox/52.0'
header_ceshi = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',  
          'Accept-Encoding': 'gzip, deflate, compress',  
          'Accept-Language': 'en-us;q=0.5,en;q=0.3',  
          'Cache-Control': 'max-age=0',  
          'Connection': 'keep-alive',          
          'X-Requested-With': 'XMLHttpRequest',  
          'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36' }  

#必须加这条才能登陆成功 {'x-requested-with': 'XMLHttpRequest'}
byr_data = {'id': '**', 'passwd': '**'}#replace ** with your id and passwd
session = requests.Session()
req = session.post(r_url, data=byr_data, headers = header_ceshi)
#print(req.text+'\n'),查看cookie

#set ES
es = Elasticsearch()
#create a database,named job.db
conn = sqlite3.connect("job.db")
#定位指针
c = conn.cursor()

if os.path.isfile("job.db"):
    # create tables
    c.execute('''CREATE TABLE job
          (id int, title text ,content text)''')
#all pages in the home  page
page_array = []
#get hrefs from all pages,from page1 to page_num
def find_all_href(page_num):
    print('*******Collecting hrefs!*******')
    for page in range(1,page_num):
        page = str(page)
        job_url = 'https://bbs.byr.cn/board/JobInfo?p='+page+'&_uid=C771397803'
        job_response = session.get(job_url,data = byr_data,headers = header_ceshi)
        
        bs = BeautifulSoup(job_response.text,'lxml')
        #all_a contains all a tag and special target value
        all_a = bs.find_all('a',target="_blank")
        for href in all_a:
            #find href in each a tag
            href = str(href)
            #now there is 'board-' in the page arrray,remove it 
            href=href[26:32]
            if href!='board-':
                page_array.append(href+'\n')
        print('page',page)

    print('*******Get hrefs success!*******')
    with open('page.data', 'w') as f:
        f.writelines(page_array)
def get_content(pagenum):
    print('*******Upload to database and ES*******')
    #get content in txt
    try:
        job_url = 'https://bbs.byr.cn/article/JobInfo/'+pagenum+'?_uid=C771397803'
        job_response = session.get(job_url,data = byr_data,headers = header_ceshi)
        bs = BeautifulSoup(job_response.text,'lxml')
        all_a = bs.find('div',class_ = 'a-content-wrap')
        #用正则表达式把标签全去掉
        reg1 = re.compile("<[^>]*>")
        content = reg1.sub('',all_a.prettify())  
        extracted_content= content.split()
        #extracted_content [7] is like '【社招】【小米】高级后台研发工程师（智能家居）',which is need to make into index
        title = extracted_content[7]
        #save content into table
        page = int(pagenum)
        valid_content = (page, title,content)
        #upload to ES
        es.index(index="search-index",doc_type="test-type",id=page,body={"page":page,"title":title,"content":content,"href":job_url})
        #save into the database
        c.execute('INSERT INTO job VALUES(?,?,?)',valid_content)
        
        # save the changes
        conn.commit()
        print('success',page)
    except Exception:
            print('Erro!')
            pass

    
#get every hrefs in the first 500 pages
find_all_href(500)
with open('page.data', 'r') as f:
    page_array = f.readlines()
#remove \n in page array
page_array = ''.join(page_array).strip('\n').splitlines()
for all_pages in page_array:
    get_content(all_pages)
