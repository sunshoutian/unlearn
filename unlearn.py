#!/usr/bin/python

import re
import sys
import getpass
import mechanize
import BeautifulSoup

# A Node is either a directory or a file. We will build a tree of these based 
# on a course's Table of Contents in LEARN
class Node(object):
    def __init__(self, node_type, name, url=None):
        if node_type not in ['header', 'directory', 'file']:
            raise Exception('Invalid node type')

        self.node_type = node_type
        self.name = name
        self.url = url
        self.children = []

    def insert_child(self, index, node):
        self.children.insert(index, node)

    def append_child(self, node):
        self.children.append(node)

def login(browser, username, password):

    login_url = ('https://cas.uwaterloo.ca/cas/login?service=http%3a%2f%2flear'
            'n.uwaterloo.ca%2fd2l%2forgtools%2fCAS%2fDefault.aspx')
    browser.open(login_url)
    browser.select_form(nr=0)
    browser['username'] = username
    browser['password'] = password
    browser.submit()
    
    if browser.geturl() != ('https://learn.uwaterloo.ca/d2l/lp/homepage/home.d'
            '2l?ou=6606'):
        return False

    return True

def get_ou_params(browser):
    params = []

    # Get the special ou parameter from each of the user's courses
    for link in browser.links(url_regex='/d2l/lp/ouHome/home\.d2l\?ou=\d+'):
         split_url = link.url.split('?')
         if len(split_url) == 2:
            split_ou = split_url[1].split('=')
            if len(split_ou) == 2:
                params.append(split_ou[1])

    return params

def is_dir(html_row):
    img = html_row.findAll('img')[-1]
    if img == None:
        return False
    
    return '/d2l/img/0/Framework.Grid' in img['src']

def build_tree(ou_param, root, html):

    if html == '':
        return root

    trees_stack = []
    trees_seen = 0
    leaves = []
    seen_dir = False
    rows = html.findAll('tr')
    for row in reversed(rows):

        # Get the name of the row
        name_col = row.find('td', 'd_gn')
        if name_col == None:
            continue
        name = name_col.text.strip()

        if is_dir(row):

            dir_node = Node('directory', name)

            # If the last row was a directory and this one is again a 
            # directory, all the previous rows on our stack must be children of
            # this directory
            if seen_dir:
                while trees_seen:
                    dir_node.insert_child(0, trees_stack.pop())
                    trees_seen -= 1

                trees_stack.append(dir_node)
                continue

            seen_dir = True
            while leaves:
                dir_node.insert_child(0, leaves.pop(0))

            trees_stack.append(dir_node)
            trees_seen += 1

        else:
            seen_dir = False

            href = row.find('a')['href']
            tId_param = re.search('\&tId\=([0-9]+)', href).group(1) 
            url = ('https://learn.uwaterloo.ca/d2l/lms/content/preview.d2l?tId'
                    '=%s&ou=%s') % (tId_param, ou_param)  
            leaves.append(Node('file', name, url))

    while trees_stack:
        root.append_child(trees_stack.pop())

    return root

def get_content_tree(browser, params):
    base_url = 'https://learn.uwaterloo.ca/d2l/lms/content/home.d2l?ou='
    root_node = Node('directory', 'root')
    for ou in params:
        course_html = browser.open(base_url + ou).read()
        # TODO: Verify that the page opened
        soup = BeautifulSoup.BeautifulSoup(course_html, convertEntities='html')
        table = soup.find(id='z_n')
        if table == None:
            continue

        # Find the course name
        title = soup.find('title').text
        split_title = title.split('-')
        if len(split_title) < 3:
            course_name = title
        else:
            course_name = '%s - %s' % (split_title[1], split_title[2])

        course_node = Node('header', course_name.strip())
        root_node.append_child(build_tree(ou, course_node, table))

    return root_node

def _to_json(tree):

    json_list = []
    for child in tree.children:    

        json_list.append('{"type":"' + child.node_type + '",')
        json_list.append('"name":"' + child.name + '"')

        if child.name == 'file':
            json_list.append(',"url":"' + child.url + '"')

        if len(child.children) != 0:
            json_list.append(',"children":[' + _to_json(child) + ']')

        json_list.append('}')
        json_list.append(',')

    # Remove the trailing comma
    json_list.pop()

    return ''.join(json_list)

def to_json(tree):

    return '{"courses":[' + _to_json(tree) + ']}'

def to_html(tree):
    
    sys.stderr.write('Tree->html conversion is unimplemented. Showing JSON.\n')
    print to_json(tree)

def run(username, password):

    browser = mechanize.Browser()

    if not login(browser, username, password):
        raise Exception('Failed to log in.')

    params = get_ou_params(browser)
    if len(params) == 0:
        raise Exception('No courses found.')

    tree = get_content_tree(browser, params)
    if tree == None:
        raise Exception('Failed to get content HTML.')

    return to_html(tree)

username = raw_input('Desire2Learn username: ')
password = getpass.getpass('Desire2Learn password: ')

print 'Getting course info...'
run(username, password)
