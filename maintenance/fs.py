#!/usr/bin/env -S python3 -Bu
# Someone's Mattermost maintenance scripts.
#   Copyright (c) 2016-2025 by Someone <someone@somenet.org> (aka. Jan Vales <jan@jvales.net>)
#   published under MIT-License
#
# Permanently delete orphaned files (=no longer referenced in MM-db).
#

import os
import sys
import time
import psycopg2
import psycopg2.extras

import config
print("Mattermost FS cleanup script: https://git.somenet.org/pub/jan/mattermost-privileged.git")
print("Tested on 10.5\n")

dbconn = psycopg2.connect(config.dbconnstring)
dbconn.set_session(autocommit=False)


TS_START = time.time()

###############################
# get all db referenced files #
###############################
print("Getting db-referenced files ...")
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cur.execute("SELECT unnest(ARRAY[path, thumbnailpath, previewpath]) FROM fileinfo")
print(f"* [{round(time.time() - TS_START, 5):07.6g}] {cur.rowcount} referenced files in fileinfo.")
db_files = {val for sublist in cur.fetchall() for val in sublist}


# add all existing teams' teamicons
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cur.execute("SELECT id FROM teams WHERE lastteamiconupdate IS DISTINCT FROM 0")
print(f"* [{round(time.time() - TS_START, 5):07.6g}] {cur.rowcount} referenced team icons.")
db_files = db_files.union({"teams/"+val+"/teamIcon.png" for sublist in cur.fetchall() for val in sublist})


# add all existing user's profile.png
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cur.execute("SELECT id FROM users")
print(f"* [{round(time.time() - TS_START, 5):07.6g}] {cur.rowcount} referenced profile pics.")
db_files = db_files.union({"users/"+val+"/profile.png" for sublist in cur.fetchall() for val in sublist})


# add all existing emoji's image and image_deleted (as deleted emojis could still be recovered/reactivated in db)
cur = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cur.execute("SELECT id FROM emoji")
print(f"* [{round(time.time() - TS_START, 5):07.6g}] {cur.rowcount} possibly referenced emoji.")
db_files = db_files.union({"emoji/"+val+"/image" for sublist in cur.fetchall() for val in sublist})

cur.execute("SELECT id FROM emoji")
print(f"* [{round(time.time() - TS_START, 5):07.6g}] {cur.rowcount} possibly referenced deleted emoji.")
db_files = db_files.union({"emoji/"+val+"/image_deleted" for sublist in cur.fetchall() for val in sublist})


cur.close()
dbconn.close()
print(f"\n* [{round(time.time() - TS_START, 5):07.6g}] Files referenced in db: {len(db_files)}")



###############################
# get paths of physical files #
###############################
fs_files = set()
for relative_root, dirs, files in os.walk(config.fs_data_path):
    for file_ in files:
        # Compute the relative file path to the media directory, so it can be compared to the values from the db
        relative_file = os.path.join(os.path.relpath(relative_root, config.fs_data_path), file_)
        fs_files.add(relative_file)

if len(fs_files) < 3:
    print("Too few files. No access-permissions?")
    sys.exit(1)

print(f"* [{round(time.time() - TS_START, 5):07.6g}] Files on filesystem: {len(fs_files)}")



#########################
# diff + del files/dirs #
#########################
diff_files = fs_files - db_files
del_files = [f for f in diff_files if not f.startswith("brand/") and not f.startswith("plugins/")]

print(f"* [{round(time.time() - TS_START, 5):07.6g}] Files to be deleted: {len(del_files)}")


# show files to delete.
if del_files:
    for file_ in del_files:
        if hasattr(config, "dry_run") and config.dry_run:
            print("dry_run: would remove orphaned file: "+os.path.join(config.fs_data_path, file_))
        else:
            print("Removing orphaned file: "+os.path.join(config.fs_data_path, file_))
            os.remove(os.path.join(config.fs_data_path, file_))


# remove empty directories.
for relative_root, dirs, files in os.walk(config.fs_data_path, topdown=False):
    for dir_ in dirs:
        if not os.listdir(os.path.join(relative_root, dir_)):
            if hasattr(config, "dry_run") and config.dry_run:
                print("dry_run: would remove empty dir: "+os.path.join(relative_root, dir_))
            else:
                print("Removing empty dir: "+os.path.join(relative_root, dir_))
                os.rmdir(os.path.join(relative_root, dir_))
