import argparse
import configparser
import json
import MySQLdb
import os
import re
import requests
from bs4 import BeautifulSoup
from collections import OrderedDict
from datetime import datetime
from time import sleep

_board_name = ''
_add_to_db = True
_rs = requests.session()
_conn = None
_cursor = None

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
    if _add_to_db:
        connect_db()

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

    if _add_to_db and _conn.open:
        close_db()

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
    soup = BeautifulSoup(res.text, 'html.parser')

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
        m = re.search('From: ([0-9]*\.[0-9]*\.[0-9]*\.[0-9]*)', content)
        ip = m.group(1)
    except:
        ip = 'none'

    target_content = u'※ 發信站'
    content = content.split(target_content)

    if date == 'none':
        main_content = content[0].replace('\n', '  ').replace('\t', '  ')
    else:
        content = content[0].split(date)
        main_content = content[1].replace('\n', '  ').replace('\t', '  ')

    # pushes
    num = 0
    pushes = []
    for tag in soup.select('div.push'):
        # if not a push, go next.
        # ex: 檔案過大！部分文章無法顯示
        # ex: class="push center warning-box"
        if len(tag['class']) != 1:
            continue
        num += 1
        push_tag = tag.find('span', {'class': 'push-tag'}).text
        push_tag = push_tag.strip()
        push_userid = tag.find('span', {'class': 'push-userid'}).text
        push_content = tag.find('span', {'class': 'push-content'}).text
        push_content = push_content[1:]
        push_ipdatetime = tag.find('span', {'class': 'push-ipdatetime'}).text
        push_ipdatetime = push_ipdatetime.strip()

        pushes.append({'status': push_tag, 'userid': push_userid, 'content': push_content, 'datetime': push_ipdatetime})

    post = OrderedDict()
    post['board'] = _board_name
    post['url'] = url
    post['author'] = author
    post['title'] = title
    post['datetime'] = f_date
    post['ip'] = ip
    post['content'] = main_content
    post['pushes'] = pushes

    save(post)

    if _add_to_db:
        insert_into_db(post)

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

    with open(filename, 'a') as f:
        j = json.dumps(post, ensure_ascii = False, indent = 4,sort_keys = False)
        f.write(j)

def connect_db():
    """ connect to databcase

    Args:
        none

    Returns:
        none
    """
    global _conn
    global _cursor
    _conn = MySQLdb.connect(read_default_file = '~/.my.cnf')
    _cursor = _conn.cursor()

def close_db():
    """ close the connected database

    Args:
        none
    
    Returns:
        none
    """
    _cursor.close()
    _conn.close()

def insert_into_db(post):
    """ insert data into database

    Args:
        param1 (OrderedDict): post details
    
    Returns:
        none
    """
    # post
    sql_post = "INSERT INTO `ptt_posts` VALUES(%s, %s, %s, %s, %s, %s, %s)"
    value_post = (post['board'], post['url'], post['author'], post['title'], post['datetime'], post['ip'], post['content'])

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
        _cursor.execute(sql_post, value_post)
        
        if len(post['pushes']) != 0:
            _cursor.executemany(sql_pushes, value_pushes)

        _conn.commit()
    except MySQLdb.Error as e:
        print(str(e))
        _conn.rollback()

def parse_argvs():
    """ parse argvs via argparse

    Args:
        none

    Returns:
        none
    """
    parser = argparse.ArgumentParser(description = 'A crawler for web ptt')
    parser.add_argument('-b', '--board', type = str, help = 'Board name', required = True)
    parser.add_argument('--no-database', dest = 'db', action = 'store_false', help = 'don\'t add to the database')
    parser.set_defaults(db = True)
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
