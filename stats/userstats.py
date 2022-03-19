#!/usr/bin/env python3
# Ju's statistics for mattermost
#   written 2019-2020 by ju <daju@fsinf.at>
#   fix'd 2020 by Someone <someone@somenet.org> (aka. Jan Vales <jan@jvales.net>)
#
# Different active users within a time range (last 24h, last 7 days, begin of the semester)
#   and their number of posts
#

import psycopg2
import psycopg2.extras

import config


def main(dbconn):
    msg = "Users: Active different users and their posts within a certain time.\n\n||different users|# of posts\n|---|---:|---:|\n"

    # 24h
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT COUNT(DISTINCT UserId), COUNT(id) FROM posts WHERE posts.deleteat=0 AND posts.createat > EXTRACT(EPOCH FROM (NOW() - INTERVAL '1 day'))*1000""")
    # list size n where n = number of different UserIds and all values are the same - the count of posts
    row = cur.fetchone()
    msg += "|24 hours|"+str(row[0])+"|"+str(row[1])+"|\n"

    # 7 days
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT COUNT(DISTINCT UserId), COUNT(id) FROM posts WHERE posts.deleteat=0 AND posts.createat > EXTRACT(EPOCH FROM (NOW() - INTERVAL '1 week'))*1000""")
    row = cur.fetchone()
    msg += "|7 days|"+str(row[0])+"|"+str(row[1])+"|\n"

    # since cutoff_date
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT COUNT(DISTINCT UserId), COUNT(id) FROM posts WHERE posts.deleteat=0 AND posts.createat > EXTRACT(EPOCH FROM TIMESTAMP '"""+config.cutoff_date+"""')*1000""")
    row = cur.fetchone()
    msg += "|since "+config.cutoff_date+"|"+str(row[0])+"|"+str(row[1])+"|\n"

    return msg
