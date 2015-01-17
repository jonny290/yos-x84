""" YOSPOS index page reader for x84 by jonny290"""

# Variables for start position of lightbar etc can be found in def main()
# If you are running this on a -Windows- machine you will have to search
# and replace the '/' with '\' for the directory browsing to work correctly.

from x84.bbs import getsession, echo, getch, gosub, getterminal, getch
import os
from os import walk


import requests
import bs4



__author__ = 'Hellbeard'
__version__ = 1.11



FILTER_PRIVATE = True
ALREADY_READ = set()
DELETED = set()
SEARCH_TAGS = set()
READING = False
TIME_FMT = '%A %b-%d, %Y at %r'


def quote_body(msg, width=79, author='some asshole', quote_txt=u'> ', hardwrap=u'\r\n'):
    """
    Given a message, return new string suitable for quoting it.
    """
    from x84.bbs import Ansi
    ucs = u''
    for line in msg.splitlines():
        ucs += u''.join((
            quote_txt,
            Ansi(line).wrap(width - len(quote_txt), indent=quote_txt),
            hardwrap,))
    return u''.join((
         author,' posted:',
        hardwrap, ucs, hardwrap))


def allow_tag(idx):
    """
    Returns true if user is allowed to 't'ag message at idx:
        * sysop and moderator
        * author or recipient
        * a member of any message tag matching user group
    """
    from x84.bbs import getsession, get_msg
    session = getsession()
    if ('sysop' in session.user.groups
            or 'moderator' in session.user.groups):
        return True
    msg = get_msg(idx)
    if session.user.handle in (msg.recipient, msg.author):
        return True
    for tag in msg.tags:
        if tag in session.user.groups:
            return True
    return False


def mark_undelete(idx):
    """ Mark message ``idx`` as deleted. """
    from x84.bbs import getsession
    session = getsession()
    # pylint: disable=W0603
    #         Using the global statement
    global DELETED
    DELETED = session.user.get('trash', set())
    if idx in DELETED:
        DELETED.remove(idx)
        session.user['trash'] = DELETED
        return True


def mark_delete(idx):
    """ Mark message ``idx`` as deleted. """
    from x84.bbs import getsession
    session = getsession()
    # pylint: disable=W0603
    #         Using the global statement
    global DELETED
    DELETED = session.user.get('trash', set())
    if not idx in DELETED:
        DELETED.add(idx)
        session.user['trash'] = DELETED
        return True


def mark_read(idx):
    """ Mark message ``idx`` as read. """
    from x84.bbs import getsession
    session = getsession()
    # pylint: disable=W0603
    #         Using the global statement
    global ALREADY_READ
    ALREADY_READ = session.user.get('readmsgs', set())
    if idx not in ALREADY_READ:
        ALREADY_READ.add(idx)
        session.user['readmsgs'] = ALREADY_READ
        return True



def banner():
    """ Returns string suitable for displaying banner. """
    from x84.bbs import getterminal
    term = getterminal()
    return u''.join((u'\r\n\r\n',
                     term.yellow(u'... '.center(term.width).rstrip()),
                     term.bold_yellow(' MSG R'),
                     term.yellow('EAdER'),))


