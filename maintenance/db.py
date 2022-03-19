#!/usr/bin/env -S python3 -Bu
# Someone's Mattermost maintenance scripts.
#   Copyright (c) 2016-2022 by Someone <someone@somenet.org> (aka. Jan Vales <jan@jvales.net>)
#   published under MIT-License
#
# Permanently delete {"deleted",orphaned,old,unused} db-data. Also fix some of MM's db-health degrading bugs/stuff. And enforce our system policy.
#
# Some code is duplicated - could not decide what to stick with - also its for the stats! :)
#

import sys
import time
import psycopg2
import psycopg2.extras

import config
print("Mattermost DB cleanup script: https://git.somenet.org/pub/jan/mattermost-privileged.git")
print("Tested on 6.5\n")

dbconn = psycopg2.connect(config.dbconnstring)
dbconn.set_session(autocommit=False)


TS_START = time.time()

#########################
# enforce system policy #
#########################
print("Enforcing system policy ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

## 31 days+ not active guests (no recent status, no recent account update, no recent posts)
#cur.execute("""DELETE FROM users WHERE users.id IN
#            (SELECT users.id FROM users LEFT JOIN status ON (users.id = status.userid AND lastactivityat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000)
#               WHERE roles like '%system_guest%' AND users.updateat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND users.id NOT IN (SELECT distinct userid FROM posts WHERE createat > extract(epoch from (NOW() - INTERVAL '31 day'))*1000)
#            ) RETURNING *""")
#print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 31 days+ not used guest-account(s).")
#_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# 31 days+ not active and not verified users (no recent status, no recent account update, no recent posts)
cur.execute("""DELETE FROM users WHERE users.id IN
            (SELECT users.id FROM users LEFT JOIN status ON (users.id = status.userid AND lastactivityat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000)
              WHERE emailverified = false AND users.updateat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND users.id NOT IN (SELECT distinct userid FROM posts WHERE createat > extract(epoch from (NOW() - INTERVAL '31 day'))*1000)
            ) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 31 days+ not verified account(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# 12 months inactive non-public one-user-channels (mostly DM-channels where the other user was deleted; they are inaccessible for the other user anyway)
cur.execute("""DELETE FROM channels WHERE type IS DISTINCT FROM 'O' AND lastpostat < extract(epoch from (NOW() - INTERVAL '12 month'))*1000 AND updateat < extract(epoch from (NOW() - INTERVAL '12 month'))*1000 AND
            id IN (SELECT id FROM (SELECT count(id) as cnt, id FROM channels LEFT JOIN channelmembers ON (id = channelid) GROUP BY id) AS a WHERE cnt < 2)
            RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 12 months+ inactive non-public one-user-channel(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# bot breaking channels in vowi team
cur.execute("""DELETE FROM channels WHERE teamid = 'sswtb6oqciyyfmkibh6mjz479w' AND type = 'O' AND creatorid NOT IN ('5ugpycz1mfrj3ff4k6hbg6g37o', '') RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted breaking channel(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]


cur.close()
if not hasattr(config, "enforce_system_policy") or hasattr(config, "enforce_system_policy") and not config.enforce_system_policy:
    dbconn.rollback()
    print("\n*** rollback - not enforcing system policy ***")
print()



####################################
# Delete ``AUTODELETE-*`` messages #
####################################
if hasattr(config, "del_autodelete") and config.del_autodelete:
    print("Deleting ``AUTODELETE-*`` messages ...")
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # delete autodelete-messages by message content
    cur.execute("""DELETE FROM posts WHERE ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '2 day'))*1000 AND message LIKE '``AUTODELETE-DAY``%' RETURNING *""")
    print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old AUTODELETE-DAY message(s).")
    cur.execute("""DELETE FROM posts WHERE ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '7 day'))*1000 AND message LIKE '``AUTODELETE-WEEK``%' RETURNING *""")
    print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old AUTODELETE-WEEK message(s).")
    cur.execute("""DELETE FROM posts WHERE ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND message LIKE '``AUTODELETE%``%' RETURNING *""")
    print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old AUTODELETE-MONTH message(s).")

    # delete autodelete-messages by property. We need an index to make this **really** fast... # Dont!
    # CREATE INDEX someone_idx_posts_props_autodelete ON public.posts USING btree ((props::jsonb ->> 'somemaint_auto_delete'::text) COLLATE pg_catalog."default");
    cur.execute("""DELETE FROM posts WHERE ispinned = false AND props::text LIKE '%somecleaner_autodelete%' AND createat < extract(epoch from (NOW() - INTERVAL '1 day'))*1000 AND props::jsonb ->> 'somecleaner_autodelete' = 'day' RETURNING *""")
    print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old AUTODELETE-PROP-DAY message(s).")
    cur.execute("""DELETE FROM posts WHERE ispinned = false AND props::text LIKE '%somecleaner_autodelete%' AND createat < extract(epoch from (NOW() - INTERVAL '7 day'))*1000 AND props::jsonb ->> 'somecleaner_autodelete' = 'week' RETURNING *""")
    print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old AUTODELETE-PROP-WEEK message(s).")
    cur.execute("""DELETE FROM posts WHERE ispinned = false AND props::text LIKE '%somecleaner_autodelete%' AND createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND props::jsonb ? 'somecleaner_autodelete' RETURNING *""")
    print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old AUTODELETE-PROP-MONTH message(s).")

    cur.close()
else:
    print("SKIPPED deleting ``AUTODELETE-*`` messages ...")

print()



##################################
# Delete old unused/history data #
##################################
print("Deleting old unused/history data ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# unused DM/Group channels (mostly created implicitly)
cur.execute("""DELETE FROM channels WHERE totalmsgcount = 0 AND type IN ('D', 'G') AND updateat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted unused (implicitly created) DM/Group channel(s).")

