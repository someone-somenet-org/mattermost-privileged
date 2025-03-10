#!/usr/bin/env -S python3 -Bu
# Someone's Mattermost maintenance scripts.
#   Copyright (c) 2016-2025 by Someone <someone@somenet.org> (aka. Jan Vales <jan@jvales.net>)
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
print("Tested on 10.5\n")

dbconn = psycopg2.connect(config.dbconnstring)
dbconn.set_session(autocommit=False)


TS_START = time.time()

#########################
# enforce system policy #
#########################
print("Enforcing system policy ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# 31 days+ not active and not verified users (no recent status, no recent account update, no recent posts)
cur.execute("""DELETE FROM users WHERE users.id IN
            (SELECT users.id FROM users LEFT JOIN status ON (users.id = status.userid AND lastactivityat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000)
              WHERE emailverified = false AND users.updateat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND users.id NOT IN (SELECT distinct userid FROM posts WHERE createat > extract(epoch from (NOW() - INTERVAL '31 day'))*1000)
            ) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 31 days+ not verified account(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]


## 91 days+ not active guest accounts (no recent status, no recent account update, no recent posts)
cur.execute("""UPDATE posts SET userid = '"""+config.deleted_user_uid+"""' WHERE userid IN (SELECT id FROM (
                SELECT users.id, users.username, users.email, status.status, status.manual, date_trunc('second',TO_TIMESTAMP(GREATEST(status.lastactivityat, MAX(sessions.lastactivityat), users.updateat)/1000)) as lastactivity
                FROM users LEFT JOIN status ON (users.id = status.userid) LEFT JOIN sessions ON (users.id = sessions.userid)
                WHERE users.roles like '%system_guest%' GROUP BY users.id, users.username, users.email, status.status, status.manual, status.lastactivityat, users.updateat ORDER BY lastactivity DESC
            ) A where extract(epoch from lastactivity)*1000 < extract(epoch from (NOW() - INTERVAL '91 day'))*1000
            ) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} chowned 91 days+ not used guest-account(s) public post(s).")

cur.execute("""DELETE FROM users WHERE id IN (SELECT id FROM (
                SELECT users.id, users.username, users.email, status.status, status.manual, date_trunc('second',TO_TIMESTAMP(GREATEST(status.lastactivityat, MAX(sessions.lastactivityat), users.updateat)/1000)) as lastactivity
                FROM users LEFT JOIN status ON (users.id = status.userid) LEFT JOIN sessions ON (users.id = sessions.userid)
                WHERE users.roles like '%system_guest%' GROUP BY users.id, users.username, users.email, status.status, status.manual, status.lastactivityat, users.updateat ORDER BY lastactivity DESC
            ) A where extract(epoch from lastactivity)*1000 < extract(epoch from (NOW() - INTERVAL '91 day'))*1000
            ) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 91 days+ not used guest-account(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]


## 48 months+ not active accounts (no recent status, no recent account update, no recent posts)
cur.execute("""UPDATE posts SET userid = '"""+config.deleted_user_uid+"""' WHERE userid IN (SELECT id FROM (
                SELECT users.id, users.username, users.email, status.status, status.manual, date_trunc('second',TO_TIMESTAMP(GREATEST(status.lastactivityat, MAX(sessions.lastactivityat), users.updateat)/1000)) as lastactivity
                FROM users LEFT JOIN status ON (users.id = status.userid) LEFT JOIN sessions ON (users.id = sessions.userid)
                GROUP BY users.id, users.username, users.email, status.status, status.manual, status.lastactivityat, users.updateat ORDER BY lastactivity DESC
            ) A where extract(epoch from lastactivity)*1000 < extract(epoch from (NOW() - INTERVAL '48 month'))*1000
            ) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} chowned 48 months+ not used account(s) public post(s).")

cur.execute("""DELETE FROM users WHERE id IN (SELECT id FROM (
                SELECT users.id, users.username, users.email, status.status, status.manual, date_trunc('second',TO_TIMESTAMP(GREATEST(status.lastactivityat, MAX(sessions.lastactivityat), users.updateat)/1000)) as lastactivity
                FROM users LEFT JOIN status ON (users.id = status.userid) LEFT JOIN sessions ON (users.id = sessions.userid)
                GROUP BY users.id, users.username, users.email, status.status, status.manual, status.lastactivityat, users.updateat ORDER BY lastactivity DESC
            ) A where extract(epoch from lastactivity)*1000 < extract(epoch from (NOW() - INTERVAL '48 month'))*1000
            ) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 48 months+ not used account(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]


## 91 days+ disabled accounts
#cur.execute("""UPDATE posts SET userid = '"""+config.deleted_user_uid+"""' WHERE userid IN (SELECT id FROM users WHERE users.deleteat <> 0 AND deleteat < extract(epoch from (NOW() - INTERVAL '91 day'))*1000) RETURNING *""")
#print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} chown 91 days+ disabled account(s) public post(s).")
#
#cur.execute("""DELETE FROM users WHERE users.deleteat <> 0 AND deleteat < extract(epoch from (NOW() - INTERVAL '91 day'))*1000 RETURNING *""")
#print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 91 days+ disabled account(s).")
#_ = [print(row, file=sys.stderr) for row in cur.fetchall()]


# move channel-creatorship of deleted users to deleted_user
cur.execute("""UPDATE channels SET creatorid = '"""+config.deleted_user_uid+"""' WHERE creatorid NOT IN (SELECT id FROM users) AND creatorid != '' RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} chowned channel-creatorship(s) of deleted users to deleted_user.")


# 12 months inactive non-public one-user-channels (mostly DM-channels where the other user was deleted; they are inaccessible for the other user anyway)
cur.execute("""DELETE FROM channels WHERE type IS DISTINCT FROM 'O' AND lastpostat < extract(epoch from (NOW() - INTERVAL '12 month'))*1000 AND updateat < extract(epoch from (NOW() - INTERVAL '12 month'))*1000 AND
            id IN (SELECT id FROM (SELECT count(id) as cnt, id FROM channels LEFT JOIN channelmembers ON (id = channelid) GROUP BY id) AS a WHERE cnt < 2)
            RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 12 months+ inactive non-public one-user-channel(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]


# bot breaking channels in vowi team
cur.execute("""DELETE FROM channels WHERE teamid = 'sswtb6oqciyyfmkibh6mjz479w' AND type = 'O' AND creatorid NOT IN ('5ugpycz1mfrj3ff4k6hbg6g37o', '') RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted breaking channel(s).")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]


cur.close()
if not hasattr(config, "enforce_system_policy") or hasattr(config, "enforce_system_policy") and not config.enforce_system_policy:
    dbconn.rollback()
    print("\n*** rollback - not enforcing system policy ***")
print()



##################################
# Delete old unused/history data #
##################################
print("Deleting old unused/history data ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# old audit entries
cur.execute("""DELETE FROM audits WHERE createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted old audit entries.")

# old job entries
cur.execute("""DELETE FROM jobs WHERE createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND status = 'success' RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted old job entries.")

# old linkmetadata entries
cur.execute("""DELETE FROM linkmetadata WHERE timestamp < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted old linkmetadata entries.")

# channelmemberhistory of left members
cur.execute("""DELETE FROM channelmemberhistory WHERE leavetime < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted old channelmemberhistory entries.")


cur.close()
print()



####################################
# Delete 'deleted'/'archived' data #
####################################
print("Deleting 'deleted'/'archived' entries ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# posts
cur.execute("""DELETE FROM posts WHERE deleteat <> 0 AND deleteat < extract(epoch from (NOW() - INTERVAL '14 day'))*1000 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' post(s).")

# drafts
cur.execute("""DELETE FROM drafts WHERE deleteat <> 0 OR message = '' RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' draft(s).")

# channels
cur.execute("""DELETE FROM channels WHERE deleteat <> 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' channel(s).")

# emojis
cur.execute("""DELETE FROM emoji WHERE deleteat <> 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' emoji(s).")

# reactions - MM 5.33 started soft-deleting them :/
cur.execute("""DELETE FROM reactions WHERE deleteat <> 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' reaction(s).")

# teammembers
cur.execute("""DELETE FROM teammembers WHERE deleteat <> 0 OR (schemeuser = FALSE AND schemeadmin = FALSE AND schemeguest = FALSE) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' teammember(s).")

# usergroups
cur.execute("""DELETE FROM usergroups WHERE deleteat <> 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' usergroup(s).")

# usergroup members
cur.execute("""DELETE FROM groupmembers WHERE deleteat <> 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' usergroupmember(s).")

# slash commands
cur.execute("""DELETE FROM commands WHERE deleteat <> 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' slash command(s).")

# outgoing hooks
cur.execute("""DELETE FROM outgoingwebhooks WHERE deleteat <> 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' outgoing webhook(s).")

# incoming hooks
cur.execute("""DELETE FROM incomingwebhooks WHERE deleteat <> 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted 'deleted' incoming webhook(s).")


cur.close()
print()



#######################
# clean orphaned data #
#######################
print("Deleting orphaned entries ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# slash commands by team
cur.execute("""DELETE FROM commands WHERE teamid NOT IN (SELECT id FROM teams) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned slash command(s).")

# channels by team
cur.execute("""DELETE FROM channels WHERE teamid NOT IN (SELECT id FROM teams) and teamid IS DISTINCT FROM '' RETURNING *""")
_ = [print(row, file=sys.stderr) for row in cur.fetchall()]
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned channel(s).")

# empty private channels
cur.execute("""DELETE FROM channels WHERE id NOT IN (SELECT channelid FROM channelmembers) AND type = 'P' RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned private channel(s).")

# posts orphaned by channel + user
cur.execute("""DELETE FROM posts WHERE channelid NOT IN (SELECT id FROM channels) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned post(s).")

# posts orphaned by root post (fixing my own shit; only happens because of AUTODELETE)
cur.execute("""DELETE FROM posts WHERE rootid IS DISTINCT FROM '' AND rootid NOT IN (SELECT id FROM posts) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned post-comment(s).")

# threads orphaned by post + being emptied (by channel happens automatically because of post orphaning)
cur.execute("""DELETE FROM threads WHERE postid NOT IN (SELECT id FROM posts) OR replycount = 0 RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned thread(s).")

# threadmembers by thread + post + user
cur.execute("""DELETE FROM threadmemberships WHERE postid NOT IN (SELECT postid FROM threads) OR postid NOT IN (SELECT id FROM posts) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned threadmembership(s).")

# reactions orphaned by post + user
cur.execute("""DELETE FROM reactions WHERE postid NOT IN (SELECT id FROM posts) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned reaction(s).")

# postspriorities orphaned by post (by channel happens automatically because of post orphaning)
cur.execute("""DELETE FROM postspriority WHERE postid NOT IN (SELECT id FROM posts) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned postspriorit(y/ies).")

# postacknowledgements orphaned by post + user
cur.execute("""DELETE FROM postacknowledgements WHERE postid NOT IN (SELECT id FROM posts) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned postacknowledgement(s). (needed?)")

# channelmembers orphaned by channel + user
cur.execute("""DELETE FROM channelmembers WHERE channelid NOT IN (SELECT id FROM channels) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned channelmember(s).")

# channelmemberhisroty orphaned by channel + user
cur.execute("""DELETE FROM channelmemberhistory WHERE channelid NOT IN (SELECT id FROM channels) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned channelmemberhistory entr(y/ies).")

# teammembers by user
cur.execute("""DELETE FROM teammembers WHERE userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned teammember(s).")

# groupmembers orphanes by group + user
cur.execute("""DELETE FROM groupmembers WHERE groupid NOT IN (SELECT id FROM usergroups) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned usergroupmember(s).")

# online-status
cur.execute("""DELETE FROM status WHERE userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned user status entr(y/ies).")

# sidebarcategories orphaned by team + user
cur.execute("""DELETE FROM sidebarcategories WHERE teamid NOT IN (SELECT id FROM teams) OR userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned sidebarcategor(y/ies).")

# sidebarchannels orphaned by channel + sidebarcategory
cur.execute("""DELETE FROM sidebarchannels WHERE channelid NOT IN (SELECT id FROM channels) OR categoryid NOT IN (SELECT id FROM sidebarcategories) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned sidebarchannel entr(y/ies).")

# sessions by user
cur.execute("""DELETE FROM sessions WHERE userid NOT IN (SELECT id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned session(s).")

# filereferences (keep last)
cur.execute("""DELETE FROM fileinfo WHERE id NOT IN
            (SELECT unnest(string_to_array(replace(replace(replace(fileids, '"', ''), ']', ''), '[', ''), ',')) FROM posts WHERE fileids IS DISTINCT FROM '[]')
            RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned file reference(s).")


# space for settings
print()


# orphaned preferences by user
cur.execute("""DELETE FROM preferences WHERE userid NOT IN (select id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned preference(s).")

# orphaned preferences: open channel info entries by user
cur.execute("""DELETE FROM preferences WHERE category = 'direct_channel_show' AND name NOT IN (select id FROM users) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned direct_channel_show preference(s).")

# orphaned preferences: deleted viewved channel info by user
cur.execute("""DELETE FROM preferences WHERE category = 'channel_approximate_view_time' AND name NOT IN (select id FROM channels union select '') RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned channel_approximate_view_time preference(s).")

# orphaned preferences: deleted fav'ed channel info by user
cur.execute("""DELETE FROM preferences WHERE category = 'favorite_channel' AND name NOT IN (select id FROM channels) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned favorite_channel preference(s).")

# orphaned preferences: deleted flagged posts by user
cur.execute("""DELETE FROM preferences WHERE category = 'flagged_post' AND name NOT IN (select id FROM posts) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted orphaned flagged_post preference(s).")


cur.close()
print()



################################
# Soft-delete system messages. #
################################
if hasattr(config, "softdel_systemspam") and config.softdel_systemspam:
    print("'Deleting' system messages ...")
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
            WHERE (deleteat = 0 OR deleteat IS NULL) AND (
                type IN ('system_join_team','system_leave_team','system_add_to_team','system_remove_from_team','system_join_channel','system_leave_channel','system_purpose_change','system_header_change','system_guest_join_channel')
                OR (type IN ('system_add_to_channel','system_add_guest_to_chan') AND props::jsonb @> '{"userId":"5ugpycz1mfrj3ff4k6hbg6g37o"}'::jsonb)
            ) RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' system spam message(s).")


    cur.close()
else:
    print("SKIPPED 'Deleting' system messages ...")

print()



#########################################
# Soft-delete ``AUTODELETE-*`` messages #
#########################################
if hasattr(config, "softdel_autodelete") and config.softdel_autodelete:
    print("'Deleting' ``AUTODELETE-*`` messages ...")
    cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # delete autodelete-messages by message content
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '2 day'))*1000 AND message LIKE '``BOT-AUTODELETE-DAY``%' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old BOT-AUTODELETE-DAY message(s).")
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '7 day'))*1000 AND message LIKE '``BOT-AUTODELETE-WEEK``%' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old BOT-AUTODELETE-WEEK message(s).")
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND message LIKE '``AUTODELETE%``%' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old BOT-AUTODELETE-MONTH message(s).")

    # delete autodelete-messages by message content
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '2 day'))*1000 AND message LIKE '``AUTODELETE-DAY``%' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old AUTODELETE-DAY message(s).")
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '7 day'))*1000 AND message LIKE '``AUTODELETE-WEEK``%' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old AUTODELETE-WEEK message(s).")
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND message LIKE '``AUTODELETE%``%' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old AUTODELETE-MONTH message(s).")

    # delete autodelete-messages by property. We need an index to make this **really** fast... # Dont!
    # CREATE INDEX someone_idx_posts_props_autodelete ON public.posts USING btree ((props::jsonb ->> 'somemaint_auto_delete'::text) COLLATE pg_catalog."default");
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND props::text LIKE '%somecleaner_autodelete%' AND createat < extract(epoch from (NOW() - INTERVAL '1 day'))*1000 AND props::jsonb ->> 'somecleaner_autodelete' = 'day' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old AUTODELETE-PROP-DAY message(s).")
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND props::text LIKE '%somecleaner_autodelete%' AND createat < extract(epoch from (NOW() - INTERVAL '7 day'))*1000 AND props::jsonb ->> 'somecleaner_autodelete' = 'week' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old AUTODELETE-PROP-WEEK message(s).")
    cur.execute("""UPDATE posts SET deleteat = extract(epoch FROM(date_trunc('second',NOW())))*1000, updateat = extract(epoch FROM(date_trunc('second',NOW())))*1000
        WHERE (deleteat = 0 OR deleteat IS NULL) AND ispinned = false AND props::text LIKE '%somecleaner_autodelete%' AND createat < extract(epoch from (NOW() - INTERVAL '31 day'))*1000 AND props::jsonb ? 'somecleaner_autodelete' RETURNING *""")
    print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} 'deleted' old AUTODELETE-PROP-MONTH message(s).")


    cur.close()
else:
    print("SKIPPED deleting ``AUTODELETE-*`` messages ...")

print()



####################################
# fix self-caused-db-health issues #
####################################
print("Fixing self-caused stuff ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# mark threads as deleted if their root post is deleted.
cur.execute("""UPDATE threads SET threaddeleteat = a.deleteat FROM (SELECT id AS pid, deleteat FROM posts WHERE deleteat <> 0) AS a WHERE postid = a.pid AND (threaddeleteat = 0 OR threaddeleteat IS NULL) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} corrected thread deletion(s).")

# soft-delete posts that belong to a deleted post/thread.
cur.execute("""WITH deleted_top_posts AS (SELECT * FROM posts WHERE deleteat <> 0) UPDATE posts SET deleteat = deleted_top_posts.deleteat FROM deleted_top_posts
            WHERE posts.rootid = deleted_top_posts.id AND (posts.deleteat = 0 OR posts.deleteat IS NULL) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} corrected post deletions of deleted thread(s).")


# regenerate thread replycount and participants.
cur.execute("""UPDATE threads SET replycount = a.cnt, participants=a.part FROM (SELECT rootid, COUNT(*) cnt, json_agg(distinct userid) part FROM posts WHERE rootid IN (SELECT postid FROM threads) GROUP BY 1) AS a
			WHERE threads.postid=a.rootid AND (replycount<>a.cnt OR participants::text<>a.part::text) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} corrected thread replycount and participant(s).")


# recalculate channel totalmsgcount(root) and lastpostat(root) because MM doesnt care about system posts AND edited posts for the counts, but always cares for timestamps... WHYYYY?!
cur.execute("""UPDATE channels SET totalmsgcount = a.cnt, totalmsgcountroot = a.cntr
            FROM ( SELECT channels.id, COUNT(posts.id) AS cnt, SUM(CASE WHEN NOT posts.id IS NULL AND (posts.rootid = '' OR posts.rootid IS NULL) THEN 1 ELSE 0 END) AS cntr
                FROM posts RIGHT JOIN channels ON (posts.channelid = channels.id AND posts.type NOT LIKE 'system_%' AND posts.originalid = '') GROUP BY channels.id ) AS a
            WHERE channels.id = a.id and (totalmsgcount IS DISTINCT FROM a.cnt OR totalmsgcountroot IS DISTINCT FROM a.cntr) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} updated channel totalmsgcount(root).")

cur.execute("""UPDATE channels SET lastpostat = a.lpts, lastrootpostat = a.lptsr
            FROM ( SELECT channels.id, COALESCE(MAX(posts.createat), 0) AS lpts,
                COALESCE(MAX(CASE WHEN NOT posts.id IS NULL AND (posts.rootid = '' OR posts.rootid IS NULL) THEN posts.createat ELSE 0 END),channels.updateat) AS lptsr
                FROM posts RIGHT JOIN channels ON (posts.channelid = channels.id) GROUP BY channels.id) AS a
            WHERE channels.id = a.id and (lastpostat > a.lpts OR lastrootpostat > a.lptsr) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} updated channel lastpostat(root).")


# fix msgcount(root)/lastviewedat.
cur.execute("""UPDATE channelmembers SET msgcount = totalmsgcount FROM channels WHERE channelid = channels.id AND msgcount > totalmsgcount RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} corrected channelmember's msgcount.")
cur.execute("""UPDATE channelmembers SET msgcountroot = totalmsgcountroot FROM channels WHERE channelid = channels.id AND msgcountroot > totalmsgcountroot RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} corrected channelmember's msgcountroot.")
cur.execute("""UPDATE channelmembers SET lastviewedat = lastpostat FROM channels WHERE channelid = channels.id AND lastviewedat > lastpostat RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} corrected channelmember's lastviewedat.")


cur.close()
print()



########################
# fix db-health issues #
########################
print("Fixing stuff ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)

# "refresh" materialized "view": publicchannels
cur.execute("""TRUNCATE publicchannels""")
cur.execute("""INSERT INTO publicchannels (id, deleteat, teamid, displayname, name, header, purpose) SELECT c.id, c.deleteat, c.teamid, c.displayname, c.name, c.header, c.purpose FROM channels c WHERE c.type = 'O'""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} inserted public channel(s) into 'materialized view'.")


# FIX: delete public channels from dm/group-channel list
cur.execute("""DELETE FROM preferences WHERE category = 'group_channel_show' AND name IN (SELECT id FROM channels WHERE type NOT IN ('G','D')) RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} deleted public channel group_channel_show preference(s). THIS IS A BUGFIX. SHOULD BE 0!")

# FIX: make guests converted to users not join any channel "as guest". github: https://github.com/mattermost/mattermost-server/issues/14821
cur.execute("""UPDATE channelmembers SET schemeuser = True, schemeguest = False FROM users WHERE channelmembers.userid = users.id AND schemeguest = True AND 'system_guest' != users.roles RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} corrected joins 'as guest' to channels for now-users. THIS IS A BUGFIX. SHOULD BE 0!")

# FIX: recalculate postcount to exclude deleted posts in threads table - migration issue of old threads. github: https://github.com/mattermost/mattermost-server/issues/16321
#cur.execute("""UPDATE threads SET replycount = a.cnt FROM (SELECT rootid, count(*) cnt, max(createat) ts FROM posts WHERE deleteat = 0 or deleteat = NULL GROUP BY 1) AS a WHERE threads.postid = a.rootid AND replycount <> a.cnt RETURNING *""")
#print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} corrected threads replycount(s).")

## Change limit of 40 to 400 direct message channels. Breaks settings page.
#cur.execute("""UPDATE preferences SET value='400' WHERE category='sidebar_settings' AND name='limit_visible_dms_gms' AND value='40' RETURNING *""")
#print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} user's dm sidebar limit set to 400.")

# remove "disable_group_highlight" prop from posts.
cur.execute("""UPDATE posts SET props = props::jsonb - 'disable_group_highlight' WHERE props::jsonb ? 'disable_group_highlight' RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} removed 'disable_group_highlight' prop from post(s).")

# order channels list alphabetically again
cur.execute("""UPDATE sidebarcategories SET sorting = '' WHERE type ='channels' AND sorting != '' RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} type = channel sidebarcategory reverted sorting to alphabetical.")
cur.execute("""DELETE FROM sidebarchannels WHERE sidebarchannels.categoryid IN (SELECT id FROM sidebarcategories WHERE type = 'channels') RETURNING *""")
print(f"* [{(time.time() - TS_START):08.5f}] {cur.rowcount} removed type = channel sidebarchannels sorting information.")


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