def prompt_tags(tags):
    """ Prompt for and return valid tags from TAGDB. """
    # pylint: disable=R0914,W0603
    #         Too many local variables
    #         Using the global statement
    from x84.bbs import DBProxy, echo, getterminal, getsession
    from x84.bbs import Ansi, LineEditor, getch
    session, term = getsession(), getterminal()
    tagdb = DBProxy('tags')
    global FILTER_PRIVATE
    while True:
        # Accept user input for a 'search tag', or /list command
        #
        echo(u"\r\n\r\nENtER SEARCh %s, COMMA-dEliMitEd. " % (
            term.red('TAG(s)'),))
        echo(u"OR '/list', %s%s\r\n : " % (
            (term.yellow_underline('^x') + u':autoscan '
                if session.user.get('autoscan', False) else u''),
            term.yellow_underline('^a') + u':ll msgs ' +
            term.yellow_underline('Esc') + u':quit',))
        width = term.width - 6
        sel_tags = u', '.join(tags)
        while len(Ansi(sel_tags)) >= (width - 8):
            tags = tags[:-1]
            sel_tags = u', '.join(tags)
        lne = LineEditor(width, sel_tags)
        echo(lne.refresh())
        while not lne.carriage_returned:
            inp = getch()
            if inp in (unichr(27), term.KEY_EXIT):
                return None
            if inp in (unichr(24),): # ^A:all
                return set()
            if inp in (unichr(1),): # ^X:autoscan
                return session.user.get('autoscan', set())
            else:
                echo(lne.process_keystroke(inp))
        if lne.carriage_returned:
            inp_tags = lne.content
        if (inp_tags is None or 0 == len(inp_tags)
                or inp_tags.strip().lower() == '/quit'):
            return set()
        elif inp_tags.strip().lower() == '/list':
            # list all available tags, and number of messages
            echo(term.normal)
            echo(u'\r\n\r\nTags: \r\n')
            all_tags = sorted(tagdb.items())
            if 0 == len(all_tags):
                echo(u'None !'.center(term.width / 2))
            else:
                echo(Ansi(u', '.join(([u'%s(%s)' % (
                    term.red(tag),
                    term.yellow(str(len(msgs))),)
                        for (tag, msgs) in all_tags]))).wrap(term.width - 2))
            continue
        elif (inp_tags.strip().lower() == '/nofilter'
                and 'sysop' in session.user.groups):
            # disable filtering private messages
            FILTER_PRIVATE = False
            continue

        echo(u'\r\n')
        # search input as valid tag(s)
        tags = set([_tag.strip().lower() for _tag in inp_tags.split(',')])
        for tag in tags.copy():
            if not tag in tagdb:
                tags.remove(tag)
                echo(u"\r\nNO MESSAGES With tAG '%s' fOUNd." % (
                    term.red(tag),))
        return tags



def read_messages(msgs, title, currentpage, totalpages, threadid, cachetime):
    """
    Provide message reader UI given message list ``msgs``,
    with new messages in list ``new``.
    """
    # pylint: disable=R0914,R0912,R0915
    #         Too many local variables
    #         Too many branches
    #         Too many statements
    from x84.bbs import timeago, get_msg, getterminal, echo, gosub
    from x84.bbs import ini, Pager, getsession, getch, Ansi, Msg
    import x84.default.writemsg
    session, term = getsession(), getterminal()

    session.activity = 'reading msgs'
    # build header
    #len_idx = max([len('%d' % (_idx,)) for _idx in msgs])
    len_idx = 40
    len_author = ini.CFG.getint('nua', 'max_user')
    len_ago = 9
    len_subject = ini.CFG.getint('msg', 'max_subject')
    len_preview = min(len_idx + len_author + len_ago + len_subject + -1, term.width - 2)
    reply_depth = ini.CFG.getint('msg', 'max_depth')
    indent_start, indent, indent_end = u'\\', u'-', u'> '

    def get_header(msgs_idx):
        """
        Return list of tuples, (idx, unicodestring), suitable for Lightbar.
        """
        import datetime
        msg_list = list()

        def head(msg, depth=0, maxdepth=reply_depth):
            """ This recursive routine finds the 'head' message
                of any relationship, up to maxdepth.
            """
            if (depth <= maxdepth
                    and hasattr(msg, 'parent')
                    and msg.parent is not None):
                return head(get_msg(msg.parent), depth + 1, maxdepth)
            return msg.idx, depth

        for idx, txt in enumerate(msgs_idx):
            author, subj = txt[0], txt[1]
            msg_list.append([idx, author, subj])
            
        return msg_list

    def get_selector(mailbox, prev_sel=None):
        """
        Provide Lightbar UI element given message mailbox returned from
        function get_header, and prev_sel as previously instantiated Lightbar.
        """
        from x84.bbs import Lightbar
        pos = prev_sel.position if prev_sel is not None else (0, 0)
        sel = Lightbar(
            height=(term.height / 3
                    if term.width < 140 else term.height - 3),
            width=len_preview, yloc=2, xloc=0)
        sel.glyphs['top-horiz'] = u''
        sel.glyphs['left-vert'] = u''
        sel.colors['highlight'] = term.yellow_reverse
        sel.update(mailbox)
        sel.position = pos
        return sel

    def get_reader():
        """
        Provide Pager UI element for message reading.
        """
        reader_height = (term.height - (term.height / 3) - 2)
        reader_indent = 2
        reader_width = min(term.width - 1, min(term.width - reader_indent, 80))
        reader_ypos = ((term.height - 1 ) - reader_height if
                      (term.width - reader_width) < len_preview else 2)
        reader_height = term.height - reader_ypos - 1
        msg_reader = Pager(
            height=reader_height,
            width=reader_width,
            yloc=reader_ypos,
            xloc=min(len_preview + 2, term.width - reader_width))
        msg_reader.glyphs['top-horiz'] = u''
        msg_reader.glyphs['right-vert'] = u''
        return msg_reader

