import requests
import bs4

url = 'http://forums.somethingawful.com/forumdisplay.php?forumid=219'

def getthreads(number=20):
    cookies = dict(bbuserid='78389', bbpassword='9bf24e58b249fd296f751a98456ce72d')
    response = requests.get(url, cookies=cookies)
    soup = bs4.BeautifulSoup(response.text)
    threads = soup.findAll("tr", {'class':['thread', 'thread seen']})
    
    ids = [a['id'] for a in threads] 
    titles = []
    authors = []
    replies = []
    unreads = []
    ratings = []
    lastpostbys = []
    lastposttimes = []
    for thread in threads:
        titles.append(thread.find('a', {"class" : "thread_title"} ).string)
        authors.append(thread.find('td', {"class" : "author"}).string)
        unread = thread.find('a', {"class" : "count"}) or None
        if (unread):
            unreads.append(unread.string)
        else:
            if (thread['class'] == [u'thread',u'seen']):
                unreads.append('Caught up!')
            else:
                unreads.append('All')
        rating = thread.find('td', {"class":"rating"}) or None
        if (rating.contents == [u'\xa0']):
            ratings.append('None')
        else:
            ratingalt = rating.find('img')["title"]
            ratings.append(ratingalt.split()[3])
        lastposttimes.append(u' '.join(thread.find('td', {"class":"lastpost"}).find('div', {"class":"date"}).string.split()[:2]))
        lastpostbys.append(thread.find('td', {"class":"lastpost"}).find('a', {"class":"author"}).string)
    return zip(ids, titles, authors, unreads, ratings, lastpostbys, lastposttimes)

line = 1
for id, title, author, unread, rating, lastpostby, lastposttime in getthreads():
    print line, id, title, author, unread, rating, lastpostby, lastposttime
    line += 1
