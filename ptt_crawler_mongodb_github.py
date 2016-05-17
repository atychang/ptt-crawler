#!/usr/bin/python
# -*- coding: utf-8 -*-

import argparse
import configparser
import json
import MySQLdb
import os
import re
import requests
import sys
from bs4 import BeautifulSoup
from collections import OrderedDict
from datetime import datetime
from time import sleep
from pymongo import MongoClient 


_board_name = ''
_add_to_db = True
_db_open_mysql = True       #False:close or True:open MySQLdb
_db_open_mongodb = True    #False:close or True:open Mongodb
_rs = requests.session()
_conn_mysql = None
_cursor_mysql = None
_mongo_database = None
_mongo_collection = None


def read_configuration():
    """ read configuration by configparser
    
    Args:
        none
    Returns:
        configparser
    """
    filename = '.config/' + _board_name + '.cfg'

    if not os.path.exists(filename):
        open(filename, 'w').close() 

    with open(filename) as configfile:
        config = configparser.ConfigParser()
        config.readfp(configfile)
    return config

def write_configuration(config):
    """ write config into configuration
    Args:
        param1 (configparser): configparser object
    Returns:
        none
    """
    filename = '.config/' + _board_name + '.cfg'
    with open(filename, 'w') as configfile:
        config.write(configfile)

def set_crawler_index(index_of_page, index_of_post):
    """ 儲存下次crawler該抓的文章的index
    
    Args:
        param1 (int): index of page
        param2 (int): index of post of @board_name
    
    Returns:
        none
    """
    config = read_configuration()
    value = str(index_of_page) + ', ' + str(index_of_post)
    config.set('board', _board_name, value)
    write_configuration(config)

def get_crawler_index():
    """ 根據@_board_name取得此次crawler該從哪篇文章開始抓的index
        
    ps: ptt web版為20篇文章為1頁
    
    Args:
        none
    Returns:
        list of integer
        list[0] = index of page
        list[1] = index of post of list[0]
    """
    config = read_configuration()
    crawler_index = []

    if not 'board' in config.sections():
        config.add_section('board')
        write_configuration(config)

    try:
        cfg = config.get('board', _board_name)
        crawler_index.extend(map(int, cfg.split(', ')))
    except:
        config.set('board', _board_name, '1, 1')
        write_configuration(config)
        crawler_index.extend([1, 1])

    return crawler_index

def ask_over_18():
    """ 是否年滿18歲
    
    Args:
        none
    Returns:
        none
    """
    load = {
        'from':'/bbs/' + _board_name + '/index.html',
        'yes':'yes' 
    }
    _rs.post('https://www.ptt.cc/ask/over18', verify = False, data = load)

def get_newest_page_index():
    """ get newest page index
    
    Args:
        none
    Returns:
        int
        newest page index
    """
    url = 'https://www.ptt.cc/bbs/' + _board_name + '/index.html'
    res = _rs.get(url, verify = False)
    soup = BeautifulSoup(res.text, 'html.parser')
    newest_page_url = soup.select('.btn.wide')[1]['href']
    m = re.search('[0-9]+', newest_page_url)
    newest_page_index = m.group(0)  # previous index
    
    return int(newest_page_index) + 1   # so, plus one

def crawler(index_of_page, index_of_post, newest_page_index):
    """ 解析看板, 獲得貼文網址
    
    Args:
        param1 (int): index 0f page
        param2 (int): index of post
        param3 (int): newest index of @_board_name
    Returns:
        none
    """
    if _add_to_db and _db_open_mysql:
        connect_db_mysql()

    if _add_to_db and _db_open_mongodb:
        connect_db_mongodb()

    for idx in range(index_of_page, newest_page_index + 1):
        res = _rs.get('https://www.ptt.cc/bbs/' + _board_name + '/index' + str(idx) + '.html', verify = False)
        soup = BeautifulSoup(res.text, 'html.parser')
        post_urls = []  # single page

        for tag in soup.findAll('div', {'class': ['r-ent', 'r-list-sep']}):
            try:
                atag = tag.find('a')
                if atag:
                    url = atag['href']
                    post_url = 'https://www.ptt.cc/' + url
                    post_urls.append(post_url)
                elif not atag and tag['class'][0] == 'r-ent':
                    # deleted post
                    post_urls.append(None)
                elif not atag and tag['class'][0] == 'r-list-sep':
                    # bottom post
                    break
            except:
                print('error: ' + url)

        number_of_posts = len(post_urls)

        for i in range(index_of_post - 1, number_of_posts):
            if post_urls[i]:
                parse_post(post_urls[i])
                set_crawler_index(idx, i + 2)
                print(post_urls[i] + ' success, index: ' + str(idx) + '-' + str(i + 1))
                # wait for 0.5 second
                sleep(0.5)

        # reset
        index_of_post = 1

    if _add_to_db and _db_open_mysql and _conn_mysql.open:
        close_db_mysql()

    index_of_post = number_of_posts + 1
    index_of_page = idx
    set_crawler_index(index_of_page, index_of_post)