#   def format_msg(reader, idx):
#       """ Format message of index ``idx`` into Pager instance ``reader``. """
#       msg = msgs[idx]
#       author = msg[1][0]
#       body = msg[1][1]
#       ucs = u'\r\n'.join((
#           (u''.join((
#               term.yellow('fROM: '),
#               (u'%s' % term.bold(author,)).rjust(len(author)),
#               u' ' * (reader.visible_width - (len(author) )),
#               ))),
#           u''.join((
#               term.yellow('tO: '),
#           (Ansi(
#               term.yellow('tAGS: ')
#               + (u'%s ' % (term.bold(','),)).join((
#                   [term.bold_red(_tag)
#                       if _tag in SEARCH_TAGS
#                       else term.yellow(_tag)
#                       for _tag in msg.tags]))).wrap(
#                           reader.visible_width,
#                           indent=u'      ')),
#           (term.yellow_underline(
#               (u'SUbj: %s' % (msg.subject,)).ljust(reader.visible_width)
#           )),
#           u'', (msg.body),))
#       return ucs

    def get_selector_title(mbox):
        return cachetime

    def get_selector_footer(currentpage, totalpages):
        return 'Page '+currentpage+'/'+totalpages 

    def get_reader_footer(idx):
        """
        Returns unicode string suitable for displaying
        as footer of reader when window is active
        """

        return u''.join((
            idx,
            term.yellow(u'- '),
            u' '.join((
                term.yellow_underline(u'<') + u':back ',
                term.yellow_underline(u'r') + u':eply ',
                term.yellow_underline(u'q') + u':uit',)),
            term.yellow(u' -'),))

    def refresh(reader, selector, mbox, title):
        """
        Returns unicode string suitable for refreshing the screen.
        """
        if READING:
            reader.colors['border'] = term.bold_yellow
            selector.colors['border'] = term.bold_black
        else:
            reader.colors['border'] = term.bold_black
            selector.colors['border'] = term.bold_yellow
        padd_attr = (term.bold_yellow if not READING
                     else term.bold_black)
        sel_padd_right = padd_attr(
            u'-'
            + selector.glyphs['bot-horiz'] * (
            selector.visible_width - len(Ansi(str(title))) - 7)
            + u'-\u25a0-' if READING else u'- -')
        sel_padd_left = padd_attr(
            selector.glyphs['bot-horiz'] * 3)
        idx = selector.selection[0]
        return u''.join((term.move(0, 0), term.clear, u'\r\n',cachetime,
                         u'// REAdiNG MSGS ..'.center(term.width).rstrip(),
                         selector.refresh(),
                         selector.border() if READING else reader.border(),
                         reader.border() if READING else selector.border(),
                         selector.title(
                             sel_padd_left + title + sel_padd_right),
                         selector.footer(get_selector_footer(currentpage, totalpages)
                                         ) if not READING else u'',
                         #reader.footer(get_reader_footer(u'Post '+str(idx))
                         reader.footer(get_reader_footer(cachetime)
                                       ) if READING else u'',
                         reader.refresh(),
                         ))

    echo((u'\r\n' + term.clear_eol) * (term.height - 1))
    dirty = 2
    msg_selector = None
    msg_reader = None
    idx = None
    # pylint: disable=W0603
    #         Using the global statement
    global READING
    while (msg_selector is None and msg_reader is None
           ) or not (msg_selector.quit or msg_reader.quit):
        if session.poll_event('refresh'):
            dirty = 2
        if dirty:
            if dirty == 2:
                mailbox = get_header(msgs)
            msg_selector = get_selector(mailbox, msg_selector)
            idx = msg_selector.selection[0]
            msg_reader = get_reader()
            msg_reader.update(msgs[idx][1])
            echo(refresh(msg_reader, msg_selector, msgs, title))
            dirty = 0
        inp = getch(1)
        if inp in (u'r', u'R'):
            reply_msgbody = quote_body(msgs[idx][1],
                                        max(30, min(79, term.width - 4)), msgs[idx][0])
            echo(term.move(term.height, 0) + u'\r\n')
            session.user['draft'] = reply_msgbody
            if gosub('editor', 'draft'):
                makepost(threadid, session.user['draft'])
                dirty = 2
                READING = False
            else:
                dirty = 1
            #mark_read(idx)  # also mark as read

        # 't' uses writemsg.prompt_tags() routine, how confusing ..
        elif inp in (u't',) and allow_tag(idx):
            echo(term.move(term.height, 0))
            msg = get_msg(idx)
            if x84.default.writemsg.prompt_tags(msg):
                msg.save()
            dirty = 2

        # spacebar marks as read, goes to next message
        elif inp in (u' ',):
            dirty = 1#2 if mark_read(idx) else 1
            msg_selector.move_down()
            idx = msg_selector.selection[0]
            READING = False

        # D marks as deleted, goes to next message
        elif inp in (u'D',):
            dirty = 2 if mark_delete(idx) else 1
            msg_selector.move_down()
            idx = msg_selector.selection[0]
            READING = False

        # U undeletes, does not move.
        elif inp in (u'U',):
            dirty = 2 if mark_undelete(idx) else 1
            msg_selector.move_down()
            idx = msg_selector.selection[0]
            READING = False

        if READING:
            echo(msg_reader.process_keystroke(inp))
            # left, <, or backspace moves UI
            if inp in (term.KEY_LEFT, u'<', u'h',
                       '\b', term.KEY_BACKSPACE):
                READING = False
                dirty = 1
        else:
            echo(msg_selector.process_keystroke(inp))
            idx = msg_selector.selection[0]
            # right, >, or enter marks message read, moves UI
            if inp in (u'\r', term.KEY_ENTER, u'>',
                       u'l', 'L', term.KEY_RIGHT):
                dirty = 1#2 if mark_read(idx) else 1
                READING = True
            elif msg_selector.moved:
                dirty = 1
    echo(term.move(term.height, 0) + u'\r\n')
    return




