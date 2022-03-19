#!/usr/bin/env python3
# Someone's Mattermost scripts.
#   Copyright (c) 2016-2022 by Someone <someone@somenet.org> (aka. Jan Vales <jan@jvales.net>)
#   published under MIT-License
#
# Users online
#

import psycopg2
import psycopg2.extras

import config


def main(dbconn):
    msg = "#user_activity #mmstats distinct user activity.\n\n|users ...|day|week|month|since "+config.cutoff_date+"|\n|---|---:|---:|---:|---:|\n"

    # online
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
                SELECT sum(CASE WHEN lastactivity > extract(epoch FROM (NOW() - INTERVAL '1 day'))*1000 THEN 1 ELSE 0 END) AS cnt_day,
                    sum(CASE WHEN lastactivity > extract(epoch FROM (NOW() - INTERVAL '1 week'))*1000 THEN 1 ELSE 0 END) AS cnt_week,
                    sum(CASE WHEN lastactivity > extract(epoch FROM (NOW() - INTERVAL '1 month'))*1000 THEN 1 ELSE 0 END) AS cnt_month,
                    sum(CASE WHEN lastactivity > extract(epoch FROM TIMESTAMP '"""+config.cutoff_date+"""')*1000 THEN 1 ELSE 0 END) AS cnt_cutoff
                FROM (SELECT users.id, GREATEST(status.lastactivityat, MAX(sessions.lastactivityat), users.updateat) as lastactivity 
                    FROM users LEFT JOIN status ON (users.id = status.userid) LEFT JOIN sessions ON (users.id = sessions.userid)
                    GROUP BY users.id, status.lastactivityat, users.updateat) AS a;
                """)
    record = cur.fetchall()[0]
    msg += "|online|"+str(record["cnt_day"])+"|"+str(record["cnt_week"])+"|"+str(record["cnt_month"])+"|"+str(record["cnt_cutoff"])+"|\n"

    # posts
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
                SELECT sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 day'))*1000 THEN 1 ELSE 0 END) AS cnt_day,
                    sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 week'))*1000 THEN 1 ELSE 0 END) AS cnt_week,
                    sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 month'))*1000 THEN 1 ELSE 0 END) AS cnt_month,
                    sum(CASE WHEN createat > extract(epoch FROM TIMESTAMP '"""+config.cutoff_date+"""')*1000 THEN 1 ELSE 0 END) AS cnt_cutoff
                FROM (select userid, max(createat) as createat FROM posts GROUP BY userid ORDER BY createat DESC) AS a limit 10
                """)
    record = cur.fetchall()[0]
    msg += "|posted|"+str(record["cnt_day"])+"|"+str(record["cnt_week"])+"|"+str(record["cnt_month"])+"|"+str(record["cnt_cutoff"])+"|\n"

    # pubchan posts
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
                SELECT sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 day'))*1000 THEN 1 ELSE 0 END) AS cnt_day,
                    sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 week'))*1000 THEN 1 ELSE 0 END) AS cnt_week,
                    sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 month'))*1000 THEN 1 ELSE 0 END) AS cnt_month,
                    sum(CASE WHEN createat > extract(epoch FROM TIMESTAMP '"""+config.cutoff_date+"""')*1000 THEN 1 ELSE 0 END) AS cnt_cutoff
                FROM (select userid, max(posts.createat) as createat FROM posts JOIN channels ON (posts.channelid = channels.id) WHERE channels.type='O' GROUP BY userid ORDER BY createat DESC) AS a
                """)
    record = cur.fetchall()[0]
    msg += "|posted in pubchan|"+str(record["cnt_day"])+"|"+str(record["cnt_week"])+"|"+str(record["cnt_month"])+"|"+str(record["cnt_cutoff"])+"|\n"

    # privchan posts
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
                SELECT sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 day'))*1000 THEN 1 ELSE 0 END) AS cnt_day,
                    sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 week'))*1000 THEN 1 ELSE 0 END) AS cnt_week,
                    sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 month'))*1000 THEN 1 ELSE 0 END) AS cnt_month,
                    sum(CASE WHEN createat > extract(epoch FROM TIMESTAMP '"""+config.cutoff_date+"""')*1000 THEN 1 ELSE 0 END) AS cnt_cutoff
                FROM (select userid, max(posts.createat) as createat FROM posts JOIN channels ON (posts.channelid = channels.id) WHERE channels.type='P' GROUP BY userid ORDER BY createat DESC) AS a
                """)
    record = cur.fetchall()[0]
    msg += "|posted in privchan|"+str(record["cnt_day"])+"|"+str(record["cnt_week"])+"|"+str(record["cnt_month"])+"|"+str(record["cnt_cutoff"])+"|\n"

    # privchan posts
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
                SELECT sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 day'))*1000 THEN 1 ELSE 0 END) AS cnt_day,
                    sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 week'))*1000 THEN 1 ELSE 0 END) AS cnt_week,
                    sum(CASE WHEN createat > extract(epoch FROM (NOW() - INTERVAL '1 month'))*1000 THEN 1 ELSE 0 END) AS cnt_month,
                    sum(CASE WHEN createat > extract(epoch FROM TIMESTAMP '"""+config.cutoff_date+"""')*1000 THEN 1 ELSE 0 END) AS cnt_cutoff
                FROM (select userid, max(posts.createat) as createat FROM posts JOIN channels ON (posts.channelid = channels.id) WHERE channels.type NOT IN ('O', 'P') GROUP BY userid ORDER BY createat DESC) AS a
                """)
    record = cur.fetchall()[0]
    return msg + "|posted private|"+str(record["cnt_day"])+"|"+str(record["cnt_week"])+"|"+str(record["cnt_month"])+"|"+str(record["cnt_cutoff"])+"|\n"
