#!/usr/bin/env -S python3 -Bu
# Someone's Mattermost scripts.
#   Copyright (c) 2016-2025 by Someone <someone@somenet.org> (aka. Jan Vales <jan@jvales.net>)
#   published under MIT-License
#
# Custom profile badges.
#

import psycopg2
import psycopg2.extras
from inspect import cleandoc

import mattermost

import config

mm = mattermost.MMApi(config.mm_api_url)
mm.login(config.mm_user, config.mm_user_pw)

cfg = mm._get("/v4/config")
cfg["PluginSettings"]["Enable"] = True
cfg["PluginSettings"]["PluginStates"]["com.mattermost.custom-attributes"]["Enable"] = True
cfg["PluginSettings"]["Plugins"]["com.mattermost.custom-attributes"]["customattributes"] = []

# Im a bot!
bot_ids = [mm._my_user_id]
bot_ids.extend(config.bot_ids)
cfg["PluginSettings"]["Plugins"]["com.mattermost.custom-attributes"]["customattributes"].append({"Name": ":robot:[**``Bot (software agent)``**](https://en.wikipedia.org/wiki/Software_agent)", "UserIDs": bot_ids})


#####################################
# post-based badges + 2k+posts club #
#####################################
if hasattr(config, "dbconnstring") and hasattr(config, "club_team_id") and hasattr(config, "club_id") :
    dbconn = psycopg2.connect(config.dbconnstring)
    dbconn.set_session(autocommit=False)

    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT users.id AS id, username, count(*) AS posts, SUM(LENGTH(posts.message)) AS chars FROM posts JOIN users ON(users.id = userid)
                WHERE posts.userid != ALL(%(club_banned_uids)s) AND posts.deleteat = 0 AND NOT posts.props::jsonb @> '{"from_webhook":"true"}'::jsonb AND posts.createat > EXTRACT(EPOCH FROM (NOW() - INTERVAL '7 day'))*1000
                GROUP BY users.id, username ORDER BY posts DESC LIMIT 1
                """, {"club_banned_uids":config.club_banned_uids})
    sotw = cur.fetchall()[0]
    cfg["PluginSettings"]["Plugins"]["com.mattermost.custom-attributes"]["customattributes"].append({"Name": ":crown: **``Spammer of the week ("+str(sotw["posts"])+")``**", "UserIDs": [sotw["id"]]})

    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT users.id AS id, username, count(*) AS posts, SUM(LENGTH(posts.message)) AS chars FROM posts JOIN users ON(users.id = userid)
                WHERE posts.userid != ALL(%(club_banned_uids)s) AND posts.deleteat = 0 AND NOT posts.props::jsonb @> '{"from_webhook":"true"}'::jsonb AND posts.createat > EXTRACT(EPOCH FROM (NOW() - INTERVAL '7 day'))*1000
                GROUP BY users.id, username ORDER BY chars DESC LIMIT 1
                """, {"club_banned_uids":config.club_banned_uids})
    sotwc = cur.fetchall()[0]
    cfg["PluginSettings"]["Plugins"]["com.mattermost.custom-attributes"]["customattributes"].append({"Name": ":crown: **``Spammer of the week ("+str(sotwc["chars"])+")``**", "UserIDs": [sotwc["id"]]})


    pbb = [
        {"Name": "placeholder1", "UserIDs": []},
        {"Name": "placeholder2", "UserIDs": []},
        {"Name": "placeholder3", "UserIDs": []},
        {"Name": ":envelope::medal_sports:``50000+ posts``", "UserIDs": []},
        {"Name": ":envelope::medal_sports:``20000+ posts``", "UserIDs": []},
        {"Name": ":envelope::medal_sports:``10000+ posts``", "UserIDs": []},
        {"Name": ":envelope::medal_sports:``5000+ posts``", "UserIDs": []},
        {"Name": ":envelope::medal_sports:``2000+ posts``", "UserIDs": []},
        {"Name": ":envelope:``1000+ posts``", "UserIDs": []},
        {"Name": ":envelope:``500+ posts``", "UserIDs": []},
        {"Name": ":envelope:``200+ posts``", "UserIDs": []},
        {"Name": ":envelope:``100+ posts``", "UserIDs": []},
        {"Name": ":envelope:``50+ posts``", "UserIDs": []},
        {"Name": ":envelope:``10+ posts``", "UserIDs": []},
        {"Name": ":envelope::medal_military:``Less than 10 posts``", "UserIDs": []},
        ]

    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT users.id AS id, username, count(*) AS posts, SUM(LENGTH(posts.message)) AS chars FROM posts JOIN users ON(users.id = userid)
                WHERE posts.deleteat = 0 AND NOT posts.props::jsonb @> '{"from_webhook":"true"}'::jsonb AND posts.createat < EXTRACT(EPOCH FROM (NOW() - INTERVAL '7 day'))*1000
                GROUP BY users.id, username ORDER BY posts DESC
                """)
    last_week_post_pos = [[r["id"], r["posts"], r["chars"]] for r in cur.fetchall()]
    last_week_post_statsres = {x[0]:[x[1], x[2]] for x in last_week_post_pos}
    last_week_post_pos = [x[0] for x in last_week_post_pos if x[0] not in config.club_banned_uids]


    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT users.id AS id, username, count(*) AS posts, SUM(LENGTH(posts.message)) AS chars FROM posts JOIN users ON (users.id = userid)
                WHERE posts.deleteat = 0 AND NOT posts.props::jsonb @> '{"from_webhook":"true"}'::jsonb
                GROUP BY users.id, username ORDER BY posts DESC
                """)

    msg = cleandoc("""Post-Stats. #mmstats
    :crown: SOTW (Spammer-of-the-week): **@"""+sotw["username"]+"""** ("""+str(sotw["posts"])+""")

    :crown: SOTWbC (Spammer-of-the-week-by-chars): **@"""+sotwc["username"]+"""** ("""+str(sotwc["chars"])+""")

    |Rank|Username|Posts|Chars|Chars/post|Posts:7-day-diff|Chars:7-day-diff|
    |---:|----|---:|---:|---:|---:|---:|
    """)+"\n"
    rank = 0
    for record in cur.fetchall():
        # add/remove users to/from 2k+ posts club. The post count can decline e.g. if channels are deleted.
        if record["id"] in config.club_ignored_uids:
            continue

        if record["posts"] >= 2000 and record["id"] not in config.club_banned_uids:
            rank += 1
            mm.add_user_to_team(config.club_team_id, record["id"])
            mm.add_user_to_channel(config.club_id, record["id"])
            mm.update_channel_members_scheme_roles(config.club_id, record["id"], {"scheme_user": True, "scheme_admin": True})
        else:
            mm.remove_user_from_channel(config.club_id, record["id"], exc=False)

        # setrank based on post count
        if rank == 1 and record["id"] not in config.club_banned_uids:
            pbb[0] = {"Name": ":envelope::1st_place_medal: **``Top-user! ("+str(record["posts"])+" posts)``**", "UserIDs": [record["id"]]}
            msg += "|"+str(rank)+" ("+str(last_week_post_pos.index(record["id"])+1)+")|**``"+record["username"]+"``**|"+str(record["posts"])+"|"+str(record["chars"])+"|"+str(round(record["chars"]/record["posts"]))+"|"+str(record["posts"]-last_week_post_statsres[record["id"]][0])+"|"+str(record["chars"]-last_week_post_statsres[record["id"]][1])+"|\n"

        elif rank == 2 and record["id"] not in config.club_banned_uids:
            pbb[1] = {"Name": ":envelope::2nd_place_medal: **``Top-user! ("+str(record["posts"])+" posts)``**", "UserIDs": [record["id"]]}
            msg += "|"+str(rank)+" ("+str(last_week_post_pos.index(record["id"])+1)+")|**``"+record["username"]+"``**|"+str(record["posts"])+"|"+str(record["chars"])+"|"+str(round(record["chars"]/record["posts"]))+"|"+str(record["posts"]-last_week_post_statsres[record["id"]][0])+"|"+str(record["chars"]-last_week_post_statsres[record["id"]][1])+"|\n"

        elif rank == 3 and record["id"] not in config.club_banned_uids:
            pbb[2] = {"Name": ":envelope::3rd_place_medal: **``Top-user! ("+str(record["posts"])+" posts)``**", "UserIDs": [record["id"]]}
            msg += "|"+str(rank)+" ("+str(last_week_post_pos.index(record["id"])+1)+")|**``"+record["username"]+"``**|"+str(record["posts"])+"|"+str(record["chars"])+"|"+str(round(record["chars"]/record["posts"]))+"|"+str(record["posts"]-last_week_post_statsres[record["id"]][0])+"|"+str(record["chars"]-last_week_post_statsres[record["id"]][1])+"|\n"

        elif record["posts"] >= 50000 and record["id"] not in config.club_banned_uids:
            pbb[3]["UserIDs"].append(record["id"])
            msg += "|"+str(rank)+" ("+str(last_week_post_pos.index(record["id"])+1)+")|**``"+record["username"]+"``**|"+str(record["posts"])+"|"+str(record["chars"])+"|"+str(round(record["chars"]/record["posts"]))+"|"+str(record["posts"]-last_week_post_statsres[record["id"]][0])+"|"+str(record["chars"]-last_week_post_statsres[record["id"]][1])+"|\n"

        elif record["posts"] >= 20000 and record["id"] not in config.club_banned_uids:
            pbb[4]["UserIDs"].append(record["id"])
            msg += "|"+str(rank)+" ("+str(last_week_post_pos.index(record["id"])+1)+")|**``"+record["username"]+"``**|"+str(record["posts"])+"|"+str(record["chars"])+"|"+str(round(record["chars"]/record["posts"]))+"|"+str(record["posts"]-last_week_post_statsres[record["id"]][0])+"|"+str(record["chars"]-last_week_post_statsres[record["id"]][1])+"|\n"

        elif record["posts"] >= 10000 and record["id"] not in config.club_banned_uids:
            pbb[5]["UserIDs"].append(record["id"])
            msg += "|"+str(rank)+" ("+str(last_week_post_pos.index(record["id"])+1)+")|**``"+record["username"]+"``**|"+str(record["posts"])+"|"+str(record["chars"])+"|"+str(round(record["chars"]/record["posts"]))+"|"+str(record["posts"]-last_week_post_statsres[record["id"]][0])+"|"+str(record["chars"]-last_week_post_statsres[record["id"]][1])+"|\n"

        elif record["posts"] >= 5000 and record["id"] not in config.club_banned_uids:
            pbb[6]["UserIDs"].append(record["id"])
            msg += "|"+str(rank)+" ("+str(last_week_post_pos.index(record["id"])+1)+")|**``"+record["username"]+"``**|"+str(record["posts"])+"|"+str(record["chars"])+"|"+str(round(record["chars"]/record["posts"]))+"|"+str(record["posts"]-last_week_post_statsres[record["id"]][0])+"|"+str(record["chars"]-last_week_post_statsres[record["id"]][1])+"|\n"

        elif record["posts"] >= 2000 and record["id"] not in config.club_banned_uids:
            pbb[7]["UserIDs"].append(record["id"])
            msg += "|"+str(rank)+" ("+str(last_week_post_pos.index(record["id"])+1)+")|**``"+record["username"]+"``**|"+str(record["posts"])+"|"+str(record["chars"])+"|"+str(round(record["chars"]/record["posts"]))+"|"+str(record["posts"]-last_week_post_statsres[record["id"]][0])+"|"+str(record["chars"]-last_week_post_statsres[record["id"]][1])+"|\n"

        elif record["posts"] >= 1000:
            pbb[8]["UserIDs"].append(record["id"])
        elif record["posts"] >= 500:
            pbb[9]["UserIDs"].append(record["id"])
        elif record["posts"] >= 200:
            pbb[10]["UserIDs"].append(record["id"])
        elif record["posts"] >= 100:
            pbb[11]["UserIDs"].append(record["id"])
        elif record["posts"] >= 50:
            pbb[12]["UserIDs"].append(record["id"])
        elif record["posts"] >= 10:
            pbb[13]["UserIDs"].append(record["id"])
        elif record["posts"] >= 1:
            pbb[14]["UserIDs"].append(record["id"])

    cfg["PluginSettings"]["Plugins"]["com.mattermost.custom-attributes"]["customattributes"].extend(pbb)