def getposts(threadid='3263403', number=40):
    from x84.bbs import User, getsession
    import requests
    import bs4
    session = getsession()
    url = 'http://forums.somethingawful.com/showthread.php?threadid='+threadid+'&goto=lastpost'
    print url
    cookies = dict(bbuserid=session.user['sausercookie'], bbpassword=session.user['sapasscookie'])
    response = requests.get(url, cookies=cookies)
    soup = bs4.BeautifulSoup(response.text)
    title = soup.find('a',{"class":"bclast"}).text
    if hasattr(soup.find('option',{"selected":"selected"}), 'text'):
        currentpage = soup.find('option',{"selected":"selected"}).text
        totalpages = soup.find('div',{"class":"pages top"}).find_all('option',)[-1].text
    else:
        currentpage = "1"
        totalpages = "1"
    posts = soup.findAll("table", {'class':'post'})
    authors = []
    times = []
    bodies = []
    seens = []

    print len(posts)
    for post in posts:
        seenstyle = post.find('tr')['class'][0]
        if seenstyle == 'seen' or seenstyle == 'seen2':
            newpost = False
        else:
            newpost = True
        seens.append(newpost)
        authors.append(post.find('dt', {"class":['author','author platinum']}).text)
        bodies.append(post.find('td',{"class":"postbody"}).text.rstrip().lstrip())

    return [zip(authors, bodies, seens), title, currentpage, totalpages]