def parse_post(post_url):
    """ parse posts
    Args:
        param1 (string): post url
        param2 (int): index of page
        param3 (int): index of post
    Returns:
        none
    """
    res = _rs.get(post_url, verify = False)
    soup = BeautifulSoup(res.text, 'html.parser', from_encoding="utf-8")

    # post id
    m = re.match('.+/(.*)\.html', post_url)
    url = m.group(1)

    article_info = soup.select('[class~=article-meta-value]')

    # author
    try:
        author = article_info[0].text
    except:
        author = 'none'
    # title
    try:
        title = article_info[2].text
    except:
        title = 'none'
    # datetime
    try:
        date = article_info[3].text
        f_date = str(datetime.strptime(date, '%a %b %d %H:%M:%S %Y'))
    except:
        date = 'none'
        f_date = 'none'

    # post content
    try:
        content = soup.find(id = 'main-content').text
    except:
        return None
    
    # ip address
    try:
        #m = re.search('From: ([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*)', content)
        if content.find('From:') != -1:
            m = re.search('From: ([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*)', content)
        else:
            m = re.search('來自: ([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*)', content)
        ip = m.group(1)
    except:
        ip = 'none'

    #----使用"※ 發信站"或"※ 編輯"來分割文章與推文
    if content.find('※ 發信站') != -1:
        target_content = u'※ 發信站'
    else:
        target_content = u'※ 編輯'
    content = content.split(target_content)

    if date == 'none':
        main_content = content[0].replace('\n', '  ').replace('\t', '  ')
    else:
        content = content[0].split(date)
        main_content = content[1].replace('\n', '  ').replace('\t', '  ')

    # pushes
    pushes_num = 0
    pushes = []
    for tag in soup.select('div.push'):
        # if not a push, go next.
        # ex: 檔案過大！部分文章無法顯示
        # ex: class="push center warning-box"
        if len(tag['class']) != 1:
            continue

        push_tag = tag.find('span', {'class': 'push-tag'}).text
        push_tag = push_tag.strip()
        push_userid = tag.find('span', {'class': 'push-userid'}).text
        push_content = tag.find('span', {'class': 'push-content'}).text
        push_content = push_content[1:]
        push_ipdatetime = tag.find('span', {'class': 'push-ipdatetime'}).text
        push_ipdatetime = push_ipdatetime.strip()
        pushes.append({'status': push_tag, 
                       'userid': push_userid, 
                       'content': push_content, 
                       'datetime': push_ipdatetime})
        
        #------ number of pushes -------------------
        if '推' in push_tag:
            num = 1
        elif '噓' in push_tag:
            num = -1
        else:
            num = 0
        pushes_num += num
        
    post = []
    post = OrderedDict()
    post['board'] = _board_name
    post['url'] = url
    post['author'] = author
    post['title'] = title
    post['datetime'] = f_date
    post['ip'] = ip
    post['content'] = main_content
    post['pushes'] = pushes
    post['pushes_num'] = pushes_num
    
    save(post)

    #Insert data to MySQL
    if _add_to_db and _db_open_mysql:
        insert_into_db_mysql(post)

