import requests
import bs4

url = 'http://forums.somethingawful.com/forumdisplay.php?forumid=219'

def thread_titles(number=20):
    cookies = dict(bbuserid='78389', bbpassword='9bf24e58b249fd296f751a98456ce72d')
    response = requests.get(url, cookies=cookies)
    soup = bs4.BeautifulSoup(response.text)
    threads = soup.findAll("tr", {'class':['thread', 'thread seen']})
    
    titles = [a.string for a in soup.find_all("a", class_="thread_title")][:number]
    authors =  [a.string for a in soup.find_all("a", class_="author")][:number]
    time =  [a.string for a in soup.find_all("div", class_="date")][:number]

    return zip(titles,authors, time)

line = 1
for title, author, time in thread_titles():
    print line, title, author, time
    line += 1