def makepost(threadid, body):
    from x84.bbs import getsession
    session = getsession()
    baseurl = 'http://forums.somethingawful.com/newreply.php'
    replyurl = baseurl+'?action=newreply&threadid='+threadid
    cookies = dict(bbuserid=session.user['sausercookie'], bbpassword=session.user['sapasscookie'])
    echo(replyurl)
    response = requests.get(replyurl, cookies=cookies)
    soup = bs4.BeautifulSoup(response.text)
    formkey = soup.find('input', {"name":"formkey"})["value"]
    formcookie = soup.find('input', {"name":"form_cookie"})["value"]
    echo(formkey)
    echo(formcookie)
    form = { "action":"postreply", "message":"[fixed]"+body+"[/fixed]", "submit":"Submit Reply", "threadid":threadid, "formkey":formkey, "form_cookie":formcookie}
    r = requests.post(baseurl, cookies=cookies, data=form)




def getthreads(number=20):
    from x84.bbs import getsession
    session = getsession() 
    url = 'http://forums.somethingawful.com/forumdisplay.php?forumid=219'
#cookies = dict(bbuserid=session.user['sausercookie'], bbpassword=session.user['sapasscookie'])
    cookies = dict(bbuserid=session.user['sausercookie'], bbpassword=session.user['sapasscookie'])
    #cookies = dict(bbuserid='78389', bbpassword='9bf24e58b249fd296f751a98456ce72d')
    print url
    response = requests.get(url, cookies=cookies)
    soup = bs4.BeautifulSoup(response.text)
    threads = soup.findAll("tr", {'class':['thread', 'thread seen']})[1:]
    ids = [a['id'].split('d')[1] for a in threads] 
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
        lastposttimes.append(u''.join(thread.find('td', {"class":"lastpost"}).find('div', {"class":"date"}).string))
        lastpostbys.append(thread.find('td', {"class":"lastpost"}).find('a', {"class":"author"}).string)
    return zip(ids, titles, authors, unreads, ratings, lastpostbys, lastposttimes)


# ---------------------------------------------------

def banner():
    term = getterminal()
    banner = ''
    return banner

# ---------------------------------------------------

def helpscreen():
    term = getterminal()
    text = []
    text.append (u'x/84 bulletins v 1.1')
    text.append (u'')
    text.append (term.bold_white+term.underline+u'Key bindings for the navigator:'+term.normal)
    text.append (u'(Q/Escape) to quit.')
    text.append (u'(Up/Dn/Right/Left/Pgup/Pgdn/Enter) to navigate.')
    text.append ('')
    text.append (term.bold_white+term.underline+u'Key bindings for the file viewer:'+term.normal)
    text.append (u'(Q/Escape/Enter) to return.')
    text.append (u'(Up/Dn/Right/Left/Pgup/Pgdn) to navigate.')
    text.append ('')
    text.append (term.bold_white+term.underline+'General key bindings:'+term.normal)
    text.append (u'(Alt+f) change to a more appropiate font in Syncterm.')

    echo(term.clear()+banner()+term.move_y(8))
    for line in text:
        echo(term.move_x(8)+line+u'\r\n')

# ---------------------------------------------------