def save(post):
    """ save post as json
    
    Args:
        param1 (OrderedDict): post detail
        param2 (string): url
    Returns:
        none
    """
    filename = 'posts/' + post['board'] + '/' + post['url'] + '.json'
    directory = os.path.dirname(filename)

    if not os.path.exists(directory):
        os.makedirs(directory)

    #add encoding='utf-8'
    with open(filename, 'a', encoding='utf-8') as f:
        j = json.dumps(post, ensure_ascii = False, indent = 4,sort_keys = False)
        f.write(j)
    f.close()

    #Insert data to MongoDB
    if _add_to_db and _db_open_mongodb:
        insert_into_db_mongodb(filename)

def connect_db_mysql():
    """ connect to MySQL
    Args:
        none
    Returns:
        none
    """
    global _conn_mysql
    global _cursor_mysql
    #add encoding='utf-8'
    _conn_mysql = MySQLdb.connect(host="MySQL IP", port=3306, user=" ", passwd=" ", db=" ", use_unicode=True, charset="utf8")
    _cursor_mysql = _conn_mysql.cursor()

def close_db_mysql():
    """ close the connected database
    Args:
        none
    
    Returns:
        none
    """
    _cursor_mysql.close()
    _conn_mysql.close()

def insert_into_db_mysql(post):
    """ insert data into database
    Args:
        param1 (OrderedDict): post details
    
    Returns:
        none
    """
    # post
    sql_post = "INSERT INTO `ptt_posts` VALUES(%s, %s, %s, %s, %s, %s, %s, %s)"
    value_post = (post['board'], post['url'], post['author'], post['title'], post['datetime'], post['ip'], post['content'], post['pushes_num'])

    # pushes
    sql_pushes = ''
    value_pushes = ''

    if len(post['pushes']) != 0:
        sql_pushes = "INSERT INTO `ptt_pushes` VALUES (%s, %s, %s, %s, %s, %s)"
        value_pushes = []
        for i in range(0, len(post['pushes'])):
            value_pushes.append((post['url'], i + 1, post['pushes'][i]['status'], 
            post['pushes'][i]['userid'], post['pushes'][i]['content'], post['pushes'][i]['datetime']))

    try:
        _cursor_mysql.execute(sql_post, value_post)
        
        if len(post['pushes']) != 0:
            _cursor_mysql.executemany(sql_pushes, value_pushes)

        _conn_mysql.commit()
    except MySQLdb.Error as e:
        print(str(e))
        _conn_mysql.rollback()

def connect_db_mongodb():
    """ connect to MongoDB 
    Args:
        none
    Returns:
        none
    """
    global _mongo_database
    global _mongo_collection

    conn_mongodb = MongoClient(host="MongoDB IP", port=27017)
    
    #chose database and collection
    _mongo_database = conn_mongodb.eoc
    _mongo_collection = _mongo_database.ptt_posts

def insert_into_db_mongodb(filename):
    """ insert data into MongoDB
    Args:
        param1 (OrderedDict): filename
    
    Returns:
        none
    """
    data = []
    with open(filename, 'rU' ,encoding='utf-8') as f:
        data = json.loads(f.read())
    _mongo_collection.insert(data)
    f.close()
    # wait for 1 second
    sleep(1)
    
def parse_argvs():
    """ parse argvs via argparse
    Args:
        none
    Returns:
        none
    """
    # 建立一個參數解析器，並為程式功能加上說明
    parser = argparse.ArgumentParser(description = 'A crawler for web ptt')
    # 增加一個想要的參數名稱 -b, --board, 以及參數的使用說明
    # argparse 會自動將 -b 與 --board 視為是同一個參數
    # 即是 -b 為 --board 的縮寫
    parser.add_argument('-b', '--board', type = str, help = 'Board name', required = True)
    parser.add_argument('--no-database', dest = 'db', action = 'store_false', help = 'don\'t add to the database')
    parser.set_defaults(db = True)
    # 解析參數
    args = parser.parse_args()
    
    global _board_name
    global _add_to_db

    _board_name = args.board
    _add_to_db = args.db

def main():
    parse_argvs()
    crawler_index = get_crawler_index()
    ask_over_18()
    newest_page_index = get_newest_page_index()
    crawler(crawler_index[0], crawler_index[1], newest_page_index)
    
if __name__ == '__main__':
    main()