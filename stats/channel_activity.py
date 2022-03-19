#!/usr/bin/env python3
# Someone's Mattermost scripts.
#   Copyright (c) 2016-2022 by Someone <someone@somenet.org> (aka. Jan Vales <jan@jvales.net>)
#   Copyright (c) 2020 by michi <michi@fsinf.at> (SQL-fix)
#   published under MIT-License
#
# Active channels, order by last 7 days.
#

import psycopg2
import psycopg2.extras

import config


def main(dbconn):
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
                    SELECT teams.name||'|'||channels.name AS cname, COALESCE(A.cntp,0) AS cutoff_cntp, COALESCE(A.cntu,0) AS cutoff_cntu, COALESCE(B.cntp,0) AS month_cntp, COALESCE(B.cntu,0) AS month_cntu,
                        COALESCE(C.cntp,0) AS week_cntp, COALESCE(C.cntu,0) AS week_cntu, COALESCE(D.cntp,0) AS day_cntp, COALESCE(D.cntu,0) AS day_cntu
                    FROM (select channelid, count(*) as cntp, count(distinct userid) as cntu FROM posts WHERE deleteat = 0 AND createat > extract(epoch FROM TIMESTAMP '"""+config.cutoff_date+"""')*1000 GROUP BY channelid) as A
                    LEFT JOIN (select channelid, count(*) as cntp, count(distinct userid) as cntu FROM posts WHERE deleteat = 0 AND createat > extract(epoch FROM (NOW() - INTERVAL '1 month'))*1000 GROUP BY channelid) as B ON (A.channelid=B.channelid)
                    LEFT JOIN (select channelid, count(*) as cntp, count(distinct userid) as cntu FROM posts WHERE deleteat = 0 AND createat > extract(epoch FROM (NOW() - INTERVAL '1 week'))*1000 GROUP BY channelid) as C ON (A.channelid=C.channelid)
                    LEFT JOIN (select channelid, count(*) as cntp, count(distinct userid) as cntu FROM posts WHERE deleteat = 0 AND createat > extract(epoch FROM (NOW() - INTERVAL '1 day'))*1000 GROUP BY channelid) as D ON (A.channelid=D.channelid)
                    JOIN channels ON (channels.id = A.channelid AND channels.type = 'O') JOIN teams ON (teams.id = channels.teamid) ORDER BY A.cntp DESC
                """)

    totalp_day = totalp_week = totalp_month = totalp_cutoff = 0
    msg = "#channel_activity #mmstats posts and distinct users in course-channels.\n\n|team|channel|since "+config.cutoff_date+" posts|du|month posts|du|week posts|du|day posts|du|\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for record in cur.fetchall():

        if record["cutoff_cntp"] > 2 and "w-inf-tuwien|" in record["cname"]:
            totalp_day += record["day_cntp"]
            totalp_week += record["week_cntp"]
            totalp_month += record["month_cntp"]
            totalp_cutoff += record["cutoff_cntp"]

            msg += "|"+record["cname"]+"|"+str(record["cutoff_cntp"])+"|"+str(record["cutoff_cntu"])+"|"+str(record["month_cntp"])+"|"+str(record["month_cntu"])+"|"+str(record["week_cntp"])+"|"+str(record["week_cntu"])+"|"+str(record["day_cntp"])+"|"+str(record["day_cntu"])+"|\n"

    return msg + "||**Totals**|**"+str(totalp_cutoff)+"**||**"+str(totalp_month)+"**||**"+str(totalp_week)+"**||**"+str(totalp_day)+"**||"