def displayfile(filename):
    term = getterminal()
    echo(term.clear+term.move(0,0)+term.normal)

    text = {}
    counter = 0
    offset = 0
    keypressed = ''


    while 1:
        echo(term.move(0,0)+term.normal)
        for i in range (0, term.height-1): # -2 om man vill spara en rad i botten
            if len(text) > i+offset:
                echo(term.clear_eol+u'\r'+text[i+offset])

        keypressed = getch()
        echo(term.hide_cursor)
        if keypressed == 'q' or keypressed == 'Q' or keypressed == term.KEY_ESCAPE or keypressed == term.KEY_ENTER:
            break

        if keypressed == term.KEY_HOME:
            offset = 0

        if keypressed == term.KEY_END:
            if len(text) < term.height: # if the textline has fewer lines than the screen..
                offset = 0
            else:
                offset = len(text) - term.height+1

        if keypressed == term.KEY_DOWN:
            if len(text) > offset+term.height-1: #offset < len(text) + term.height:
                offset = offset + 1

        if keypressed == term.KEY_UP:
            if offset > 0:
                offset = offset -1

        if keypressed == term.KEY_LEFT or keypressed == term.KEY_PGUP:
            if offset > term.height:
                offset = offset - term.height+2
            else:
                offset = 0

        if keypressed == term.KEY_RIGHT or keypressed == term.KEY_PGDOWN:
            if (offset+term.height*2)-1 < len(text):
                offset = offset + term.height-2
            else:
                if len(text) < term.height: # if the textline has fewer lines than the screen..
                     offset = 0
                else:
                     offset = len(text) - term.height+1
         
# ---------------------------------------------------

def redrawlightbar(filer, lighty,lightx,lightbar,start,antalrader): # if the variable lightbar is negative the lightbar will be invisible
    import time
    from x84.bbs import timeago
    term = getterminal()
    echo(term.move(lighty,lightx))

    for i in range (0, term.height - 2):
        echo(term.move(lighty+i,lightx)+u' '*(term.width - lightx)) # erases 60 char. dont want to use clreol. So filenames/directories can be 45 char.

    i2 = 0
    for i in range (start,start+antalrader):
        origtime = filer[i][6].strip()
        secsago = timeago(time.time() - (3600 * 6)- time.mktime(time.strptime(origtime,"%I:%M %p %b %d, %Y")))
        
#       if secsago[-1] == 's':
        secsago = secsago[:-3]
        secsago = u''.join([ u' ' * (5-len(secsago)),  secsago ])
        rightbar = filer[i][5].rjust(19)+u' '+ str(secsago)
        leftbar = filer[i][1][:term.width - len(rightbar) - 5]
        if i2 == lightbar:
            echo(term.move(lighty+i-start-1,lightx)+term.blue_reverse+leftbar[:10]+term.normal)
        else:
            echo(term.move(lighty+i-start-1,lightx)+term.white+leftbar[:10]+term.normal)
        echo(term.move(lighty+i-start-1,term.width - len(rightbar) - 2)+rightbar+term.normal)
        i2 = i2 + 1

# ---------------------------------------------------

def getfilelist(katalog):
    filer = []
    kataloger = []
    for (dirpath, dirnames, filenames) in walk(katalog):
        filer.extend(sorted(filenames, key=str.lower))
        kataloger.extend(dirnames)
        break
    for i in range (0, len(kataloger)):
        filer.insert(0,kataloger[i]+'/')
    return filer

# ---------------------------------------------------

def main():
    """ Main procedure. """
    import time
    import memcache
    import json
    mc = memcache.Client(['104.131.0.180:11211'],debug=0)
    session = getsession()
    term = getterminal()
    session.activity = u'yospostin'
    echo(term.clear+banner())