###############################
# uid based badges (pre cmbb) #
###############################
for ubb_def in config.uid_based_bagdes_pre:
    cfg["PluginSettings"]["Plugins"]["com.mattermost.custom-attributes"]["customattributes"].append({"Name": ubb_def[0], "UserIDs": ubb_def[1]})


###################################
# channel-membership based badges #
###################################
for cmbb_def in config.channel_membership_based_bagdes:
    uids_in_channel = {u["user_id"] for u in mm.get_channel_members(cmbb_def[1])}
    uids_not_in_channel = set()
    if cmbb_def[2]:
        uids_not_in_channel = {u["user_id"] for u in mm.get_channel_members(cmbb_def[2])}

    uids = uids_in_channel - uids_not_in_channel - set(cmbb_def[3])
    cfg["PluginSettings"]["Plugins"]["com.mattermost.custom-attributes"]["customattributes"].append({"Name": cmbb_def[0], "UserIDs": list(uids)})


################################
# uid based badges (post cmbb) #
################################
for ubb_def in config.uid_based_bagdes_post:
    cfg["PluginSettings"]["Plugins"]["com.mattermost.custom-attributes"]["customattributes"].append({"Name": ubb_def[0], "UserIDs": ubb_def[1]})


########################
# set mm-server-config #
########################
mm._put("/v4/config", data=cfg)

# post 2k+posts stats to 2k+posts club channel.
if hasattr(config, "dbconnstring") and hasattr(config, "club_team_id") and hasattr(config, "club_id"):
    mm.create_post(config.club_id, msg)

mm.logout()
