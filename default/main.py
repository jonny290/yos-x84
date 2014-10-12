"""
 Main menu script for x/84, http://github.com/jquast/x84
"""


def refresh(items=['all',]):

    """ Refresh main menu. """
    # pylint: disable=R0914
    #         Too many local variables
    from x84.bbs import getsession, getterminal, echo, Ansi, showcp437, ini, AnsiWindow
    import os
    import random, time, glob
    session, term = getsession(), getterminal()
    session.activity = u'Main menu'
    headers = glob.glob(os.path.join(os.path.dirname(__file__),"art","YOSBBS*.ANS"))
    bannername = "YOSBBS"+str(random.randrange(1,len(headers))).zfill(2)+".ANS"
    artfile = os.path.join(os.path.dirname(__file__), 'art', bannername)
    echo(term.clear())
    for line in showcp437(artfile):
        echo(line)
    echo(u'\r\n\r\n')
    entries = [
    #   ('b', 'bS NEXUS'),
        ('y', 'OsPOsT'),
        ('l', 'ASt CAllS'),
        ('o', 'NE liNERS'),
        ('w', "hO'S ONliNE"),
        ('n', 'EWS'),
    #   ('c', 'hAt'),
        ('!', 'ENCOdiNG'),
    #   ('t', 'EtRiS'),
    #   ('s', 'YS. iNfO'),
        ('f', 'ORECASt'),
        ('e', 'dit PROfilE'),
    #   ('p', 'OSt A MSG'),
    #   ('r', 'EAd All MSGS'),
        ('g', 'eT OUt'),]

    # add LORD to menu only if enabled,
    #if ini.CFG.getboolean('dosemu', 'enabled'):# and (
        #ini.CFG.get('dosemu', 'lord_path') != 'no'):
    entries.insert(0, ('#', 'PlAY lORd!'))

    #if 'sysop' in session.user.groups:
    #    entries += (('v', 'idEO CASSEttE'),)
    menu_item_width = 20; #allows us 16 char columns after pad/key
    menu_columns = 4 
    menulist = list()
    buf_str = u''
    menucol = 1
    for key, name in entries:
        menutext =u''.join((term.green(name.split()[0]),
            u' ', u' '.join(name.split()[1:]), ))
        out_str = Ansi(u''.join((
            term.bold(u'('),
            term.bold_green_underline(key),
            term.bold(u')'),
            menutext,
            u'  '))).ljust(menu_item_width)
        buf_str += out_str
        menucol += 1
        if menucol > menu_columns:
            menulist.append(buf_str)
            buf_str = u''
            menucol = 1
    if len(buf_str) > 0:
        menulist.append(buf_str)
    echo(term.move(term.height - len(menulist) - 1,0))
    for i, m in enumerate(menulist):
        echo(term.move(term.height - i - 2,0))
        echo(Ansi(m).ljust(term.width))
    echo(term.move(term.height - 1,0))
    echo(u' [%s]:' % (
        term.blue_underline(''.join([key for key, name in entries]))))


def main():
    """ Main procedure. """
    # pylint: disable=R0912
    #         Too many branches
    from x84.bbs import getsession, getch, goto, gosub
    session = getsession()

    inp = -1
    dirty = True
    while True:
        if dirty or session.poll_event('refresh'):
            refresh()
        inp = getch(1)
        dirty = True
        if inp == u'*':
            refresh()
        elif inp == u'b':
            gosub('bbslist')
        elif inp == u'l':
            gosub('lc')
        elif inp == u'o':
            gosub('ol')
        elif inp == u's':
            gosub('si')
        elif inp == u'w':
            gosub('online')
        elif inp == u'n':
            gosub('news')
        elif inp == u'f':
            gosub('weather')
        elif inp == u'e':
            gosub('profile')
        elif inp == u'#':
            gosub('lord')
        elif inp == u't':
            gosub('tetris')
        elif inp == u'c':
            gosub('chat')
        elif inp == u'p':
            gosub('writemsg')
        elif inp == u'r':
            gosub('readmsgs')
        elif inp == u'g':
            goto('logoff')
        elif inp == u'!':
            gosub('charset')
        elif inp == u'y':
            gosub('yosindex')
        elif inp == '\x1f' and 'sysop' in session.user.groups:
            # ctrl+_, run a debug script
            gosub('debug')
        elif inp == u'v' and 'sysop' in session.user.groups:
            # video cassette player
            gosub('ttyplay')
        else:
            dirty = False