#********** default variables for you to change ! ************* 

    lightx = 1                                      # xpos for the lightbar
    lighty = 1                                    # ypos for the lightbar
    max_amount_rows = term.height - 2

    getstart = time.time()
    filerstr = mc.get(str(session.node)+'-yosindex')
    if not filerstr:
        filer = getthreads()
        filerstr = json.dumps(filer)
        mc.set(str(session.node)+'-yosindex',filerstr,30)
        echo(term.move(term.height ,0)+'Cache miss: ' + str( time.time() - getstart) + ' seconds')
    else:
        echo(term.move(term.height ,0)+'Cache hit: ' + str( time.time() - getstart) + ' seconds')
        filer = json.loads(filerstr)
    if len(filer) > max_amount_rows:
        antalrader = max_amount_rows
    else:
        antalrader = len(filer)
# antalrader = amount of rows to be displayed. By default it will display up to 14 lines. More wont fit because of the artwork.
# as for colours and stuff.. just search and replace.
#****************************************************************

    offset = 0
    lightbarpos = 0
    keypressed = ''

    redrawlightbar(filer, lighty,lightx,lightbarpos,offset,offset+antalrader)
    echo(term.hide_cursor)

    while 1:

        keypressed = getch()

        if keypressed == 'q' or keypressed == 'Q' or keypressed == term.KEY_ESCAPE:
            echo(term.normal_cursor)
            return

        if keypressed == term.KEY_LEFT or keypressed == term.KEY_PGUP:
            offset = offset - antalrader
            if offset < 0:
                offset = 0
                lightbarpos = 0
            redrawlightbar(filer, lighty,lightx,lightbarpos,offset,antalrader)

        if keypressed == term.KEY_RIGHT or keypressed == term.KEY_PGDOWN:
            offset = offset + antalrader
            if offset+antalrader > len(filer)-1:
                offset = len(filer) - antalrader
                lightbarpos = antalrader-1
            redrawlightbar(filer, lighty,lightx,lightbarpos,offset,antalrader)

        if keypressed == term.KEY_UP and lightbarpos+offset > -1:
            echo(term.white+term.move(lighty+lightbarpos-1,lightx)+filer[lightbarpos+offset][1][:20]) # restore colour on the old coordinate
            lightbarpos = lightbarpos - 1 
            if lightbarpos < 0:
               if offset > 0:
                   offset = offset - 1
               lightbarpos = lightbarpos + 1
               redrawlightbar(filer, lighty,lightx,-1,offset,antalrader)

            echo(term.blue_reverse+term.move(lighty+lightbarpos-1,lightx)+filer[lightbarpos+offset][1][:10]+term.normal)

        if keypressed == term.KEY_DOWN and lightbarpos+offset < len(filer)-1:
            echo(term.white+term.move(lighty+lightbarpos-1,lightx)+filer[lightbarpos+offset][1][:10]) # restore colour on the old coordnate 
            lightbarpos = lightbarpos + 1
            if lightbarpos > antalrader-1:
               offset = offset + 1
               lightbarpos = lightbarpos- 1
               redrawlightbar(filer, lighty,lightx,-1,offset,antalrader)

            echo(term.blue_reverse+term.move(lighty+lightbarpos-1,lightx)+filer[lightbarpos+offset][1][:10]+term.normal)

        if keypressed == 'h':
            helpscreen()            
            getch()
            echo(term.clear+banner()+term.normal)
            redrawlightbar(filer, lighty,lightx,lightbarpos,offset,antalrader)


        if keypressed == term.KEY_ENTER:
            starttime = time.time()
            getstart = time.time()
            postsstr = mc.get(str(session.node)+str(filer[lightbarpos+offset][0]))
            if not postsstr:
                [msgs, title, currentpage, totalpages] = getposts(filer[lightbarpos+offset][0])
                postsstr = json.dumps([msgs, title, currentpage, totalpages])
                mc.set(str(session.node)+str(filer[lightbarpos+offset][0]),postsstr,30)
                cachetime = str(time.time() - getstart)
            else:
                [msgs, title, currentpage, totalpages] = json.loads(postsstr)
                cachetime = str(time.time() - getstart)
 
            read_messages(msgs, title, currentpage, totalpages, filer[lightbarpos+offset][0], cachetime)
            echo(term.clear())
            redrawlightbar(filer, lighty,lightx,lightbarpos,offset,antalrader)

