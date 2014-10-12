
import requests
import bs4

def getposts(threadid, number=40):
    url = 'http://forums.somethingawful.com/showthread.php?threadid='+threadid+'&goto=lastpost'
    print url
    cookies = dict(bbuserid='78389', bbpassword='9bf24e58b249fd296f751a98456ce72d')
    response = requests.get(url, cookies=cookies)
    soup = bs4.BeautifulSoup(response.text)
    posts = soup.findAll("table", {'class':'post'})
    authors = []
    times = []
    bodies = []

    print len(posts)
    for post in posts:
        authors.append(post.find('dt', {"class":['author','author platinum']}).text)
        bodies.append(post.find('td',{"class":"postbody"}).text)

    return zip(authors, bodies)

posts = getposts('3669245')

print len(posts)

for post in posts:
    print "Author is: "+post[0].rstrip()
    print "Body is: "+post[1].rstrip().lstrip()

        
