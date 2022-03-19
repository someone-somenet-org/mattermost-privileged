#!/usr/bin/env python3
# Someone's Mattermost scripts.
#   Copyright (c) 2016-2022 by Someone <someone@somenet.org> (aka. Jan Vales <jan@jvales.net>)
#   published under MIT-License
#
# Posts with most reactions in the last 6 months.
#

import psycopg2
import psycopg2.extras

import config


def main(dbconn):
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT 'https://mattermost.fsinf.at/'||teams.name||'/pl/'||postid AS url, teams.name||'::'||channels.name AS channelname, count(*) AS cnt, postid
                FROM reactions JOIN posts ON (postid=posts.id) JOIN channels ON (posts.channelid=channels.id) left JOIN teams ON (teams.id=channels.teamid)
                WHERE channels.type='O' and posts.createat > extract(epoch FROM (NOW() - INTERVAL '6 month'))*1000 GROUP BY teams.name, channels.name, postid ORDER BY cnt DESC LIMIT 30
                """)

    msg = "#posts_with_most_reactions #mmstats top30 posts in the last 6 months with the most reactions.\n**``DO NOT ADD ANY REACTIONS IF YOU FOUND THEM VIA THESE LINKS. IT WILL SKEW THE STATS``**\n\n|team::channel + link|cnt|\n|---|---:|\n"
    for record in cur.fetchall():
        try:
            msg += "|["+record["channelname"]+"]("+record["url"]+")|"+str(record["cnt"])+"|\n"
        except TypeError:
            pass
    return msg