# old audit entries
cur.execute("""DELETE FROM audits WHERE createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old audit entries.")

# old job entries
cur.execute("""DELETE FROM jobs WHERE createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND status = 'success' RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old job entries.")

# old linkmetadata entries
cur.execute("""DELETE FROM linkmetadata WHERE timestamp < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old linkmetadata entries.")

# channelmemberhistory of left members
cur.execute("""DELETE FROM channelmemberhistory WHERE leavetime < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted old channelmemberhistory entries.")


cur.close()
print()



####################################
# Delete 'deleted'/'archived' data #
####################################
print("Deleting 'deleted'/'archived' entries ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# posts
cur.execute("""DELETE FROM posts WHERE deleteat IS DISTINCT FROM 0 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 'deleted' post(s).")

# channels
cur.execute("""DELETE FROM channels WHERE deleteat IS DISTINCT FROM 0 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 'deleted' channel(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# emojis
cur.execute("""DELETE FROM emoji WHERE deleteat IS DISTINCT FROM 0 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 'deleted' emoji(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# reactions - MM 5.33 started soft-deleting them :/
cur.execute("""DELETE FROM reactions WHERE deleteat IS DISTINCT FROM 0 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 'deleted' reaction(s).")

# teammembers
cur.execute("""DELETE FROM teammembers WHERE deleteat IS DISTINCT FROM 0 OR (schemeuser = FALSE AND schemeadmin = FALSE AND schemeguest = FALSE) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 'deleted' teammember(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# slash commands
cur.execute("""DELETE FROM commands WHERE deleteat IS DISTINCT FROM 0 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 'deleted' slash command(s).")

# outgoing hooks
cur.execute("""DELETE FROM outgoingwebhooks WHERE deleteat IS DISTINCT FROM 0 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 'deleted' outgoing webhook(s).")

# incomming hooks
cur.execute("""DELETE FROM incomingwebhooks WHERE deleteat IS DISTINCT FROM 0 RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted 'deleted' incoming webhook(s).")


cur.close()
print()



#######################
# clean orphaned data #
#######################
print("Deleting orphaned entries ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# empty private channels
cur.execute("""DELETE FROM channels WHERE id NOT IN (SELECT channelid FROM channelmembers) AND type = 'P' RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned private channel(s).")

# posts orphaned by channel + user
cur.execute("""DELETE FROM posts WHERE channelid NOT IN (SELECT id FROM channels) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned post(s).")

# posts orphaned by root post (fixing my own shit; only happens because of AUTODELETE)
cur.execute("""DELETE FROM posts WHERE rootid IS DISTINCT FROM '' AND rootid NOT IN (SELECT id FROM posts) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned post-comment(s).")

# threads
cur.execute("""DELETE FROM threads WHERE postid NOT IN (SELECT id FROM posts) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned thread(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# threadmembers
cur.execute("""DELETE FROM threadmemberships WHERE postid NOT IN (SELECT id FROM posts) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned threadmembership(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# reactions orphaned by post + user
cur.execute("""DELETE FROM reactions WHERE postid NOT IN (SELECT id FROM posts) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned reaction(s).")

# channelmembers orphaned by channel + user
cur.execute("""DELETE FROM channelmembers WHERE channelid NOT IN (SELECT id FROM channels) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned channelmember(s).")

# channelmemberhisroty orphaned by channel + user
cur.execute("""DELETE FROM channelmemberhistory WHERE channelid NOT IN (SELECT id FROM channels) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned channelmemberhistory entr(y/ies).")

# teammembers
cur.execute("""DELETE FROM teammembers WHERE userid NOT IN (SELECT id FROM users) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned teammember(s).")

# online-status
cur.execute("""DELETE FROM status WHERE userid NOT IN (SELECT id FROM users) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned user status entr(y/ies).")

# sidebarchannels orphaned by channel deletion
cur.execute("""DELETE FROM sidebarchannels WHERE channelid NOT IN (SELECT id FROM channels) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned sidebarchannel entr(y/ies).")

# sidebarchannels orphaned by category deletion - does this really happen?
cur.execute("""DELETE FROM sidebarchannels WHERE categoryid NOT IN (SELECT id FROM sidebarcategories) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned sidebarchannel entr(y/ies) by category-delete. does this happen?")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]

# sessions of not verified, or deleted users (likely always noop)
cur.execute("""DELETE FROM sessions WHERE userid NOT IN (SELECT id FROM users WHERE emailverified IS TRUE) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned session(s).")

# slash commands by team
cur.execute("""DELETE FROM commands WHERE teamid NOT IN (SELECT id FROM teams) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned slash command(s).")

# filereferences (keep last)
cur.execute("""DELETE FROM fileinfo WHERE id NOT IN
            (SELECT unnest(string_to_array(replace(replace(replace(fileids, '"', ''), ']', ''), '[', ''), ',')) FROM posts WHERE fileids IS DISTINCT FROM '[]')
            RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned file reference(s).")

# space for settings
print()


# orphaned preferences by User
cur.execute("""DELETE FROM preferences WHERE userid NOT IN (select id FROM users) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned preference(s).")

# orphaned preferences: open channel info entries
cur.execute("""DELETE FROM preferences WHERE category = 'direct_channel_show' AND name NOT IN (select id FROM users) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned direct_channel_show preference(s).")

# orphaned preferences: deleted viewved channel info
cur.execute("""DELETE FROM preferences WHERE category = 'channel_approximate_view_time' AND name NOT IN (select id FROM channels union select '') RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned channel_approximate_view_time preference(s).")

# orphaned preferences: deleted fav'ed channel info
cur.execute("""DELETE FROM preferences WHERE category = 'favorite_channel' AND name NOT IN (select id FROM channels) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned favorite_channel preference(s).")

# orphaned preferences: deleted flagged posts
cur.execute("""DELETE FROM preferences WHERE category = 'flagged_post' AND name NOT IN (select id FROM posts) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted orphaned flagged_post preference(s).")


cur.close()
print()



################################
# Soft-delete system messages. #
################################
if hasattr(config, "softdel_systemspam") and config.softdel_systemspam:
    print("'Deleting' system messages ...")
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""UPDATE posts SET deleteat=extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat=extract(epoch FROM(date_trunc('second',NOW())))*1000
            WHERE type IN ('system_join_team','system_leave_team','system_add_to_team','system_remove_from_team','system_join_channel','system_leave_channel','system_purpose_change','system_header_change','system_guest_join_channel')
            OR (type IN ('system_add_to_channel','system_add_guest_to_chan') AND props::jsonb @> '{"userId":"5ugpycz1mfrj3ff4k6hbg6g37o"}'::jsonb)
            RETURNING *""")
    print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" 'deleted' system spam message(s).")

    cur.close()
else:
    print("SKIPPED 'Deleting' system messages ...")

print()



########################
# fix db-health issues #
########################
print("Fixing stuff ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# "rematerialize" materialized "view": publicchannels
cur.execute("""TRUNCATE publicchannels""")
cur.execute("""INSERT INTO publicchannels (id, deleteat, teamid, displayname, name, header, purpose) SELECT c.id, c.deleteat, c.teamid, c.displayname, c.name, c.header, c.purpose FROM channels c WHERE c.type = 'O'""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" inserted public channel(s) into 'materialized view'.")

# FIX: delete public channels from dm/group-channel list
cur.execute("""DELETE FROM preferences WHERE category = 'group_channel_show' AND name IN (SELECT id FROM channels WHERE type NOT IN ('G','D')) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" deleted public channel group_channel_show preference(s). THIS IS A BUGFIX. SHOULD BE 0!")

# FIX: make guests converted to users not join any channel "as guest". github: https://github.com/mattermost/mattermost-server/issues/14821
cur.execute("""UPDATE channelmembers SET schemeuser=True, schemeguest=False FROM users WHERE channelmembers.userid = users.id AND schemeguest = True AND 'system_guest' != users.roles RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" corrected joins 'as guest' to channels for now-users. THIS IS A BUGFIX. SHOULD BE 0!")

# FIX: regenerate participants list in threads table - migration issue of old threads. github: https://github.com/mattermost/mattermost-server/issues/16320
# TODO? Unknown use of said table -> wait for next thread release phase?

# FIX: recalculate postcount to exclude deleted posts in threads table - migration issue of old threads. github: https://github.com/mattermost/mattermost-server/issues/16321
# TODO. easyly fixable, but unknown use of said table -> wait for next threads release phase?

# remove "disable_group_highlight" prop from posts.
cur.execute("""UPDATE posts SET props=props::jsonb - 'disable_group_highlight' WHERE props::jsonb ? 'disable_group_highlight' RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" removed 'disable_group_highlight' prop from post(s).")

# order channels list alphabetically again
cur.execute("""UPDATE sidebarcategories SET sorting='' WHERE type ='channels' AND sorting != '' RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" type=channel sidebarcategory reverted sorting to alphabetical.")
cur.execute("""DELETE FROM sidebarchannels WHERE sidebarchannels.categoryid IN (SELECT id FROM sidebarcategories WHERE type = 'channels') RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" removed type=channel sidebarchannels sorting information.")

# channel totalmsgcount (MM updates totalmsgcount for non-system-posts only)
cur.execute("""UPDATE channels SET totalmsgcount = sq.cnt, totalmsgcountroot = sq.cntroot FROM (
                SELECT COUNT(posts.id) AS cnt, SUM(CASE WHEN NOT posts.id isNULL AND (posts.rootid = '' OR posts.rootid isNULL) THEN 1 ELSE 0 END) AS cntroot, channels.id AS id
                FROM posts RIGHT JOIN channels ON (posts.channelid = channels.id AND posts.type NOT LIKE 'system_%') GROUP BY channels.id) AS sq
            WHERE channels.id = sq.id and (totalmsgcount IS DISTINCT FROM sq.cnt OR totalmsgcountroot IS DISTINCT FROM sq.cntroot)
            RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" updated channel totalmsgcount(root).")

# channel lastpostat for non-empty channels only (MM updates lastpostat for every post, incl. systemposts)
cur.execute("""UPDATE channels SET lastpostat = sq.pt
            FROM (SELECT coalesce(max(posts.createat), channels.updateat) AS pt, channels.id AS id FROM posts JOIN channels ON (posts.channelid = channels.id) GROUP BY channels.id) AS sq
            WHERE channels.id = sq.id and lastpostat IS DISTINCT FROM sq.pt
            RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" updated non-empty channel lastpostat.")

# remove prop:"{"disable_group_highlight":true}" - its only set by the webapp, not by the android app. Doing... unsure what.
#cur.execute("""UPDATE posts SET props='{}' WHERE props='{"disable_group_highlight":true}' RETURNING *""")
#print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" removed obscure post-properti(y/ies).")

# good enough approach: channelmembers msgcount and lastviewedat (mm sometimes checks diffrences in msg counts and sometimes its lastviewedat. 0 for both is ok)
cur.execute("""UPDATE channelmembers SET msgcount = totalmsgcount, msgcountroot = totalmsgcountroot, lastviewedat = lastpostat FROM channels
            WHERE channelid = channels.id AND (msgcount > totalmsgcount OR msgcountroot > totalmsgcountroot OR lastviewedat > lastpostat) RETURNING *""")
print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" updated channelmember msgcount(root)/lastviewedat. (good enough)")

# perfect: channelmembers msgcount and lastviewedat (mm sometimes checks diffrences in msg counts and sometimes its lastviewedat. 0 for both is ok)
#cur.execute("UPDATE channelmembers SET msgcount = sq.cnt, lastviewedat = sq.pt FROM ( "
#            "SELECT count(posts.id) AS cnt, max(coalesce(posts.createat, 0)) AS pt, channels.id AS cid, channelmembers.userid AS uid "
#            "  FROM channelmembers LEFT JOIN channels ON (channelmembers.channelid = channels.id) LEFT JOIN posts ON (posts.channelid = channels.id AND posts.type NOT LIKE 'system_%' AND channelmembers.lastviewedat >= posts.createat) "
#            "  GROUP BY channels.id, channelmembers.userid "
#            ") AS sq WHERE channelid = sq.cid AND userid = sq.uid AND (msgcount IS DISTINCT FROM sq.cnt OR lastviewedat IS DISTINCT FROM sq.pt) RETURNING *")
#print("* ["+("%07.6g"%round(time.time() - TS_START, 5))+"] "+str(cur.rowcount)+" updated channelmember msgcount/lastviewedat. (perfect)")

cur.close()
print()



##################################
# commit changes, print db size. #
##################################
if hasattr(config, "dry_run") and config.dry_run:
    dbconn.rollback()
    print("*** rollback - dry_run ***\n")
else:
    dbconn.commit()
    print("*** committed ***\n")

cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cur.execute("""SELECT pg_size_pretty(pg_database_size(current_database())) AS size""")
print("* db-size: "+cur.fetchall()[0]["size"]+"\n")

dbconn.close()
